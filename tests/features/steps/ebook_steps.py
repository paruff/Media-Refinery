import asyncio
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from behave import given, then  # type: ignore[import-untyped]

from app.core.orchestrator import PipelineOrchestrator
from tests.ebook_helpers import make_drm_epub, make_epub, make_mobi
from tests.pipeline_helpers import import_input, make_config, make_session_factory

TOOLS = ("ffprobe", "calibredb", "ebook-convert", "ebook-meta")


def _run(context, coro):
    return context.spine_loop.run_until_complete(coro)


@given("an ebook workspace")
def step_workspace(context):
    missing = [t for t in TOOLS if not shutil.which(t)]
    if missing:
        assert not os.environ.get("REQUIRE_CALIBRE"), f"missing {missing}"
        context.scenario.skip(f"{missing} not installed (Calibre CLI)")
        return
    tmp = tempfile.TemporaryDirectory()
    context.add_cleanup(tmp.cleanup)
    base = Path(tmp.name)
    context.spine_loop = asyncio.new_event_loop()
    context.add_cleanup(context.spine_loop.close)
    context.cfg = make_config(base, auto_approve_types=frozenset({"ebook"}))
    engine, context.factory = _run(context, make_session_factory(base))
    context.add_cleanup(lambda: _run(context, engine.dispose()))
    context.orch = PipelineOrchestrator(context.factory, context.cfg)


def _import(context):
    _run(context, import_input(context.cfg, context.factory))


@given('a generated EPUB "{title}" by "{author}"')
def step_epub(context, title, author):
    make_epub(context.cfg.input_dir / f"{title}.epub", title, author)
    _import(context)


@given('a generated MOBI "{title}" by "{author}"')
def step_mobi(context, title, author):
    make_mobi(context.cfg.input_dir / f"{title}.mobi", title, author)
    _import(context)


@given('a generated DRM EPUB "{title}" by "{author}"')
def step_drm(context, title, author):
    make_drm_epub(context.cfg.input_dir / f"{title}.epub", title, author)
    _import(context)


def _library(context) -> list[dict]:
    lib = context.cfg.ebooks_root
    if not (lib / "metadata.db").exists():
        return []
    out = subprocess.run(
        [
            "calibredb",
            "list",
            "--for-machine",
            "--with-library",
            str(lib),
            "--fields",
            "title,authors,cover,formats",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return json.loads(out)


@then('the Calibre library lists "{title}" by "{author}" with a cover')
def step_listed(context, title, author):
    books = [b for b in _library(context) if b["title"] == title]
    assert len(books) == 1, _library(context)
    assert books[0]["authors"] == author and Path(books[0]["cover"]).is_file()


@then("the library holds EPUB files only")
def step_epub_only(context):
    formats = [Path(f).suffix for b in _library(context) for f in b["formats"]]
    assert formats and set(formats) == {".epub"}, formats


@then("the originals are archived")
def step_archived(context):
    assert not [p for p in context.cfg.input_dir.rglob("*") if p.is_file()]
    assert len([p for p in context.cfg.archive_dir.rglob("*") if p.is_file()]) == 2


@then('the DRM file is in "{rel}"')
def step_drm_quarantined(context, rel):
    assert (
        len(list((context.cfg.quarantine_dir.parent / rel).glob("*Locked Book.epub")))
        == 1
    )
    assert not list(context.cfg.input_dir.glob("*.epub"))


@then("the Calibre library is empty")
def step_empty(context):
    assert _library(context) == []


@then("both EPUBs passed epubcheck")
def step_epubcheck(context):
    from sqlalchemy import select

    from app.models.media import VerificationRecord

    async def records():
        async with context.factory() as s:
            return (await s.execute(select(VerificationRecord))).scalars().all()

    found = _run(context, records())
    assert len(found) == 2
    for rec in found:
        check = next(c for c in rec.checks if c["name"] == "epubcheck")
        assert check["passed"] and "not installed" not in check["detail"], check
