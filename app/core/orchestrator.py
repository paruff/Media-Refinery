"""Drives every MediaItem through spec §4: scan → classify → plan → approve →
execute → verify → publish → archive. State is committed before side effects (R-PIPE-1)."""

import asyncio
import json
import logging
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.core.paths import ensure_inside
from app.core.planning import build_plan, is_audio_only
from app.core.publish import archive_original, publish_file, quarantine_file
from app.core.scanner import ScannerService
from app.core.tools import probe_duration, run_tool
from app.core.verify import sha256_file, verify_output
from app.models.media import (
    FileState,
    MediaItem,
    MediaType,
    NormalizationPlan,
    PlanStatus,
    VerificationRecord,
)
from app.models.saga import SagaFileMoveLog, SagaLogStatus

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


@dataclass
class PipelineConfig:
    input_dir: Path
    work_dir: Path
    archive_dir: Path
    quarantine_dir: Path
    music_root: Path
    movies_root: Path
    tv_root: Path
    dry_run: bool = False
    auto_approve_types: frozenset[str] = field(default_factory=frozenset)
    ffmpeg_timeout: float = 6 * 3600
    max_concurrent_execute: int = 2  # CPU-heavy stage bounded separately (R-PIPE-5)
    max_concurrent_io: int = 5

    @classmethod
    def from_settings(cls) -> "PipelineConfig":
        return cls(
            input_dir=Path(settings.INPUT_DIR),
            work_dir=Path(settings.WORK_DIR),
            archive_dir=Path(settings.ARCHIVE_DIR),
            quarantine_dir=Path(settings.QUARANTINE_DIR),
            music_root=Path(settings.MUSIC_ROOT),
            movies_root=Path(settings.MOVIES_ROOT),
            tv_root=Path(settings.TV_ROOT),
            dry_run=settings.DRY_RUN,
            auto_approve_types=frozenset(settings.AUTO_APPROVE_TYPES),
        )

    @property
    def roots(self) -> dict[str, str]:
        return {
            "music": str(self.music_root),
            "movie": str(self.movies_root),
            "series": str(self.tv_root),
        }

    def root_for(self, media_type) -> Path:
        return {
            MediaType.music: self.music_root,
            MediaType.movie: self.movies_root,
            MediaType.series: self.tv_root,
        }[MediaType(media_type)]


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


