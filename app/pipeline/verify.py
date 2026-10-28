"""VERIFY stage: the type's checks on the work file, recorded before anything publishes."""

from __future__ import annotations

from pathlib import Path

from app.models.media import FileState, MediaItem, PlanStatus, VerificationRecord
from app.pipeline.types import strategy_for


async def run(o, item_id) -> bool:
    async with o.session_factory() as session:
        item = await session.get(MediaItem, item_id)
        plan = await o._plan(session, item_id)
        work = o._work(item_id, Path(str(plan.target_path)).suffix)
        if not work.exists():  # lost between stages: redo the conversion
            item.state, plan.plan_status = FileState.approved, PlanStatus.approved
            await session.commit()
            return True
        checks, digest, reason = await strategy_for(item.media_type).verify(
            o, item, plan, work
        )
        session.add(
            VerificationRecord(
                media_item_id=item_id,
                passed=reason is None,
                checks=checks,
                output_sha256=digest,
            )
        )
        o._emit("verify", item_id, "failed" if reason else "passed", reason or "")
        if reason:
            detail = "; ".join(
                f"{c['name']}: {c['detail']}" for c in checks if not c["passed"]
            )
            await o._quarantine(session, item, reason, detail, work)
        else:
            item.state = FileState.verified
            await session.commit()
    return True
