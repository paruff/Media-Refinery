"""EXECUTE stage: health-check the source, then let the type's strategy build the output."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from app.core.planning import is_audio_only
from app.media.video.health import health_check, repair_remux
from app.models.media import FileState, MediaItem, PlanStatus
from app.pipeline.types import strategy_for


async def _healthy_source(o, session, item, plan, source: Path, work: Path):
    """Remux-repair fallback, else quarantine the original. Returns the (possibly
    repaired) source, or None when the item was quarantined."""
    item_id = item.id
    healthy, detail = await asyncio.to_thread(health_check, source)
    o._emit("healthcheck", item_id, "passed" if healthy else "failed", detail)
    if detail == "healthcheck_timeout":
        # inconclusive: do not call good media corrupt; VERIFY checks the output
        o._emit("healthcheck", item_id, "inconclusive", detail)
    elif not healthy:
        repaired = await asyncio.to_thread(repair_remux, source, work.parent / "repair")
        o._emit("repair", item_id, "success" if repaired else "failed", "remux_to_mkv")
        if repaired is None:
            # bad input is not resource pressure: don't feed the throttle
            await o._quarantine(session, item, "healthcheck_failed", detail, source)
            return None
        return repaired
    return source


async def run(o, item_id) -> bool:
    if o.cfg.dry_run:
        return False
    async with o.session_factory() as session:
        item = await session.get(MediaItem, item_id)
        plan = await o._plan(session, item_id)
        strategy = strategy_for(item.media_type)
        ext = Path(str(plan.target_path)).suffix
        item.state, plan.plan_status = FileState.executing, PlanStatus.executing
        await session.commit()  # persisted before any side effect
        work = o._work(item_id, ext)
        shutil.rmtree(work.parent, ignore_errors=True)
        work.parent.mkdir(parents=True)
        tmp = work.with_name(f"out.tmp{ext}")  # ffmpeg infers the container from it
        source = Path(str(item.source_path))
        if strategy.healthcheck and not is_audio_only(item):
            source = await _healthy_source(o, session, item, plan, source, work)
            if source is None:
                return True
        o._emit("execute", item_id, "started")
        rc, err, tmp = await strategy.build(o, item, plan, source, tmp)
        plan.execution_log = f"{plan.execution_log}\nffmpeg rc={rc}\n{err}".strip()
        if rc != 0:
            tmp.unlink(missing_ok=True)
            await o._quarantine(session, item, "convert_failed", err.strip()[:500])
            o._record_execute(False, item_id)
            return True
        tmp.replace(o._work(item_id, Path(str(plan.target_path)).suffix))
        item.state = FileState.executed
        await session.commit()
        o._emit("execute", item_id, "success")
        o._record_execute(True, item_id)
    return True
