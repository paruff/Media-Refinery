"""The operations behind both the REST API and the `refinery` CLI (no logic in either)."""

import asyncio
import logging
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.core.orchestrator import PipelineConfig, PipelineOrchestrator
from app.core.tools import run_tool
from app.core.verify import sha256_file
from app.core.watcher import import_file, is_excluded
from app.models.media import (
    FileState,
    MediaItem,
    NormalizationPlan,
    VerificationRecord,
)
from app.services.auditor import IssueDetectorService
from app.services.enrich import VideoEnricher
from app.services.music_id import MusicIdentifier

PUBLISHED_STATES = (FileState.published, FileState.validated, FileState.audited)


def build_orchestrator(session_factory, cfg: PipelineConfig, logger=None):
    """Orchestrator wired with whichever enrichers have API keys configured."""
    enricher = (
        VideoEnricher(settings.TMDB_API_KEY, settings.TVDB_API_KEY)
        if settings.TMDB_API_KEY
        or settings.TVDB_API_KEY  # each lookup no-ops without its key
        else None
    )
    identifier = (
        MusicIdentifier(
            settings.ACOUSTID_API_KEY, threshold=settings.ACOUSTID_MIN_SCORE
        )
        if settings.ACOUSTID_API_KEY
        else None
    )
    return PipelineOrchestrator(
        session_factory, cfg, logger=logger, enricher=enricher, identifier=identifier
    )


# rough rates behind library_report's estimates (single worker)
PER_ITEM_S = 0.5
COPY_BYTES_PER_S = 100e6
TRANSCODE_BYTES_PER_S = 2e6


def _files_under(path: Path) -> list[Path]:
    return [path] if path.is_file() else sorted(path.rglob("*"))


def _under(path: Path, value) -> bool:
    return value is not None and Path(str(value)).resolve().is_relative_to(path)


