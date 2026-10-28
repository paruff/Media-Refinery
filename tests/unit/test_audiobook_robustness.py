"""G7 review: mixed-format merge, part gaps, chapter bounds, R-PIPE-4 classification."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.core import verify
from app.core.orchestrator import PipelineOrchestrator
from app.media.audiobook import concat_inputs, part_gaps
from app.models.media import FileState, MediaItem, MediaType
from app.pipeline import classify
from app.services.classification import audiobook_by_rule
from tests.pipeline_helpers import make_config, make_session_factory

pytestmark = pytest.mark.unit


# ---- mixed inputs ---------------------------------------------------------
def test_uniform_book_uses_the_concat_demuxer():
    book = {"files": ["/a.mp3", "/b.mp3"], "mixed": False}
    args, n, maps = concat_inputs(book, "/w/files.txt")
    assert args == ["-f", "concat", "-safe", "0", "-i", "/w/files.txt"]
    assert n == 1 and maps == ["-map", "0:a"]


def test_mixed_book_uses_the_concat_filter_with_a_common_format():
    book = {
        "files": ["/a.mp3", "/b.m4a", "/c.mp3"],
        "mixed": True,
        "sample_rate": 22050,
        "channels": 1,
    }
    args, n, maps = concat_inputs(book, "/w/files.txt")
    assert args.count("-i") == 3 and n == 3
    graph = args[args.index("-filter_complex") + 1]
    assert graph.count("aresample=22050") == 3 and "channel_layouts=mono" in graph
    assert "concat=n=3:v=0:a=1[out]" in graph
    assert maps == ["-map", "[out]"]


# ---- part gaps ------------------------------------------------------------
@pytest.mark.parametrize(
    "files,gaps",
    [
        (["/b/01.mp3", "/b/02.mp3", "/b/03.mp3"], False),
        (["/b/01.mp3", "/b/02.mp3", "/b/04.mp3"], True),
        (["/b/Part 1.mp3", "/b/Part 2.mp3"], False),
        (["/b/CD1/01.mp3", "/b/CD1/02.mp3", "/b/CD2/01.mp3", "/b/CD2/02.mp3"], False),
        (["/b/CD1/01.mp3", "/b/CD1/03.mp3", "/b/CD2/01.mp3"], True),
        (["/b/intro.mp3", "/b/story.mp3"], False),  # unnumbered: nothing to check
        (["/b/book.m4b"], False),
    ],
)
def test_part_gaps(files, gaps):
    assert part_gaps([Path(f) for f in files]) is gaps


# ---- chapter bounds -------------------------------------------------------
def probe(chapters, duration):
    return json.dumps(
        {
            "format": {"duration": str(duration)},
            "chapters": [
                {"start_time": str(s), "end_time": str(e)} for s, e in chapters
            ],
        }
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "chapters,duration,ok",
    [
        ([(0, 60), (60, 120)], 120.0, True),
        ([(0, 60), (60, 120.4)], 120.0, True),  # within tolerance
        ([(0, 60), (60, 400)], 120.0, False),  # ends past the audio
        ([(0, 60), (50, 120)], 120.0, False),  # overlap / not monotonic
        ([(60, 120), (0, 60)], 120.0, False),
    ],
)
async def test_chapter_check_validates_order_and_bounds(chapters, duration, ok):
    run = AsyncMock(return_value=(0, probe(chapters, duration), ""))
    with patch("app.core.verify.run_tool", run):
        check = await verify._chapter_check("/o.m4b", len(chapters))
    assert check.passed is ok


# ---- R-PIPE-4 classification ---------------------------------------------
@pytest.mark.parametrize(
    "path,duration,expected",
    [
        ("/in/Audiobooks/Some Book/01.mp3", 120, True),
        ("/in/audiobook/x.mp3", 10, True),
        ("/in/Album/01.mp3", 3600, True),
        ("/in/Album/01.mp3", 3599, False),
        ("/in/Album/01.mp3", None, False),
        (
            "/in/Music/Audiobooks Greatest Hits/01.mp3",
            200,
            False,
        ),  # folder name must match exactly
    ],
)
def test_audiobook_by_rule(path, duration, expected):
    assert audiobook_by_rule(path, duration) is expected


@pytest.mark.asyncio
async def test_long_untagged_audio_is_classified_as_an_audiobook(tmp_path):
    cfg = make_config(tmp_path)
    engine, factory = await make_session_factory(tmp_path)
    src = cfg.input_dir / "long.mp3"
    src.write_bytes(b"x")
    async with factory() as s:
        s.add(
            MediaItem(
                id="i", source_path=str(src), state=FileState.scanned, audio_codec="mp3"
            )
        )
        await s.commit()
    orch = PipelineOrchestrator(factory, cfg)
    with patch("app.pipeline.classify.probe_duration", AsyncMock(return_value=7200.0)):
        await classify.run(orch, "i")
    async with factory() as s:
        assert (await s.get(MediaItem, "i")).media_type == MediaType.audiobook
    await engine.dispose()
