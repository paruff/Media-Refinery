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
    """Streams of a video; raises ValueError when ffprobe cannot read it (never the unchecked path)."""
    rc, out, err = await run_tool(
        ["ffprobe", "-v", "error", "-show_streams", "-of", "json", source], 120
    )
    try:
        streams = json.loads(out).get("streams", []) if rc == 0 else []
    except ValueError:
        streams = []
    if not streams:
        raise ValueError(f"ffprobe failed: {(err or 'no streams').strip()[:200]}")
    return streams


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
        try:
            streams = (
                []
                if is_audio_only(item)
                else await _probe_streams(str(item.source_path))
            )
        except ValueError as e:
            item.state, item.error_log = FileState.error, str(e)
            await session.commit()
            return True
        if any(s.get("codec_name") in IMAGE_SUBS for s in streams):
            o._emit("subtitle.image", item_id, "flagged", "kept_as_is")
        try:
            spec = build_plan(item, o.cfg.roots, streams)
        except ValueError as e:
            item.state, item.error_log = FileState.error, str(e)
            await session.commit()
            return True
        async with o.plan_lock:  # check + insert must be atomic across concurrent items
            await _claim_target(session, item, spec, review)
    return True


async def _quarantine_conflict(session, item, target_path: str) -> None:
    item.state, item.error_log = FileState.quarantined, f"plan_conflict: {target_path}"
    await session.commit()


async def _replan(session, item, spec, review) -> bool:
    """An item has at most one plan (media_item_id is unique): refresh a draft or failed one in place (#189)."""
    mine = (
        await session.execute(
            select(NormalizationPlan).where(NormalizationPlan.media_item_id == item.id)
        )
    ).scalar_one_or_none()
    if mine is None:
        return False
    if mine.plan_status not in (PlanStatus.draft, PlanStatus.failed):
        # approved/executing/completed: not ours to rewrite
        item.state = FileState.quarantined
        item.error_log = "plan_exists: item already has a plan past draft"
        await session.commit()
        return True
    others = [p for p in await _held(session, spec.target_path) if p.id != mine.id]
    if any(p.plan_status != PlanStatus.failed for p in others):
        return False  # another item holds the new target: normal conflict path
    mine.target_path, mine.ffmpeg_args = spec.target_path, spec.ffmpeg_args
    mine.needs_transcode, mine.execution_log = spec.needs_transcode, review
    mine.plan_status = PlanStatus.draft
    item.state = FileState.planned
    await session.commit()
    return True


async def _claim_target(session, item, spec, review) -> None:
    """Plan the item at spec.target_path, or quarantine it as plan_conflict."""
    if await _replan(session, item, spec, review):
        return
    held = await _held(session, spec.target_path)
    if item.media_type == MediaType.music and any(
        p.plan_status != PlanStatus.failed and p.media_item_id != item.id for p in held
    ):
        # untagged same-title tracks share a name: keep both, tell them apart by content id
        target = Path(spec.target_path)
        spec = replace(
            spec,
            target_path=str(
                target.with_name(f"{target.stem} [{str(item.id)[:8]}]{target.suffix}")
            ),
        )
        held = await _held(session, spec.target_path)
    # a failed plan keeps its history but releases the target (unique)
    for old in held:
        if old.plan_status == PlanStatus.failed:
            old.target_path = f"{old.target_path}#failed-{old.id}"
    await session.flush()
    if any(p.plan_status != PlanStatus.failed for p in held):
        await _quarantine_conflict(session, item, spec.target_path)
        return
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
    item_id = item.id  # rollback expires `item`; reading it afterwards would lazy-load
    try:
        await session.commit()
    except IntegrityError as e:  # backstop: another process claimed the target
        if "target_path" not in str(e.orig):  # only that constraint is a conflict
            raise
        await session.rollback()
        item = await session.get(MediaItem, item_id, populate_existing=True)
        await _quarantine_conflict(session, item, spec.target_path)
