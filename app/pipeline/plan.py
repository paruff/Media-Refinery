"""PLAN stage: type-specific preparation, then the shared target/ffmpeg plan."""

from __future__ import annotations

import json

from sqlalchemy import select

from app.core.planning import IMAGE_SUBS, build_plan, is_audio_only
from app.core.tools import run_tool
from app.models.media import FileState, MediaItem, NormalizationPlan, PlanStatus
from app.pipeline.types import strategy_for
from app.pipeline.types.base import load_meta


async def _probe_streams(source: str) -> list[dict]:
    rc, out, _ = await run_tool(
        ["ffprobe", "-v", "error", "-show_streams", "-of", "json", source], 120
    )
    try:
        return json.loads(out).get("streams", []) if rc == 0 else []
    except ValueError:
        return []


async def run(o, item_id) -> bool:
    async with o.session_factory() as session:
        item = await session.get(MediaItem, item_id)
        done, review = await strategy_for(item.media_type).prepare_plan(
            o, session, item
        )
        if done is not None:
            return done
        if flags := load_meta(item).get("review"):
            review = f"review_required: {', '.join(flags)}"
            o._emit("review", item_id, "degraded", review)
        streams = (
            [] if is_audio_only(item) else await _probe_streams(str(item.source_path))
        )
        if any(s.get("codec_name") in IMAGE_SUBS for s in streams):
            o._emit("subtitle.image", item_id, "flagged", "kept_as_is")
        try:
            spec = build_plan(item, o.cfg.roots, streams)
        except ValueError as e:
            item.state, item.error_log = FileState.error, str(e)
            await session.commit()
            return True
        clash = await session.execute(
            select(NormalizationPlan).where(
                NormalizationPlan.target_path == spec.target_path
            )
        )
        held = clash.scalars().all()
        # a failed plan keeps its history but releases the target (unique)
        for old in held:
            if old.plan_status == PlanStatus.failed:
                old.target_path = f"{old.target_path}#failed-{old.id}"
        await session.flush()
        if any(p.plan_status != PlanStatus.failed for p in held):
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
                # item ids are the sha256 of the content (watcher.content_hash)
                original_hash=str(item.id),
                needs_transcode=spec.needs_transcode,
                needs_rename=True,
                execution_log=review,
            )
        )
        item.state = FileState.planned
        await session.commit()
    return True
