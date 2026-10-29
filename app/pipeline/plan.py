"""PLAN stage: type-specific preparation, then the shared target/ffmpeg plan."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.planning import IMAGE_SUBS, build_plan, is_audio_only
from app.core.tools import run_tool
from app.models.media import (
    FileState,
    MediaItem,
    MediaType,
    NormalizationPlan,
    PlanStatus,
)
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


async def _held(session, target_path: str) -> list:
    clash = await session.execute(
        select(NormalizationPlan).where(NormalizationPlan.target_path == target_path)
    )
    return list(clash.scalars().all())


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
        held = await _held(session, spec.target_path)
        if item.media_type == MediaType.music and any(
            p.plan_status != PlanStatus.failed and p.media_item_id != item.id
            for p in held
        ):
            # untagged same-title tracks share a name: keep both, tell them apart by content id
            target = Path(spec.target_path)
            spec = replace(
                spec,
                target_path=str(
                    target.with_name(
                        f"{target.stem} [{str(item.id)[:8]}]{target.suffix}"
                    )
                ),
            )
            held = await _held(session, spec.target_path)
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
        try:
            await session.commit()
        except IntegrityError:
            # a concurrent worker took the target between our check and insert
            await session.rollback()
            item = await session.get(MediaItem, item_id, populate_existing=True)
            item.state, item.error_log = (
                FileState.quarantined,
                f"plan_conflict: {spec.target_path}",
            )
            await session.commit()
    return True
