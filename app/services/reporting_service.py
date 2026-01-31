from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, desc
from app.models.media import MediaItem
from pydantic import BaseModel
import logging


class StateCount(BaseModel):
    state: str
    count: int


class MediaTypeCount(BaseModel):
    media_type: str
    count: int


class SystemSummary(BaseModel):
    total: int
    by_state: List[StateCount]
    by_media_type: List[MediaTypeCount]
    validated_success_rate: float
    error_log: List[str]
    warnings: List[str] = []
    storage_bytes: int = 0


class ReportingService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.logger = logging.getLogger("ReportingService")

    async def get_summary(self) -> SystemSummary:
        # Total count
        total = await self.db.scalar(select(func.count()).select_from(MediaItem))
        # By state
        state_rows = (
            await self.db.execute(
                select(MediaItem.state, func.count()).group_by(MediaItem.state)
            )
        ).all()
        by_state = [StateCount(state=s, count=c) for s, c in state_rows]
        # By media_type
        mt_rows = (
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
        error_rows = (
            (
                await self.db.execute(
                    select(MediaItem.execution_log)
                    .where(MediaItem.state == "error")
                    .where(MediaItem.execution_log.is_not(None))
                    .order_by(desc(MediaItem.updated_at))
                )
            )
            .scalars()
            .all()
        )
        error_log = list(dict.fromkeys([e for e in error_rows if e]))[:10]
        # Warnings (files with missing metadata but not error)
        warning_rows = (
            (
                await self.db.execute(
                    select(MediaItem.execution_log)
                    .where(MediaItem.state != "error")
                    .where(MediaItem.execution_log.contains("missing metadata"))
                )
            )
            .scalars()
            .all()
        )
        warnings = list(dict.fromkeys([w for w in warning_rows if w]))
        # Storage impact (sum of file sizes if available)
        size_rows = (
            await self.db.execute(
                select(func.sum(MediaItem.size)).where(MediaItem.size.is_not(None))
            )
        ).first()
        storage_bytes = size_rows[0] or 0
        return SystemSummary(
            total=total,
            by_state=by_state,
            by_media_type=by_media_type,
            validated_success_rate=validated_success_rate,
            error_log=error_log,
            warnings=warnings,
            storage_bytes=storage_bytes,
        )

    async def log_daily_digest(self):
        summary = await self.get_summary()
        self.logger.info(f"Daily Digest: {summary.json(indent=2)}")
