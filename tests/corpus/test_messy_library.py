"""G15: the full pipeline over the generated messy library. Whatever the content, no source
is lost, nothing broken reaches the library, nothing crashes, and a rerun is a no-op."""

import hashlib
from collections import Counter
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.orchestrator import PipelineOrchestrator
from app.core.tools import run_tool
from app.models.media import FileState, MediaItem
from tests.corpus.generate import messy
from tests.pipeline_helpers import import_input, make_config, make_session_factory

pytestmark = [pytest.mark.corpus, pytest.mark.integration, pytest.mark.asyncio]


def _digests(root: Path) -> list[str]:
    return sorted(
        hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
    )


async def test_messy_library_converges_without_loss_or_junk(tmp_path):
    cfg = make_config(tmp_path)
    engine, factory = await make_session_factory(tmp_path)
    made = messy(cfg.input_dir)
    sources = _digests(cfg.input_dir)
    await import_input(cfg, factory)
    orch = PipelineOrchestrator(factory, cfg)
    await orch.run_until_idle()
    async with factory() as s:
        planned = (
            (
                await s.execute(
                    select(MediaItem.id).where(MediaItem.state == FileState.planned)
                )
            )
            .scalars()
            .all()
        )
    for item_id in planned:
        await orch.approve(str(item_id))
    await orch.run_until_idle()

    async with factory() as s:
        items = (await s.execute(select(MediaItem))).scalars().all()
    by_name = {Path(str(i.source_path)).name: i for i in items}
    # unreadable or non-media input may stop at `error` or go to quarantine, but must never
    # be processed further, and an `error` item's source stays where it was
    for i in items:
        if i.state == FileState.error:
            assert Path(str(i.source_path)).is_file(), i.source_path
    for kind in ("zero_byte", "garbage", "truncated"):
        for p in made[kind]:
            assert by_name[p.name].state in (FileState.error, FileState.quarantined), (
                p,
                by_name[p.name].state,
            )

    # nothing lost: every source byte-for-byte in input, archive or quarantine (quarantine
    # may also hold rejected outputs, so extras are fine; missing sources are not)
    kept = (
        _digests(cfg.input_dir)
        + _digests(cfg.archive_dir)
        + _digests(cfg.quarantine_dir)
    )
    assert not Counter(sources) - Counter(kept), "a source file was lost or modified"

    # nothing broken published: every library file decodes
    for f in [
        p
        for r in (cfg.music_root, cfg.movies_root)
        for p in r.rglob("*")
        if p.is_file()
    ]:
        if f.suffix in (".mp3", ".flac", ".mkv"):
            rc, _, err = await run_tool(
                ["ffmpeg", "-nostdin", "-v", "error", "-i", str(f), "-f", "null", "-"],
                60,
            )
            assert rc == 0 and not err.strip(), (f, err)
    assert not list(cfg.music_root.rglob(".*.tmp"))

    # a rerun changes nothing
    before = _digests(cfg.music_root) + _digests(cfg.movies_root)
    await import_input(cfg, factory)
    await PipelineOrchestrator(factory, cfg).run_until_idle()
    assert _digests(cfg.music_root) + _digests(cfg.movies_root) == before
    await engine.dispose()
