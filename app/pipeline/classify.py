"""CLASSIFY stage: decide the media type, then let its strategy enrich the item."""

from __future__ import annotations

from app.core.planning import is_audio_only
from app.core.tools import probe_duration
from app.media import ebook
from app.models.media import FileState, MediaItem, MediaType
from app.pipeline.types import strategy_for


async def _park_disabled(session, item, media_type) -> bool:
    """G16: a disabled type keeps its type but stays `scanned`, source untouched."""
    item.media_type = media_type
    await session.commit()
    return False


async def run(o, item_id) -> bool:
    from app.services.classification import ClassificationService, audiobook_by_rule

    async with o.session_factory() as session:
        item = await session.get(MediaItem, item_id)
        if ebook.is_ebook(str(item.source_path)):
            if "ebook" not in o.cfg.enabled_types:
                return await _park_disabled(session, item, MediaType.ebook)
            await strategy_for(MediaType.ebook).classify(o, session, item)
            return True
        # stay `scanned` until enrich ran: a crash in between must redo it
        await ClassificationService(session).classify_file(  # type: ignore[arg-type]
            item_id, state=FileState.scanned.value
        )
        await session.refresh(item)
        if item.media_type == MediaType.unknown:  # R-PIPE-4: audio ⇒ music, else movie
            item.media_type = (
                MediaType.music if is_audio_only(item) else MediaType.movie
            )
        if item.media_type == MediaType.music and audiobook_by_rule(
            str(item.source_path),
            await probe_duration(str(item.source_path)),
            o.cfg.input_dir,
        ):
            item.media_type = MediaType.audiobook  # R-PIPE-4
        if MediaType(item.media_type).value not in o.cfg.enabled_types:
            return await _park_disabled(session, item, item.media_type)
        await strategy_for(item.media_type).enrich(o, item)
        item.state = FileState.enriched
        await session.commit()
    return True
