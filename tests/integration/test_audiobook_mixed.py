"""G7 review: files of different codec/sample rate/channels merge to one M4B of the right length."""

import json
import subprocess

import pytest

from app.core.tools import run_tool
from app.media.audiobook import concat_inputs, describe_book, ffmetadata

pytestmark = pytest.mark.asyncio


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", *args], check=True)


def duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout  # fmt: skip
    return float(json.loads(out)["format"]["duration"])


async def test_mixed_mp3_and_m4a_merge_without_speed_or_length_errors(tmp_path):
    a, b = tmp_path / "01.mp3", tmp_path / "02.m4a"
    ffmpeg(
        *("-f", "lavfi", "-i", "sine=frequency=440:duration=3:sample_rate=44100"),
        "-ac",
        "1",
        str(a),
    )
    ffmpeg(
        *("-f", "lavfi", "-i", "sine=frequency=330:duration=3:sample_rate=22050"),
        "-ac",
        "2",
        "-c:a",
        "aac",
        str(b),
    )

    book = await describe_book([a, b], "Mixed")
    assert book["mixed"] is True

    listing, chapters, out = (
        tmp_path / "files.txt",
        tmp_path / "c.ffmeta",
        tmp_path / "out.m4b",
    )
    chapters.write_text(ffmetadata(book["chapters"]))
    inputs, n, audio_map = concat_inputs(book, str(listing))
    rc, _, err = await run_tool(
        [
            *("ffmpeg", "-nostdin", "-y", "-v", "error", *inputs),
            *("-i", str(chapters), *audio_map, "-map_metadata", str(n)),
            *("-map_chapters", str(n), *book["ffmpeg_args"]),
            *("-f", "ipod", str(out)),
        ],
        120,
    )  # fmt: skip
    assert rc == 0, err
    assert abs(duration(out) - book["duration"]) < 0.5
