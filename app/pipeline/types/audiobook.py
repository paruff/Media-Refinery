"""Audiobooks: one book spans many files; the lead file carries the whole book."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from app.core.planning import is_audio_only
from app.core.publish import archive_original
from app.core.tools import run_tool
from app.core.verify import verify_output
from app.media.audiobook import (
    book_dir,
    concat_inputs,
    concat_list,
    describe_book,
    ffmetadata,
    natural_key,
    tag_m4b,
)
from app.models.media import FileState, MediaItem, MediaType
from app.pipeline.types.base import MediaStrategy, flag_review, load_meta, now
from app.pipeline.types.music import album_pending
from app.services.music_id import local_cover


def _is_late(item, lead, members) -> bool:
    """True when a file turns up after its book was planned (it is not in the lead's member
    list) or built (some other file of the folder is already validated)."""
    if any(m.state == FileState.validated and m.id != item.id for m in members):
        return item.state != FileState.validated
    if lead.id == item.id:
        return False
    book = load_meta(lead).get("book")
    return book is not None and item.id not in book["members"]


class AudiobookStrategy(MediaStrategy):
    @staticmethod
    def unit(o, path) -> Path:
        return book_dir(path, o.cfg.input_dir)  # a book spans disc subfolders

    async def prepare_plan(self, o, session, item) -> tuple[bool | None, str]:
        """R-BOOK-5: the first file (natural order) carries the whole book; the rest follow it.
        Returns a stage result when this item is done for now, None to plan the book."""
        if await album_pending(o, session, item, self.unit):
            return False, ""
        unit = book_dir(str(item.source_path), o.cfg.input_dir)
        rows = await session.execute(
            select(MediaItem).where(
                MediaItem.media_type == MediaType.audiobook,
                MediaItem.source_path.startswith(str(unit)),
            )
        )
        members = sorted(
            (
                m
                for m in rows.scalars()
                if book_dir(str(m.source_path), o.cfg.input_dir) == unit
            ),
            key=lambda m: natural_key(str(m.source_path)),
        )
        lead = members[0]
        if _is_late(item, lead, members):
            # R-PIPE-6: the book was already planned or built without this file; never a new book
            item.state = FileState.quarantined
            item.error_log = f"late_part: book already built from {lead.id}"
            await session.commit()
            return True, ""
        if lead.id != item.id:
            if lead.state in (FileState.error, FileState.quarantined):
                item.state = FileState.quarantined
                item.error_log = f"book_failed: {lead.id}"
                await session.commit()
                return True, ""
            return False, ""
        meta = load_meta(item)
        files = [str(m.source_path) for m in members]
        if meta.get("book", {}).get("files") != files:  # a retry reuses the description
            meta["book"] = await describe_book([Path(f) for f in files], unit.name)
            meta["book"]["members"] = [m.id for m in members[1:]]
            item.enrichment_data = json.dumps(meta)
        if meta["book"]["gaps"]:
            flag_review(item, "missing_parts")
        if meta["book"].get("chapters_failed"):
            flag_review(item, "chapter_detection_failed")
        return None, ""

    async def build(self, o, item, plan, source: Path, tmp: Path):
        """R-BOOK-1/2/3/5: concat the files in order, embed chapters, AAC M4B, tags + cover."""
        book = json.loads(str(item.enrichment_data))["book"]
        listing, chapters = tmp.with_name("files.txt"), tmp.with_name("chapters.ffmeta")
        listing.write_text(concat_list(book["files"]))
        chapters.write_text(ffmetadata(book["chapters"]))
        inputs, n, audio_map = concat_inputs(book, str(listing))
        rc, _, err = await run_tool(
            [
                *("ffmpeg", "-nostdin", "-y", "-v", "error", *inputs),
                *("-i", str(chapters), *audio_map, "-map_metadata", str(n)),
                *("-map_chapters", str(n), *(plan.ffmpeg_args or [])),
                *("-f", "ipod", str(tmp)),
            ],
            o.cfg.ffmpeg_timeout,
        )
        if rc != 0:
            return rc, err, tmp
        cover = next(
            filter(
                None, [await asyncio.to_thread(local_cover, f) for f in book["files"]]
            ),
            None,
        )
        if cover is None:
            o._emit("cover", item.id, "skipped", "no usable cover (>=500px)")
        await asyncio.to_thread(tag_m4b, tmp, book, cover)
        return 0, "", tmp

    async def verify(self, o, item, plan, work: Path):
        book = json.loads(str(item.enrichment_data))["book"]
        return await verify_output(
            str(item.source_path),
            str(work),
            is_audio_only(item),
            book["duration"],
            len(book["chapters"]),
        )

    async def after_archive(self, o, session, item) -> None:
        """The other files of a merged book are archived with the lead, never deleted."""
        book = json.loads(str(item.enrichment_data))["book"]
        for member_id in book["members"]:
            member = await session.get(MediaItem, member_id)
            await asyncio.to_thread(
                archive_original,
                Path(str(member.source_path)),
                o.cfg.input_dir,
                o.cfg.archive_dir,
                o.run_id,
            )
            member.state = FileState.validated
            member.error_log = f"merged into {item.id}"
            member.updated_at = now()
