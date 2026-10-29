import logging
from collections import Counter
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media import MediaItem


class StateCount(BaseModel):
    state: str
    count: int


class MediaTypeCount(BaseModel):
    media_type: str
    count: int


# quarantine reason -> what the operator should do about it
SUGGESTED_ACTION = {
    "rejected": "Declined at review; restore the source if that was a mistake.",
    "healthcheck_failed": "The source is damaged; re-acquire or repair it, then retry.",
    "convert_failed": "Check the ffmpeg error in the item log; retry once the cause is fixed.",
    "target_exists": "A different file already holds the target path; resolve the clash, then retry.",
    "calibre_add_failed": "Run `refinery doctor`; check Calibre and the library path, then retry.",
}
DEFAULT_ACTION = "Read the item error log, fix the cause, then retry."


def quarantine_reason(error_log: str | None) -> str:
    """`_quarantine` stores "<reason>: <detail>"."""
    return (error_log or "unknown").split(":", 1)[0]


class QuarantineReason(BaseModel):
    reason: str
    count: int
    action: str


class SystemSummary(BaseModel):
    total: int
    by_state: list[StateCount]
    by_media_type: list[MediaTypeCount]
    validated_success_rate: float
    error_log: list[str]
    warnings: list[str] = []
    storage_bytes: int = 0
    quarantine_reasons: list[QuarantineReason] = []


async def quarantine_counts(db: AsyncSession) -> dict[str, int]:
    logs: Sequence[Any] = (
        (
            await db.execute(
                select(MediaItem.error_log).where(MediaItem.state == "quarantined")
            )
        )
        .scalars()
        .all()
    )
    return dict(Counter(quarantine_reason(log) for log in logs))


class ReportingService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.logger = logging.getLogger("ReportingService")

    async def get_summary(self) -> SystemSummary:
        # Total count
        total = await self.db.scalar(select(func.count()).select_from(MediaItem))
        # By state
        state_rows: Sequence[Any] = (
            await self.db.execute(
                select(MediaItem.state, func.count()).group_by(MediaItem.state)
            )
        ).all()
        by_state = [StateCount(state=s, count=c) for s, c in state_rows]
        # By media_type
        mt_rows: Sequence[Any] = (
            await self.db.execute(
                select(MediaItem.media_type, func.count()).group_by(
                    MediaItem.media_type
                )
            )
        ).all()
        by_media_type = [MediaTypeCount(media_type=mt, count=c) for mt, c in mt_rows]
        # Success rate
        validated = next((c.count for c in by_state if c.state == "validated"), 0)
        validated_success_rate = (validated / total) * 100 if total else 0.0
        # Error log (last 10 unique)
        # from sqlalchemy.orm import joinedload (unused)
        from typing import cast

        from app.models.media import NormalizationPlan

        error_rows: Sequence[Any] = (
            (
                await self.db.execute(
                    select(NormalizationPlan.execution_log)
                    .join(MediaItem, NormalizationPlan.media_item_id == MediaItem.id)
                    .where(MediaItem.state == "error")
                    .where(NormalizationPlan.execution_log.is_not(None))
                    .order_by(desc(MediaItem.updated_at))
                )
            )
            .scalars()
            .all()
        )
        error_log = list(dict.fromkeys([cast(str, e) for e in error_rows if e]))[:10]
        # Warnings (files with missing metadata but not error)
        warning_rows = (
            (
                await self.db.execute(
                    select(NormalizationPlan.execution_log)
                    .join(MediaItem, NormalizationPlan.media_item_id == MediaItem.id)
                    .where(MediaItem.state != "error")
                    .where(NormalizationPlan.execution_log.contains("missing metadata"))
                )
            )
            .scalars()
            .all()
        )
        warnings = list(dict.fromkeys([w for w in warning_rows if w]))[:10]
        # Same-album duplicates are skipped; surface the count so the user can decide (#178)
        dup_skipped = await self.db.scalar(
            select(func.count())
            .select_from(MediaItem)
            .where(MediaItem.state == "error")
            .where(MediaItem.error_log.like("Duplicate % fingerprint detected%"))
        )
        if dup_skipped:
            warnings.append(
                f"{dup_skipped} item(s) skipped as duplicates by fingerprint within"
                " the same album; review them and keep or delete the extras."
            )
        # Storage impact (sum of file sizes if available)
        size_rows = (
            await self.db.execute(
                select(func.sum(MediaItem.size)).where(MediaItem.size.is_not(None))
            )
        ).first()
        storage_bytes = 0
        if size_rows and size_rows[0] is not None:
            storage_bytes = size_rows[0]
        return SystemSummary(
            total=total if total is not None else 0,
            by_state=by_state,
            by_media_type=by_media_type,
            validated_success_rate=validated_success_rate,
            error_log=error_log,
            warnings=warnings,
            storage_bytes=storage_bytes,
            quarantine_reasons=[
                QuarantineReason(
                    reason=r, count=n, action=SUGGESTED_ACTION.get(r, DEFAULT_ACTION)
                )
                for r, n in (await quarantine_counts(self.db)).items()
            ],
        )

    async def log_daily_digest(self):
        summary = await self.get_summary()
        self.logger.info(f"Daily Digest: {summary.json(indent=2)}")
