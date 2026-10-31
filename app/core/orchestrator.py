"""Drives every MediaItem through spec §4: scan → classify → plan → approve →
execute → verify → publish → archive. State is committed before side effects (R-PIPE-1).
This is the stage driver only: stage bodies live in app/pipeline, per-type behaviour in
app/pipeline/types."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

from sqlalchemy import select, update

from app.core.paths import ensure_inside
from app.core.publish import quarantine_file
from app.core.scanner import ScannerService
from app.core.throttle import AdaptiveLimiter
from app.core.tools import probe_duration, run_tool
from app.core.trace import Status, TraceWriter
from app.models.media import (
    FileState,
    MediaItem,
    MediaType,
    NormalizationPlan,
    PlanStatus,
)
from app.models.saga import SagaFileMoveLog, SagaLogStatus
from app.pipeline import classify, execute, plan, publish, verify
from app.pipeline.config import PipelineConfig
from app.pipeline.types.base import needs_review
from app.services.fingerprint_service import FingerprintService
from app.services.notify import Notifier

STAGE_ORDER = (
    FileState.pending,
    FileState.scanned,
    FileState.enriched,
    FileState.planned,
    FileState.approved,
    FileState.executed,
    FileState.verified,
    FileState.published,
)
ACTIONABLE = (
    FileState.pending,
    FileState.scanned,
    FileState.enriched,
    FileState.planned,
    FileState.approved,
    FileState.executed,
    FileState.verified,
    FileState.published,
)


def _preflight(source: Path, target: Path, root: Path) -> list[dict]:
    """Dry-run checks that touch the filesystem (read-only)."""
    checks = [{"name": "source_readable", "passed": source.is_file()}]
    try:
        ensure_inside(root, target)
        checks.append({"name": "target_confined", "passed": True})
    except ValueError as e:
        checks.append({"name": "target_confined", "passed": False, "detail": str(e)})
    checks.append({"name": "target_free", "passed": not target.exists()})
    return checks


def _now() -> datetime:
    return datetime.now(UTC)


RETRYABLE = (FileState.error, FileState.quarantined)


class PipelineOrchestrator:
    def __init__(
        self,
        session_factory,
        config: PipelineConfig,
        logger=None,
        poll_interval=2,
        enricher=None,
        identifier=None,
        notifier=None,
    ):
        self.session_factory = session_factory
        self.plan_lock = asyncio.Lock()  # serializes PLAN's target check + insert
        self.cfg = config
        self.enricher = (
            enricher  # VideoEnricher (TMDB/TVDB) or None = guessit names only
        )
        self.identifier = (
            identifier  # MusicIdentifier (AcoustID/MB) or None = tags only
        )
        self.notifier = notifier or Notifier()
        self.logger = logger or logging.getLogger("PipelineOrchestrator")
        self.poll_interval = poll_interval
        self.run_id = (
            datetime.now(UTC).strftime("%Y%m%dT%H%M%S-") + uuid.uuid4().hex[:6]
        )
        self.running = False
        self.stage_seconds: dict[str, tuple[float, int]] = {}  # stage -> (total, runs)
        self._execute_ok: dict[
            str, bool
        ] = {}  # per-item EXECUTE outcome, recorded by _guarded
        self._io = asyncio.Semaphore(config.max_concurrent_io)
        self._exec = AdaptiveLimiter(
            config.max_concurrent_execute, config.throttle_after_failures
        )
        trace_path = config.trace_path or config.work_dir / "trace.jsonl"
        if config.dry_run:  # R-SAFE-4: dry-run writes only under work/dry-run/
            trace_path = config.work_dir / "dry-run" / "trace.jsonl"
        self.trace = TraceWriter(trace_path, self.run_id)
        self._scanner = ScannerService(session_factory, logger=self.logger)
        self._album_lock = asyncio.Lock()
        self._calibre_lock = asyncio.Lock()  # one calibredb writer per library
        self._album_gain: dict[Path, tuple[str, str] | None] = {}

    # ---- loop -----------------------------------------------------------
    async def run_forever(self):
        if self.cfg.enabled_types & {"movie", "series"}:
            FingerprintService.require_video_support()  # fail at startup, not per file
        self.running = True
        await self.recover()
        while self.running:
            try:
                await self.run_once()
            except Exception:
                self.logger.exception("Orchestrator pass failed")
            await asyncio.sleep(self.poll_interval)

    async def run_once(
        self,
        until: FileState | None = None,
        only: set[str] | None = None,
        types: set[str] | None = None,
    ) -> int:
        """Advance every actionable item by one stage; return how many moved.

        `until` leaves items already at that stage alone, `only` limits to item ids
        and `types` to media types (unclassified items still pass, to get classified).
        """
        async with self.session_factory() as session:
            result = await session.execute(
                select(MediaItem.id, MediaItem.state, MediaItem.media_type).where(
                    MediaItem.state.in_(ACTIONABLE)
                )
            )
            rows = result.all()
        stop = STAGE_ORDER.index(until) if until else len(STAGE_ORDER)
        if (
            self.cfg.dry_run
        ):  # R-SAFE-4: never act past planning, whatever state the DB is in
            stop = min(stop, STAGE_ORDER.index(FileState.approved))
        todo = [
            (i, s)
            for i, s, t in rows
            if STAGE_ORDER.index(s) < stop
            and (only is None or i in only)
            and (not types or t == MediaType.unknown or t.value in types)
            and (t == MediaType.unknown or t.value in self.cfg.enabled_types)
        ]
        moved = await asyncio.gather(*(self._guarded(i, s) for i, s in todo))
        return sum(moved)

    async def run_until_idle(self, max_passes: int = 100, **filters) -> None:
        try:
            for _ in range(max_passes):
                if not await self.run_once(**filters):
                    return
        finally:
            await (
                self.notifier.flush()
            )  # nothing left to wait for: send the queued rescans

    # ---- crash resume (R-PIPE-1) -----------------------------------------
    async def recover(self) -> None:
        """Reset items caught mid-flight and drop half-finished publish temp files."""
        if self.cfg.dry_run:  # R-SAFE-4: recovery deletes work files and rewrites sagas
            return
        async with self.session_factory() as session:
            for item in await self._items(session, FileState.scanning):
                item.state = FileState.pending
            for item in await self._items(session, FileState.executing):
                item.state = FileState.approved
                shutil.rmtree(self.cfg.work_dir / str(item.id), ignore_errors=True)
            sagas = await session.execute(
                select(SagaFileMoveLog).where(
                    SagaFileMoveLog.status == SagaLogStatus.prepared
                )
            )
            for log in sagas.scalars():
                await asyncio.to_thread(Path(str(log.tmp_path)).unlink, missing_ok=True)
                log.status = SagaLogStatus.failed
                log.error = "recovered after crash"
            await session.commit()

    async def _items(self, session, state):
        result = await session.execute(
            select(MediaItem).where(MediaItem.state == state)
        )
        return result.scalars().all()

    # ---- approval gate ----------------------------------------------------
    async def _claim(self, session, item_id: str, frm, to: FileState) -> bool:
        """Atomic conditional state change: of N racing callers exactly one gets rowcount 1."""
        res = await session.execute(
            update(MediaItem)
            .where(MediaItem.id == item_id, MediaItem.state.in_(frm))
            .values(state=to, updated_at=_now())
        )
        return res.rowcount == 1

    async def approve(self, item_id: str) -> bool:
        async with self.session_factory() as session:
            if not await self._claim(
                session, item_id, (FileState.planned,), FileState.approved
            ):
                return False
            plan = await self._plan(session, item_id)
            plan.plan_status = PlanStatus.approved
            await session.commit()
            return True

    async def reject(self, item_id: str) -> bool:
        """A reviewer declines a plan: nothing is touched, the item parks in quarantine."""
        async with self.session_factory() as session:
            if not await self._claim(
                session, item_id, (FileState.planned,), FileState.quarantined
            ):
                return False
            item = await session.get(MediaItem, item_id)
            await self._quarantine(session, item, "rejected", "declined at review")
            return True

    async def retry(self, item_id: str) -> bool:
        """Re-queue a failed/quarantined item from the start; its source must still exist."""
        async with self.session_factory() as session:
            # Claim first: the write lock is then held across the source check, so the check
            # judges the state we actually transition. Rolled back explicitly if it's gone.
            if not await self._claim(session, item_id, RETRYABLE, FileState.pending):
                return False
            item = await session.get(MediaItem, item_id)
            if not await self._source_exists(item):
                await session.rollback()
                return False
            plan = await session.execute(
                select(NormalizationPlan).where(
                    NormalizationPlan.media_item_id == item_id
                )
            )
            if (old := plan.scalar_one_or_none()) is not None:
                await session.delete(old)
            await session.execute(
                update(MediaItem).where(MediaItem.id == item_id).values(error_log=None)
            )
            # Deliberately inside the write txn (briefly holds the sqlite write lock): after the
            # commit the item is pending and the pipeline may start using the dir.
            await asyncio.to_thread(
                shutil.rmtree, self.cfg.work_dir / item_id, ignore_errors=True
            )
            await session.commit()
        return True

    @staticmethod
    async def _source_exists(item) -> bool:
        return await asyncio.to_thread(Path(str(item.source_path)).is_file)

    async def refusal(self, item_id: str, action: str, item=None) -> str:
        """Why `action` was refused, for the 409/notice text. Pass a freshly loaded `item` to skip the read."""
        if item is None:
            async with self.session_factory() as session:
                item = await session.get(MediaItem, item_id)
        if item is None:
            return "no such item"
        if (
            action == "retry"
            and item.state in RETRYABLE
            and not await self._source_exists(item)
        ):
            return f"its source file is missing ({item.source_path})"
        return f"it is {item.state.value}"

    # ---- dispatch -----------------------------------------------------------
    async def _guarded(self, item_id, state) -> bool:
        sem = self._exec if state == FileState.approved else self._io
        async with sem:
            start = time.monotonic()
            try:
                return await self._advance(item_id, state)
            except Exception as e:
                self.logger.exception(f"Pipeline failed for {item_id}")
                if state == FileState.approved:
                    self._execute_ok[item_id] = False
                await self._mark(item_id, FileState.error, str(e))
                return True
            finally:
                # the single place EXECUTE outcomes reach the throttle; bad input records nothing
                if state == FileState.approved and item_id in self._execute_ok:
                    self._record_execute(self._execute_ok.pop(item_id))
                total, count = self.stage_seconds.get(state.value, (0.0, 0))
                self.stage_seconds[state.value] = (
                    total + time.monotonic() - start,
                    count + 1,
                )

    async def _advance(self, item_id, state) -> bool:
        handlers: dict[FileState, Callable[[str], Awaitable[bool]]] = {
            FileState.pending: self._scan,
            FileState.scanned: partial(classify.run, self),
            FileState.enriched: partial(plan.run, self),
            FileState.planned: self._gate,
            FileState.approved: partial(execute.run, self),
            FileState.executed: partial(verify.run, self),
            FileState.verified: self._publish,
            FileState.published: partial(publish.archive, self),
        }
        return await handlers[state](item_id)

    def _record_execute(self, ok: bool) -> None:
        """Feed the adaptive throttle; trace when it halves the EXECUTE workers."""
        if (limit := self._exec.record(ok)) is not None:
            self.logger.warning(f"EXECUTE failures: reducing workers to {limit}")
            self.trace.emit("workers.throttle", "", "degraded", f"new_workers={limit}")

    def _emit(self, event: str, item_id, status: Status, detail: str = "") -> None:
        self.trace.emit(event, str(item_id), status, detail)

    async def _mark(self, item_id, state, error=None):
        async with self.session_factory() as session:
            item = await session.get(MediaItem, item_id)
            if item is not None:
                item.state = state
                item.error_log = error
                item.updated_at = _now()
                await session.commit()

    async def _plan(self, session, item_id) -> NormalizationPlan:
        result = await session.execute(
            select(NormalizationPlan).where(NormalizationPlan.media_item_id == item_id)
        )
        return result.scalar_one()

    async def _quarantine(
        self, session, item, reason, detail, file: Path | None = None
    ):
        if file is not None:
            await asyncio.to_thread(
                quarantine_file, file, self.cfg.quarantine_dir, reason, str(item.id)
            )
        plan = await self._plan(session, str(item.id))
        plan.plan_status = PlanStatus.failed
        item.state = FileState.quarantined
        item.error_log = f"{reason}: {detail}"
        item.updated_at = _now()
        shutil.rmtree(self.cfg.work_dir / str(item.id), ignore_errors=True)
        await session.commit()
        self.logger.warning(f"Quarantined {item.id} ({reason}): {detail}")
        self._emit("quarantine", item.id, "quarantined", reason)

    def _work(self, item_id, ext="") -> Path:
        return self.cfg.work_dir / str(item_id) / f"out{ext}"

    # ---- stages -------------------------------------------------------------
    async def _publish(self, item_id) -> bool:
        return await publish.publish(self, item_id)

    async def _run_ffmpeg(self, source: str, args: list[str], out: Path):
        return await run_tool(
            ["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", source, *args, str(out)],
            self.cfg.ffmpeg_timeout,
        )

    async def _scan(self, item_id) -> bool:
        await self._scanner.run(item_id)  # ends in scanned or error
        return True

    async def _gate(self, item_id) -> bool:
        """APPROVE gate: dry-run reports; opt-in rules approve; otherwise wait for a human."""
        async with self.session_factory() as session:
            item = await session.get(MediaItem, item_id)
            media_type = str(MediaType(item.media_type).value)
        if self.cfg.dry_run:
            return await self._dry_run_report(item_id)
        if media_type in self.cfg.auto_approve_types and not self._needs_review(item):
            return await self.approve(item_id)
        return False

    _needs_review = staticmethod(needs_review)

    async def _dry_run_report(self, item_id) -> bool:
        """Plan + verify-preflight; the only writes are under work/dry-run/ (R-SAFE-4)."""
        report_path = self.cfg.work_dir / "dry-run" / f"{item_id}.json"
        if report_path.exists():
            return False
        async with self.session_factory() as session:
            item = await session.get(MediaItem, item_id)
            plan = await self._plan(session, item_id)
            target, source = Path(str(plan.target_path)), Path(str(item.source_path))
            checks = await asyncio.to_thread(
                _preflight, source, target, self.cfg.root_for(item.media_type)
            )
            duration = await probe_duration(str(source))
            checks.append({"name": "source_probe", "passed": duration is not None})
            report = {
                "item_id": item_id,
                "source": str(source),
                "target": str(target),
                "ffmpeg_args": plan.ffmpeg_args,
                "needs_transcode": plan.needs_transcode,
                "preflight": checks,
            }

        def write():
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, indent=2))

        await asyncio.to_thread(write)
        self._emit("plan", item_id, "dry_run", report["target"])
        return True

    def _notify(self, media_type: str, dest: Path) -> None:
        """Queue the server rescan; a notifier problem must never fail a published item."""
        try:
            self.notifier.schedule(media_type, dest)
        except Exception:
            self.logger.warning("notify scheduling failed for %s", dest, exc_info=True)
