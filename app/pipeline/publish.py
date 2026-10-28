"""PUBLISH and ARCHIVE stages: land the verified file, then move the original aside."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from sqlalchemy import select

from app.core.paths import ensure_inside
from app.core.publish import archive_original, publish_file
from app.core.verify import sha256_file
from app.models.media import FileState, MediaItem, PlanStatus, VerificationRecord
from app.pipeline.types import strategy_for
from app.pipeline.types.base import now


async def publish(o, item_id) -> bool:
    async with o.session_factory() as session:
        item = await session.get(MediaItem, item_id)
        plan = await o._plan(session, item_id)
        strategy = strategy_for(item.media_type)
        dest = ensure_inside(o.cfg.root_for(item.media_type), str(plan.target_path))
        work = o._work(item_id, dest.suffix)
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
        if (custom := await strategy.publish(o, session, item, plan, work)) is not None:
            return custom
        if dest.exists():
            if await asyncio.to_thread(sha256_file, str(dest)) != sha:
                await o._quarantine(session, item, "target_exists", str(dest), work)
                return True
            # resumed after a crash that landed the file but not the state
        elif not work.exists():
            # work file lost (cleaned up, crash): redo the conversion instead of erroring
            o.logger.warning("work file missing for %s; re-executing", item_id)
            item.state = FileState.approved
            item.updated_at = now()
            await session.commit()
            return True
        else:
            await publish_file(session, str(plan.id), work, dest, sha)
        await strategy.after_publish(o, item, dest)
        item.state = FileState.published
        await session.commit()
        o._emit("publish", item_id, "success", str(dest))
    o._notify(str(item.media_type), dest)  # non-fatal, coalesced
    return True


async def archive(o, item_id) -> bool:
    """After VERIFY passed and the file is published, move (never delete) the original."""
    async with o.session_factory() as session:
        item = await session.get(MediaItem, item_id)
        plan = await o._plan(session, item_id)
        archived = await asyncio.to_thread(
            archive_original,
            Path(str(item.source_path)),
            o.cfg.input_dir,
            o.cfg.archive_dir,
            o.run_id,
        )
        if archived:
            plan.execution_log = f"{plan.execution_log}\narchived: {archived}".strip()
        await strategy_for(item.media_type).after_archive(o, session, item)
        shutil.rmtree(o.cfg.work_dir / item_id, ignore_errors=True)
        plan.plan_status = PlanStatus.completed
        item.state = FileState.validated
        item.updated_at = now()
        await session.commit()
        o._emit("archive", item_id, "success", str(archived or ""))
    return True