class PipelineOrchestrator:
    def __init__(
        self, session_factory, config: PipelineConfig, logger=None, poll_interval=2
    ):
        self.session_factory = session_factory
        self.cfg = config
        self.logger = logger or logging.getLogger("PipelineOrchestrator")
        self.poll_interval = poll_interval
        self.run_id = (
            datetime.now(UTC).strftime("%Y%m%dT%H%M%S-") + uuid.uuid4().hex[:6]
        )
        self.running = False
        self._io = asyncio.Semaphore(config.max_concurrent_io)
        self._exec = asyncio.Semaphore(config.max_concurrent_execute)
        self._scanner = ScannerService(session_factory, logger=self.logger)

    # ---- loop -----------------------------------------------------------
    async def run_forever(self):
        self.running = True
        await self.recover()
        while self.running:
            try:
                await self.run_once()
            except Exception:
                self.logger.exception("Orchestrator pass failed")
            await asyncio.sleep(self.poll_interval)

    async def run_once(self) -> int:
        """Advance every actionable item by one stage; return how many moved."""
        async with self.session_factory() as session:
            result = await session.execute(
                select(MediaItem.id, MediaItem.state).where(
                    MediaItem.state.in_(ACTIONABLE)
                )
            )
            rows = result.all()
        moved = await asyncio.gather(*(self._guarded(i, s) for i, s in rows))
        return sum(moved)

    async def run_until_idle(self, max_passes: int = 100) -> None:
        for _ in range(max_passes):
            if not await self.run_once():
                return

    # ---- crash resume (R-PIPE-1) -----------------------------------------
    async def recover(self) -> None:
        """Reset items caught mid-flight and drop half-finished publish temp files."""
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
    async def approve(self, item_id: str) -> bool:
        async with self.session_factory() as session:
            item = await session.get(MediaItem, item_id)
            if item is None or item.state != FileState.planned:
                return False
            plan = await self._plan(session, item_id)
            plan.plan_status = PlanStatus.approved
            item.state = FileState.approved
            item.updated_at = _now()
            await session.commit()
            return True

    # ---- dispatch -----------------------------------------------------------
    async def _guarded(self, item_id, state) -> bool:
        sem = self._exec if state == FileState.approved else self._io
        async with sem:
            try:
                return await self._advance(item_id, state)
            except Exception as e:
                self.logger.exception(f"Pipeline failed for {item_id}")
                await self._mark(item_id, FileState.error, str(e))
                return True

    async def _advance(self, item_id, state) -> bool:
        handlers = {
            FileState.pending: self._scan,
            FileState.scanned: self._classify,
            FileState.enriched: self._plan_stage,
            FileState.planned: self._gate,
            FileState.approved: self._execute,
            FileState.executed: self._verify,
            FileState.verified: self._publish,
            FileState.published: self._archive,
        }
        return await handlers[state](item_id)

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

    def _work(self, item_id, ext="") -> Path:
        return self.cfg.work_dir / str(item_id) / f"out{ext}"

    # ---- stages -------------------------------------------------------------
    async def _scan(self, item_id) -> bool:
        await self._scanner.run(item_id)  # ends in scanned or error
        return True

    async def _classify(self, item_id) -> bool:
        from app.services.classification import ClassificationService

        async with self.session_factory() as session:
            await ClassificationService(session).classify_file(item_id)  # type: ignore[arg-type]
            item = await session.get(MediaItem, item_id)
            await session.refresh(item)
            if (
                item.media_type == MediaType.unknown
            ):  # R-PIPE-4: audio ⇒ music, else movie
                item.media_type = (
                    MediaType.music if is_audio_only(item) else MediaType.movie
                )
            item.state = FileState.enriched
            await session.commit()
        return True

    async def _plan_stage(self, item_id) -> bool:
        async with self.session_factory() as session:
            item = await session.get(MediaItem, item_id)
            try:
                spec = build_plan(item, self.cfg.roots)
            except ValueError as e:
                item.state, item.error_log = FileState.error, str(e)
                await session.commit()
                return True
            clash = await session.execute(
                select(NormalizationPlan.id).where(
                    NormalizationPlan.target_path == spec.target_path
                )
            )
            if clash.first():
                item.state, item.error_log = (
                    FileState.quarantined,
                    f"plan_conflict: {spec.target_path}",
                )
                await session.commit()
                return True
            session.add(
                NormalizationPlan(
                    media_item_id=item.id,
                    target_path=spec.target_path,
                    ffmpeg_args=spec.ffmpeg_args,
                    original_hash=str(item.id),
                    needs_transcode=spec.needs_transcode,
                    needs_rename=True,
                )
            )
            item.state = FileState.planned
            await session.commit()
        return True

    async def _gate(self, item_id) -> bool:
        """APPROVE gate: dry-run reports; opt-in rules approve; otherwise wait for a human."""
        async with self.session_factory() as session:
            item = await session.get(MediaItem, item_id)
            media_type = str(MediaType(item.media_type).value)
        if self.cfg.dry_run:
            return await self._dry_run_report(item_id)
        if media_type in self.cfg.auto_approve_types:
            return await self.approve(item_id)
        return False

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
        return True

    async def _run_ffmpeg(self, source: str, args: list[str], out: Path):
        return await run_tool(
            ["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", source, *args, str(out)],
            self.cfg.ffmpeg_timeout,
        )

    async def _execute(self, item_id) -> bool:
        if self.cfg.dry_run:
            return False
        async with self.session_factory() as session:
            item = await session.get(MediaItem, item_id)
            plan = await self._plan(session, item_id)
            ext = Path(str(plan.target_path)).suffix
            item.state, plan.plan_status = FileState.executing, PlanStatus.executing
            await session.commit()  # persisted before any side effect
            work = self._work(item_id, ext)
            shutil.rmtree(work.parent, ignore_errors=True)
            work.parent.mkdir(parents=True)
            tmp = work.with_name(
                f"out.tmp{ext}"
            )  # ffmpeg infers the container from the suffix
            rc, _, err = await self._run_ffmpeg(
                str(item.source_path), list(plan.ffmpeg_args or []), tmp
            )
            plan.execution_log = f"{plan.execution_log}\nffmpeg rc={rc}\n{err}".strip()
            if rc != 0:
                tmp.unlink(missing_ok=True)
                await self._quarantine(
                    session, item, "convert_failed", err.strip()[:500]
                )
                return True
            tmp.replace(work)
            item.state = FileState.executed
            await session.commit()
        return True

    async def _verify(self, item_id) -> bool:
        async with self.session_factory() as session:
            item = await session.get(MediaItem, item_id)
            plan = await self._plan(session, item_id)
            work = self._work(item_id, Path(str(plan.target_path)).suffix)
            if not work.exists():  # lost between stages: redo the conversion
                item.state, plan.plan_status = FileState.approved, PlanStatus.approved
                await session.commit()
                return True
            checks, digest, reason = await verify_output(
                str(item.source_path), str(work), is_audio_only(item)
            )
            session.add(
                VerificationRecord(
                    media_item_id=item_id,
                    passed=reason is None,
                    checks=checks,
                    output_sha256=digest,
                )
            )
            if reason:
                detail = "; ".join(
                    f"{c['name']}: {c['detail']}" for c in checks if not c["passed"]
                )
                await self._quarantine(session, item, reason, detail, work)
            else:
                item.state = FileState.verified
                await session.commit()
        return True

    async def _publish(self, item_id) -> bool:
        async with self.session_factory() as session:
            item = await session.get(MediaItem, item_id)
            plan = await self._plan(session, item_id)
            dest = ensure_inside(
                self.cfg.root_for(item.media_type), str(plan.target_path)
            )
            work = self._work(item_id, dest.suffix)
            record = (
                (
                    await session.execute(
                        select(VerificationRecord)
                        .where(
                            VerificationRecord.media_item_id == item_id,
                            VerificationRecord.passed,
                        )
                        .order_by(VerificationRecord.created_at.desc())
                    )
                )
                .scalars()
                .first()
            )
            if record is None:
                raise RuntimeError("verified item has no passing VerificationRecord")
            sha = str(record.output_sha256)
            if dest.exists():
                if await asyncio.to_thread(sha256_file, str(dest)) != sha:
                    await self._quarantine(
                        session, item, "target_exists", str(dest), work
                    )
                    return True
                # resumed after a crash that landed the file but not the state
            else:
                await publish_file(session, str(plan.id), work, dest, sha)
            item.state = FileState.published
            await session.commit()
        return True

    async def _archive(self, item_id) -> bool:
        """After VERIFY passed and the file is published, move (never delete) the original."""
        async with self.session_factory() as session:
            item = await session.get(MediaItem, item_id)
            plan = await self._plan(session, item_id)
            source = Path(str(item.source_path))
            archived = await asyncio.to_thread(
                archive_original,
                source,
                self.cfg.input_dir,
                self.cfg.archive_dir,
                self.run_id,
            )
            if archived:
                plan.execution_log = (
                    f"{plan.execution_log}\narchived: {archived}".strip()
                )
            shutil.rmtree(self.cfg.work_dir / item_id, ignore_errors=True)
            plan.plan_status = PlanStatus.completed
            item.state = FileState.validated
            item.updated_at = _now()
            await session.commit()
        return True
