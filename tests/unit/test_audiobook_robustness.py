"""G7 review: mixed-format merge, part gaps, chapter bounds, R-PIPE-4 classification."""

import json
import shutil
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


# ---- P2 minors ------------------------------------------------------------
def test_multi_file_cue_yields_no_chapters():
    from app.media.audiobook import parse_cue

    cue = 'FILE "a.mp3" MP3\n TRACK 01 AUDIO\n  INDEX 01 00:00:00\nFILE "b.mp3" MP3\n TRACK 02 AUDIO\n  INDEX 01 00:00:00\n'
    assert parse_cue(cue, 100.0) == []


def test_newline_in_a_name_goes_through_the_concat_filter():
    from app.media.audiobook import has_newline

    assert has_newline(["/a/ok.mp3", "/a/bad\nname.mp3"])
    assert not has_newline(["/a/ok.mp3"])
    args, n, _ = concat_inputs({"files": ["/a/x\ny.mp3"], "mixed": True}, "/l.txt")
    assert "-filter_complex" in args and n == 1


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_tag_m4b_keeps_a_png_cover_as_png(tmp_path):
    from mutagen.mp4 import MP4, MP4Cover

    from app.media.audiobook import tag_m4b
    from tests.pipeline_helpers import _ffmpeg

    m4b = tmp_path / "b.m4b"
    _ffmpeg(
        "-f", "lavfi", "-i", "sine=duration=1", "-c:a", "aac", "-f", "ipod", str(m4b)
    )
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 20
    tag_m4b(m4b, {"title": "T", "author": "A"}, png)
    assert MP4(m4b)["covr"][0].imageformat == MP4Cover.FORMAT_PNG


def test_audio_args_re_encodes_he_aac_instead_of_copying():
    from app.media.audiobook import audio_args

    he = {
        "codec_name": "aac",
        "profile": "HE-AAC",
        "sample_rate": "44100",
        "channels": 2,
    }
    assert audio_args([he])[:3] == ["-vn", "-c:a", "aac"]
    lc = {**he, "profile": "LC"}
    assert audio_args([lc]) == ["-vn", "-c:a", "copy"]


@pytest.mark.asyncio
async def test_a_zero_expected_duration_fails_instead_of_using_the_source():
    ok = AsyncMock(return_value=(0, "", ""))
    with (
        patch("app.core.verify.run_tool", ok),
        patch("app.core.verify.probe_duration", AsyncMock(side_effect=[5.0])),
        patch("app.core.verify.sha256_file", return_value="x"),
    ):
        checks, _, reason = await verify.verify_output("/s", "/o", True, 0.0, None)
    assert reason == "duration_mismatch"
    assert any(c["name"] == "duration" and not c["passed"] for c in checks)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_series_atoms_round_trip_for_audiobookshelf(tmp_path):
    from mutagen.mp4 import MP4

    from app.media.audiobook import FREEFORM, tag_m4b
    from tests.pipeline_helpers import _ffmpeg

    m4b = tmp_path / "b.m4b"
    _ffmpeg(
        "-f", "lavfi", "-i", "sine=duration=1", "-c:a", "aac", "-f", "ipod", str(m4b)
    )
    book = {"title": "T", "author": "A", "series": "Saga", "sequence": "3"}
    tag_m4b(m4b, book, None)
    got = MP4(m4b)
    assert bytes(got[FREEFORM + "SERIES"][0]) == b"Saga"
    assert bytes(got[FREEFORM + "SERIES-PART"][0]) == b"3"


@pytest.mark.asyncio
async def test_a_follower_of_a_failed_lead_is_quarantined_as_book_failed(tmp_path):
    from types import SimpleNamespace

    from app.pipeline.types.audiobook import AudiobookStrategy

    cfg = make_config(tmp_path)
    engine, factory = await make_session_factory(tmp_path)
    folder = cfg.input_dir / "Book"
    folder.mkdir()
    async with factory() as s:
        for name, state in (
            ("01.mp3", FileState.error),
            ("02.mp3", FileState.enriched),
        ):
            (folder / name).write_bytes(name.encode())
            s.add(
                MediaItem(
                    id=name,
                    source_path=str(folder / name),
                    state=state,
                    media_type=MediaType.audiobook,
                )
            )
        await s.commit()
        follower = await s.get(MediaItem, "02.mp3")
        done, _ = await AudiobookStrategy().prepare_plan(
            SimpleNamespace(cfg=cfg), s, follower
        )
    assert done is True
    assert follower.state == FileState.quarantined
    assert follower.error_log == "book_failed: 01.mp3"
    await engine.dispose()