class Refinery:
    def __init__(self, orchestrator: PipelineOrchestrator):
        self.orch = orchestrator
        self.factory = orchestrator.session_factory
        self.cfg = orchestrator.cfg
        self.logger = logging.getLogger("Refinery")

    async def ingest(self, path: Path) -> list[str]:
        """Import every stable file under `path` as a pending item; return their ids."""
        files = await asyncio.to_thread(_files_under, path)
        ids = []
        for f in files:
            if not f.is_file() or is_excluded(f):
                continue
            if item_id := await import_file(str(f), self.factory, self.logger):
                ids.append(item_id)
        return ids

    async def advance(self, ids, until: FileState | None = None, types=None) -> None:
        await self.orch.run_until_idle(until=until, only=set(ids), types=types)

    async def approve(self, ids, types=None, skip_review: bool = False) -> int:
        """Approve planned items in scope; `skip_review` leaves low-confidence ones."""
        async with self.factory() as session:
            rows = (
                await session.execute(
                    select(MediaItem).where(
                        MediaItem.id.in_(list(ids)),
                        MediaItem.state == FileState.planned,
                    )
                )
            ).scalars()
            planned = [
                str(i.id)
                for i in rows
                if (not types or i.media_type.value in types)
                and not (skip_review and self.orch._needs_review(i))
            ]
        approved = [await self.orch.approve(i) for i in planned]
        return sum(approved)

    async def plan_rows(self, ids) -> list[dict]:
        """One row per item: what would happen (source → target, transcode or not)."""
        async with self.factory() as session:
            result = await session.execute(
                select(MediaItem, NormalizationPlan)
                .outerjoin(
                    NormalizationPlan, NormalizationPlan.media_item_id == MediaItem.id
                )
                .where(MediaItem.id.in_(list(ids)))
                .order_by(MediaItem.source_path)
            )
            return [
                {
                    "id": str(item.id),
                    "type": item.media_type.value,
                    "state": item.state.value,
                    "source": str(item.source_path),
                    "target": str(plan.target_path) if plan else "",
                    "action": (
                        "transcode" if plan and plan.needs_transcode else "copy/tag"
                    )
                    if plan
                    else "",
                    "error": str(item.error_log or ""),
                }
                for item, plan in result.all()
            ]

    async def library_report(self, ids) -> dict:
        """Library-level summary of a plan: counts by outcome, review list, disk/time estimate.

        Estimates are rough (size-based, fixed rates), meant to size a run, not to promise it.
        """
        async with self.factory() as session:
            result = await session.execute(
                select(MediaItem, NormalizationPlan)
                .outerjoin(
                    NormalizationPlan, NormalizationPlan.media_item_id == MediaItem.id
                )
                .where(MediaItem.id.in_(list(ids)))
                .order_by(MediaItem.source_path)
            )
            rows = result.all()
        outcomes: dict[str, int] = {}
        review, failed = [], []
        disk = seconds = 0
        for item, plan in rows:
            if item.state == FileState.planned and plan is not None:
                outcome = "transcode" if plan.needs_transcode else "copy/tag"
                size = int(item.size or 0)
                disk += size
                rate = (
                    TRANSCODE_BYTES_PER_S if plan.needs_transcode else COPY_BYTES_PER_S
                )
                seconds += PER_ITEM_S + size / rate
                if self.orch._needs_review(item):
                    review.append(str(item.source_path))
            else:
                outcome = item.state.value
                if item.error_log:
                    failed.append(f"{item.source_path}: {item.error_log}")
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
        return {
            "total": len(rows),
            "outcomes": dict(sorted(outcomes.items())),
            "needs_review": review,
            "not_planned": failed,
            "est_disk_bytes": disk,
            "est_seconds": round(seconds),
        }

    async def run(self, path: Path, types=None) -> list[str]:
        """scan → plan → (approve unless dry-run, minus items needing review) → publish."""
        ids = await self.ingest(path)
        await self.advance(ids, FileState.planned, types)
        if not self.cfg.dry_run:
            await self.approve(ids, types, skip_review=True)
        await self.advance(ids, None, types)
        return ids

    async def verify(self, path: Path) -> list[dict]:
        """R-VERIFY-2: re-check published outputs under `path` (non-destructive)."""
        path = await asyncio.to_thread(path.resolve)
        async with self.factory() as session:
            result = await session.execute(
                select(MediaItem, NormalizationPlan)
                .join(
                    NormalizationPlan, NormalizationPlan.media_item_id == MediaItem.id
                )
                .where(MediaItem.state.in_(PUBLISHED_STATES))
            )
            published = [(i, p) for i, p in result.all() if _under(path, p.target_path)]
            report = []
            for item, plan in published:
                record = (
                    (
                        await session.execute(
                            select(VerificationRecord)
                            .where(VerificationRecord.media_item_id == item.id)
                            .order_by(VerificationRecord.created_at.desc())
                        )
                    )
                    .scalars()
                    .first()
                )
                report.append(await self._drift(item, plan, record))
        return report

    @staticmethod
    async def _drift(item, plan, record) -> dict:
        target = Path(str(plan.target_path))
        problems = []
        if not await asyncio.to_thread(target.is_file):
            problems.append("missing")
        elif item.media_type.value != "ebook":
            if record and record.output_sha256 != sha256_file(str(target)):
                problems.append("sha256 changed")
            rc, _, err = await run_tool(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-v",
                    "error",
                    "-i",
                    str(target),
                    "-f",
                    "null",
                    "-",
                ],
                3600,
            )
            if rc != 0 or err.strip():
                problems.append("decode errors")
        return {
            "id": str(item.id),
            "path": str(target),
            "ok": not problems,
            "problems": problems,
        }

    async def audit(self, path: Path) -> list[dict]:
        """Run the issue detector over library items whose source or output is under `path`."""
        path = await asyncio.to_thread(path.resolve)
        async with self.factory() as session:
            result = await session.execute(
                select(MediaItem, NormalizationPlan)
                .outerjoin(
                    NormalizationPlan, NormalizationPlan.media_item_id == MediaItem.id
                )
                .where(MediaItem.state.in_(PUBLISHED_STATES))
            )
            ids = [
                str(i.id)
                for i, p in result.all()
                if _under(path, i.source_path) or (p and _under(path, p.target_path))
            ]
            for item_id in ids:
                await IssueDetectorService(session).audit(item_id)  # type: ignore[arg-type]
            await session.commit()
            rows = (
                await session.execute(select(MediaItem).where(MediaItem.id.in_(ids)))
            ).scalars()
            return [
                {"id": str(i.id), "issues": str(i.detected_issues or "[]")}
                for i in rows
            ]
