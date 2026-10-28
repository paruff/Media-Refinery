"""G8 review: missing Calibre tools, busy library, duplicates (R-PIPE-7), metadata precedence."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.core.orchestrator import PipelineOrchestrator
from app.media import ebook
from app.models.media import (
    FileState,
    MediaItem,
    MediaType,
    NormalizationPlan,
)
from app.pipeline import plan as plan_stage
from app.pipeline.types.ebook import EbookStrategy
from tests.pipeline_helpers import make_config, make_session_factory

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]
BUSY = "Another calibre program that can modify the library is running"


async def nosleep(_):
    return None


# ---- run_tool -------------------------------------------------------------
async def test_fetch_meta_is_non_fatal_when_calibre_is_missing():
    with patch(
        "app.media.ebook.run_tool", AsyncMock(return_value=(127, "", "not found"))
    ):
        assert await ebook.fetch_meta({"title": "Dune"}) == {}


# ---- busy library ---------------------------------------------------------
async def test_calibredb_add_retries_while_the_library_is_busy():
    run = AsyncMock(
        side_effect=[(1, "", BUSY), (1, "", BUSY), (0, "Added book ids: 5", "")]
    )
    with patch("app.media.ebook.run_tool", run):
        book_id, err = await ebook.calibredb_add(
            Path("/lib"), Path("/b.epub"), {}, None, sleep=nosleep
        )
    assert (book_id, err) == (5, "") and run.await_count == 3


async def test_calibredb_add_reports_busy_after_the_retries_run_out():
    run = AsyncMock(return_value=(1, "", BUSY))
    with patch("app.media.ebook.run_tool", run):
        book_id, err = await ebook.calibredb_add(
            Path("/lib"), Path("/b.epub"), {}, None, sleep=nosleep
        )
    assert book_id is None and err.startswith(ebook.BUSY_PREFIX)


async def test_real_add_failure_is_not_retried():
    run = AsyncMock(return_value=(1, "", "Invalid epub"))
    with patch("app.media.ebook.run_tool", run):
        _, err = await ebook.calibredb_add(
            Path("/lib"), Path("/b.epub"), {}, None, sleep=nosleep
        )
    assert run.await_count == 1 and not err.startswith(ebook.BUSY_PREFIX)


async def _env(tmp_path, meta=None):
    cfg = make_config(tmp_path)
    engine, factory = await make_session_factory(tmp_path)
    meta = meta or {
        "title": "Dune",
        "authors": ["Frank Herbert"],
        "format": "epub",
        "convert": False,
    }
    async with factory() as s:
        s.add(MediaItem(id="b", source_path=str(cfg.input_dir / "dune.epub"), state=FileState.verified,
                        media_type=MediaType.ebook, enrichment_data=json.dumps({"ebook": meta})))  # fmt: skip
        s.add(NormalizationPlan(media_item_id="b", target_path=str(cfg.ebooks_root / "x.epub"), original_hash="b", ffmpeg_args=[]))  # fmt: skip
        await s.commit()
    return cfg, factory, engine


async def test_busy_library_leaves_the_item_for_a_later_pass_instead_of_quarantining(
    tmp_path,
):
    cfg, factory, engine = await _env(tmp_path)
    orch = PipelineOrchestrator(factory, cfg)
    work = tmp_path / "work.epub"
    work.write_bytes(b"x")
    with patch(
        "app.media.ebook.calibredb_add",
        AsyncMock(return_value=(None, f"{ebook.BUSY_PREFIX} {BUSY}")),
    ):
        async with factory() as s:
            item = await s.get(MediaItem, "b")
            plan = (
                await s.execute(__import__("sqlalchemy").select(NormalizationPlan))
            ).scalar_one()
            assert await EbookStrategy().publish(orch, s, item, plan, work) is False
            assert item.state == FileState.verified
    await engine.dispose()


# ---- duplicates (R-PIPE-7) ------------------------------------------------
async def test_find_duplicate_by_isbn_then_title_author():
    run = AsyncMock(return_value=(0, json.dumps([{"id": 7}]), ""))
    with patch("app.media.ebook.run_tool", run):
        assert (
            await ebook.find_duplicate(
                Path("/lib"), {"isbn": "9780441172719", "title": "Dune"}
            )
            == 7
        )
    args = run.await_args.args[0]
    assert "--for-machine" in args and "identifier:isbn:9780441172719" in args

    run = AsyncMock(return_value=(0, json.dumps([{"id": 9}]), ""))
    with patch("app.media.ebook.run_tool", run):
        assert (
            await ebook.find_duplicate(
                Path("/lib"), {"title": "Dune", "authors": ["Frank Herbert"]}
            )
            == 9
        )
    assert 'title:"=Dune" and authors:"=Frank Herbert"' in run.await_args.args[0]


@pytest.mark.parametrize(
    "result",
    [(0, "[]", ""), (1, "", "boom"), (127, "", "missing"), (0, "not json", "")],
)
async def test_find_duplicate_is_none_when_nothing_found_or_calibre_fails(result):
    with patch("app.media.ebook.run_tool", AsyncMock(return_value=result)):
        assert (
            await ebook.find_duplicate(
                Path("/lib"), {"title": "Dune", "authors": ["A"]}
            )
            is None
        )


def test_allow_duplicate_adds_the_calibre_flag():
    assert "--duplicates" in ebook.add_args(
        Path("/l"), Path("/b.epub"), {"allow_duplicate": True}, None
    )
    assert "--duplicates" not in ebook.add_args(Path("/l"), Path("/b.epub"), {}, None)


async def test_duplicate_ebook_is_flagged_for_review_at_planning(tmp_path):
    cfg, factory, engine = await _env(tmp_path)
    async with factory() as s:  # back to the pre-plan state
        item = await s.get(MediaItem, "b")
        item.state = FileState.enriched
        for plan in (
            await s.execute(__import__("sqlalchemy").select(NormalizationPlan))
        ).scalars():
            await s.delete(plan)
        await s.commit()
    orch = PipelineOrchestrator(factory, cfg)
    with patch("app.media.ebook.find_duplicate", AsyncMock(return_value=7)):
        await plan_stage.run(orch, "b")
    async with factory() as s:
        item = await s.get(MediaItem, "b")
        meta = json.loads(item.enrichment_data)
        assert meta["review"] == ["duplicate_ebook"]
        assert (
            meta["ebook"]["allow_duplicate"] is True
            and meta["ebook"]["duplicate_of"] == 7
        )
        assert PipelineOrchestrator._needs_review(item)
    await engine.dispose()


# ---- metadata precedence --------------------------------------------------
def test_fetched_metadata_fills_gaps_but_never_overwrites_embedded_values():
    merged = ebook.merge_meta(
        {"title": "Dune", "isbn": "111"},
        {"title": "Dune Messiah", "isbn": "222", "publisher": "Ace"},
    )
    assert merged == {"title": "Dune", "isbn": "111", "publisher": "Ace"}
