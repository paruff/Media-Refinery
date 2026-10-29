"""Ebooks: DRM gate, Calibre metadata/duplicates, EPUB conversion, calibredb publish."""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

from app.core.publish import quarantine_file
from app.core.verify import verify_ebook
from app.media import ebook
from app.models.media import FileState, MediaType
from app.pipeline.types.base import MediaStrategy, flag_review, load_meta


class EbookStrategy(MediaStrategy):
    healthcheck = False

    async def classify(self, o, session, item) -> None:
        """R-EBOOK-4 DRM -> quarantine/drm, never processed; R-EBOOK-2 metadata."""
        source = Path(str(item.source_path))
        item.media_type = MediaType.ebook
        if drm := await asyncio.to_thread(ebook.detect_drm, source):
            await asyncio.to_thread(
                quarantine_file, source, o.cfg.quarantine_dir, "drm", str(item.id)
            )
            item.state, item.error_log = FileState.quarantined, f"drm: {drm}"
            o._emit("quarantine", item.id, "success", "drm")
            await session.commit()
            return
        meta = await ebook.read_meta(source)
        if o.cfg.ebook_fetch:
            fetched = await ebook.fetch_meta(meta)
            o._emit("enrich", item.id, "success" if fetched else "skipped")
            meta = ebook.merge_meta(meta, fetched)  # embedded values win
        ext = source.suffix.lstrip(".").lower()
        if ebook.is_untitled(meta.get("title")) or (
            ext == "epub" and await asyncio.to_thread(ebook.epub_lacks_title, source)
        ):  # the file name is the best clue left
            meta["title"] = ebook.placeholder_title(source)
            meta["placeholder_title"] = True
        meta["authors"] = meta.get("authors") or ["Unknown"]
        meta["format"], meta["convert"] = "epub" if ext != "pdf" else ext, ext != "epub"
        item.enrichment_data = json.dumps({"ebook": meta})
        item.state = FileState.enriched
        await session.commit()

    async def prepare_plan(self, o, session, item) -> tuple[bool | None, str]:
        """R-PIPE-7: a book already in Calibre is a plan decision: approve keeps both,
        reject skips."""
        meta = load_meta(item)
        dup = await ebook.find_duplicate(o.cfg.ebooks_root, meta.get("ebook", {}))
        if dup is not None:
            meta["ebook"].update(allow_duplicate=True, duplicate_of=dup)
            item.enrichment_data = json.dumps(meta)
            flag_review(item, "duplicate_ebook")
        return None, ""

    async def build(self, o, item, plan, source: Path, tmp: Path):
        """R-EBOOK-1: EPUB 3 via ebook-convert; scanned-image PDFs stay PDF and are flagged."""
        cover = tmp.with_name("cover.jpg")
        if not await ebook.extract_cover(source, cover) and o.cfg.ebook_fetch:
            await ebook.fetch_meta(load_meta(item).get("ebook", {}), cover)
        meta = load_meta(item).get("ebook", {})
        retitle = {"title": meta["title"]} if meta.get("placeholder_title") else None
        rc, err = await ebook.to_epub(source, tmp, retitle)
        out = tmp
        if (
            rc == 0
            and source.suffix.lower() == ".pdf"
            and (
                await asyncio.to_thread(ebook.epub_text_length, tmp)
                < ebook.MIN_PDF_TEXT
            )
        ):
            o._emit("ebook.scanned_pdf", item.id, "flagged", "kept_as_pdf")
            await asyncio.to_thread(tmp.unlink)
            out = tmp.with_suffix(".pdf")
            await asyncio.to_thread(shutil.copyfile, source, out)
        if rc == 0 and out.suffix == ".pdf":  # kept as PDF: plan follows the file
            # the item id (content hash) in the name keeps the unique target free of clashes
            target = Path(str(plan.target_path))
            plan.target_path = str(
                target.with_name(f"{target.stem} [{str(item.id)[:8]}].pdf")
            )
        return rc, err, out

    async def verify(self, o, item, plan, work: Path):
        return await verify_ebook(str(work))

    async def publish(self, o, session, item, plan, work: Path) -> bool | None:
        """R-EBOOK-3: calibredb add; Calibre owns the layout. A duplicate is skipped,
        not an error."""
        meta = json.loads(str(item.enrichment_data))["ebook"]
        cover = work.with_name("cover.jpg")
        async with o._calibre_lock:
            # two new copies of one book planned in the same pass both missed PLAN's check
            dup_id = (
                None
                if meta.get("allow_duplicate")
                else await ebook.find_duplicate(o.cfg.ebooks_root, meta)
            )
            if dup_id is not None:
                book_id, err = None, ""
            else:
                book_id, err = await ebook.calibredb_add(
                    o.cfg.ebooks_root, work, meta, cover if cover.exists() else None
                )
        if err.startswith(ebook.BUSY_PREFIX):  # held by another Calibre program
            o._emit("publish", item.id, "skipped", err)
            return False
        if err:
            await o._quarantine(session, item, "calibre_add_failed", err, work)
            return True
        if book_id:
            await ebook.set_extra_fields(o.cfg.ebooks_root, book_id, meta)
        if dup_id is not None:
            detail = f"duplicate of calibre id {dup_id}, skipped"
        else:
            detail = (
                f"calibre id {book_id}" if book_id else "duplicate skipped by calibre"
            )
        plan.execution_log = f"{plan.execution_log}\n{detail}".strip()
        item.state = FileState.published
        await session.commit()
        o._emit("publish", item.id, "success" if book_id else "skipped", detail)
        return True
