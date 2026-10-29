"""P1: the pipeline over a generated messy ebook library with real Calibre. Whatever the input,
no source is lost, nothing broken reaches the Calibre library, a duplicate is held for review,
and re-ingesting an already-added book is a no-op."""

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.orchestrator import PipelineOrchestrator
from app.models.media import FileState, MediaItem
from tests.ebook_helpers import (
    make_azw3,
    make_bare_epub,
    make_corrupt_epub,
    make_drm_azw3,
    make_drm_epub,
    make_epub,
    make_isbn_epub,
    make_mobi,
    make_scanned_pdf,
    make_text_pdf,
)
from tests.pipeline_helpers import import_input, make_config, make_session_factory

pytestmark = [pytest.mark.corpus, pytest.mark.integration, pytest.mark.asyncio]
NEEDS_CALIBRE = ("calibredb", "ebook-convert", "ebook-meta")
ISBN = "9780441172719"


def messy_ebooks(root: Path) -> dict[str, Path]:
    root.mkdir(parents=True, exist_ok=True)
    return {
        "epub": make_epub(root / "plain.epub", "Plain Book", "Plain Author"),
        "amp": make_epub(root / "amp.epub", "Q & A: Tom & Jerry", "Barnes & Noble"),
        "unicode": make_epub(
            root / "uni.epub", "Zażółć gęślą jaźń 日本語", "Björk Guðmundsdóttir"
        ),
        "bare": make_bare_epub(root / "bare.epub"),
        "pdf": make_text_pdf(root / "text.pdf"),
        "scanned": make_scanned_pdf(root / "scan.pdf"),
        "mobi": make_mobi(root / "old.mobi", "Old Mobi", "Mobi Author"),
        "azw3": make_azw3(root / "kindle.azw3", "Kindle Book", "Kindle Author"),
        "drm_azw3": make_drm_azw3(
            root / "locked.azw3", "Locked Kindle", "Locked Author"
        ),
        "drm_epub": make_drm_epub(root / "locked.epub", "Locked Epub", "Locked Author"),
        "corrupt": make_corrupt_epub(root / "broken.epub"),
        "isbn_a": make_isbn_epub(root / "dune-1.epub", "Dune", "Frank Herbert", ISBN),
        "isbn_b": make_isbn_epub(
            root / "dune-2.epub", "Dune (copy)", "F. Herbert", ISBN
        ),
    }


def calibre_major() -> int:
    """Calibre 7.6 (Ubuntu 24.04 apt) turns an AZW3 into an EPUB with a colon in an `id`, which
    epubcheck rejects; 8.x (the image) does not. 0 when the version cannot be read."""
    out = subprocess.run(
        ["ebook-convert", "--version"], capture_output=True, text=True
    ).stdout
    found = re.search(r"calibre (\d+)\.", out)
    return int(found.group(1)) if found else 0


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def library(cfg) -> list[dict]:
    if not (cfg.ebooks_root / "metadata.db").exists():
        return []
    out = subprocess.run(
        ["calibredb", "list", "--for-machine", "--with-library", str(cfg.ebooks_root),
         "--fields", "title,authors,formats,identifiers"],
        capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip
    return json.loads(out)


async def drive(orch, factory) -> None:
    await orch.run_until_idle()
    async with factory() as s:
        planned = (
            await s.execute(select(MediaItem.id).where(MediaItem.state == FileState.planned))
        ).scalars().all()  # fmt: skip
    for item_id in planned:
        await orch.approve(str(item_id))
    await orch.run_until_idle()


async def _by_name(factory) -> dict[str, MediaItem]:
    async with factory() as s:
        return {
            Path(str(i.source_path)).name: i
            for i in (await s.execute(select(MediaItem))).scalars()
        }


def _copies(cfg, sha: str) -> int:
    held = [
        _sha(p)
        for root in (cfg.input_dir, cfg.archive_dir, cfg.quarantine_dir)
        if root.exists()
        for p in root.rglob("*")
        if p.is_file()
    ]
    return held.count(sha)


def _snapshot(cfg) -> list:
    return sorted((b["title"], str(b["formats"])) for b in library(cfg))


async def test_messy_ebook_library_converges_without_loss_or_junk(
    tmp_path, monkeypatch
):
    missing = [t for t in NEEDS_CALIBRE if not shutil.which(t)]
    if missing:
        pytest.skip(f"{missing} not installed (Calibre CLI)")
    monkeypatch.setenv(
        "QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox"
    )  # tests run as root
    cfg = make_config(
        tmp_path, auto_approve_types=frozenset({"ebook"}), ebook_fetch=False
    )
    engine, factory = await make_session_factory(tmp_path)
    made = messy_ebooks(tmp_path / "pristine")  # the pipeline moves what it ingests
    sources = {k: _sha(p) for k, p in made.items()}
    shutil.copytree(tmp_path / "pristine", cfg.input_dir, dirs_exist_ok=True)
    await import_input(cfg, factory)
    orch = PipelineOrchestrator(factory, cfg)
    await drive(orch, factory)
    items, books = await _by_name(factory), library(cfg)
    titles = {b["title"]: b for b in books}

    # no source is lost: held in input, archive or quarantine (a book whose verified copy is
    # quarantined may also still sit in input)
    assert [k for k, sha in sources.items() if _copies(cfg, sha) < 1] == []
    # DRM (EPUB ADEPT and a DRM'd AZW3) is quarantined, never converted or added
    for key in ("drm_azw3", "drm_epub"):
        item = items[made[key].name]
        assert item.state == FileState.quarantined and "drm" in str(item.error_log), key
    assert not {"Locked Kindle", "Locked Epub"} & set(titles)
    # a corrupt zip stops short of the library
    assert items[made["corrupt"].name].state in (FileState.error, FileState.quarantined)
    # & and unicode titles, and missing metadata, come through intact
    assert titles["Q & A: Tom & Jerry"]["authors"] == "Barnes & Noble"
    assert titles["Zażółć gęślą jaźń 日本語"]["authors"] == "Björk Guðmundsdóttir"
    # an EPUB with no title is rewritten under its file name and passes epubcheck
    assert "bare" in titles and titles["bare"]["authors"] == "Unknown"
    # a PDF with no metadata still lands, under whatever title Calibre or the file name gives
    assert len([b for b in books if "text" in b["title"].lower()]) == 1, titles
    # every format converts to EPUB (a scanned PDF may stay PDF)
    assert {"Plain Book", "Old Mobi"} <= set(titles)
    kindle = items[made["azw3"].name]
    if calibre_major() >= 8:
        assert "Kindle Book" in titles
    else:  # an old Calibre's bad output is held by epubcheck, never added
        assert "Kindle Book" in titles or (
            kindle.state == FileState.quarantined
            and "epubcheck_failed" in str(kindle.error_log)
        )
    assert {Path(f).suffix for b in books for f in b["formats"]} <= {".epub", ".pdf"}
    # a duplicate ISBN is not added twice
    assert len([b for b in books if "isbn" in str(b.get("identifiers", ""))]) == 1, (
        books
    )

    # idempotence: the same files dropped again change nothing
    before, states = _snapshot(cfg), {k: v.state for k, v in items.items()}
    shutil.copytree(tmp_path / "pristine", cfg.input_dir, dirs_exist_ok=True)
    await import_input(cfg, factory)
    await drive(orch, factory)
    assert _snapshot(cfg) == before
    assert {k: v.state for k, v in (await _by_name(factory)).items()} == states
    await engine.dispose()
