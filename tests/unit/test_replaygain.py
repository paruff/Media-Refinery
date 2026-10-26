import pytest

from app.services import replaygain

STDERR = """[Parsed_replaygain_2 @ 0x1] track_gain = -3.94 dB
[Parsed_replaygain_2 @ 0x1] track_peak = 0.250000
"""


@pytest.mark.asyncio
async def test_measure_parses_ffmpeg_output(monkeypatch, tmp_path):
    seen = {}

    async def fake(args, limit=0):
        seen["args"] = args
        return 0, "", STDERR

    monkeypatch.setattr(replaygain, "run_tool", fake)
    assert await replaygain.measure([tmp_path / "a.flac", tmp_path / "b.flac"]) == (
        "-3.94 dB",
        "0.250000",
    )
    assert "concat=n=2" in seen["args"][seen["args"].index("-filter_complex") + 1]


@pytest.mark.asyncio
async def test_measure_is_none_when_filter_missing(monkeypatch, tmp_path):
    async def fake(args, limit=0):
        return 1, "", "No such filter: 'replaygain'"

    monkeypatch.setattr(replaygain, "run_tool", fake)
    assert await replaygain.measure([tmp_path / "a.flac"]) is None
