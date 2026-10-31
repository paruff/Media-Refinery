"""P3: the pipeline over a generated messy movie library with real ffmpeg. Whatever the input,
no source is lost, the output is one decodable Samsung-safe video per movie (extra audio, subtitles
and Atmos kept, cover art not re-encoded), damaged files are repaired or quarantined, and re-ingest
is a no-op."""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.orchestrator import PipelineOrchestrator
from app.models.media import FileState, MediaItem
from tests.pipeline_helpers import import_input, make_config, make_session_factory

pytestmark = [pytest.mark.corpus, pytest.mark.integration, pytest.mark.asyncio]


def ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", *args], check=True)


def video(
    path: Path,
    seconds: int,
    source: str = "testsrc",
    codec: str = "libx264",
    *extra: str,
) -> Path:
    """One distinct duration per file keeps the duplicate-fingerprint check from merging them."""
    ff(
        *("-f", "lavfi", "-t", str(seconds), "-i", f"{source}=size=160x120:rate=10"),
        *("-f", "lavfi", "-i", f"sine=frequency=330:duration={seconds}"),
        *("-c:v", codec, *extra, "-c:a", "aac", "-shortest", str(path)),
    )  # fmt: skip
    return path


def messy_movies(root: Path) -> dict[str, Path]:
    root.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}

    # two audio tracks (eng, fra) and a text subtitle, conformant video
    srt = root / "subs.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n")
    multi = root / "Multi Audio (2001).mkv"
    ff(
        *("-f", "lavfi", "-i", "testsrc=size=160x120:rate=10:duration=3"),
        *("-f", "lavfi", "-i", "sine=frequency=330:duration=3"),
        *("-f", "lavfi", "-i", "sine=frequency=550:duration=3"),
        *("-i", str(srt)),
        *("-map", "0", "-map", "1", "-map", "2", "-map", "3"),
        *("-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-c:s", "srt"),
        *("-metadata:s:a:0", "language=eng", "-metadata:s:a:1", "language=fra"),
        str(multi),
    )  # fmt: skip
    srt.unlink()
    out["multi"] = multi

    # legacy codec: forced through repair-free re-encode
    out["legacy"] = video(root / "Old Codec (2002).mkv", 4, "mandelbrot", "mpeg4")

    # 10-bit HEVC with HDR10-style colour tags: kept as Main10 (R-VIDEO-1)
    hdr = root / "Ten Bit (2003).mkv"
    ff(
        *("-f", "lavfi", "-i", "smptebars=size=160x120:rate=10:duration=5"),
        *("-c:v", "libx265", "-pix_fmt", "yuv420p10le", "-x265-params", "log-level=error"),
        *("-color_primaries", "bt2020", "-color_trc", "smpte2084", "-colorspace", "bt2020nc"),
        str(hdr),
    )  # fmt: skip
    out["hdr"] = hdr

    # Atmos: legacy video forces the converter, which must keep the Atmos E-AC3 copy
    atmos = root / "Atmos (2004).mkv"
    ff(
        *("-f", "lavfi", "-t", "6", "-i", "life=size=160x120:rate=10"),
        *("-f", "lavfi", "-i", "sine=frequency=330:duration=6"),
        *("-f", "lavfi", "-i", "sine=frequency=440:duration=6"),
        *("-map", "0", "-map", "1", "-map", "2", "-c:v", "mpeg2video", "-c:a:0", "aac", "-c:a:1", "eac3"),
        *("-metadata:s:a:1", "title=English Atmos"),
        str(atmos),
    )  # fmt: skip
    out["atmos"] = atmos

    # cover-art stream next to a legacy video stream
    cover = root / "cover.jpg"
    ff("-f", "lavfi", "-i", "color=c=red:size=64x64", "-frames:v", "1", str(cover))
    art = root / "Cover Art (2005).mp4"
    ff(
        *("-f", "lavfi", "-t", "7", "-i", "gradients=size=160x120:rate=10"),
        *("-f", "lavfi", "-i", "sine=frequency=330:duration=7"),
        *("-i", str(cover)),
        *("-map", "0", "-map", "1", "-map", "2", "-c:v:0", "mpeg4", "-c:a", "aac", "-c:v:1", "mjpeg"),
        *("-disposition:v:1", "attached_pic", str(art)),
    )  # fmt: skip
    cover.unlink()
    out["art"] = art

    # damaged: truncated mid-stream, and pure junk
    good = video(root / "tmp-good.mkv", 8, "rgbtestsrc")
    trunc = root / "Truncated (2006).mkv"
    trunc.write_bytes(good.read_bytes()[: good.stat().st_size // 2])
    good.unlink()
    out["truncated"] = trunc
    junk = root / "Corrupt (2007).mkv"
    junk.write_bytes(b"not a video" * 500)
    out["corrupt"] = junk

    # long file: the decode-scan timeout scales with duration (1 h of tiny frames)
    long = root / "Long (2008).mkv"
    ff(
        *("-f", "lavfi", "-i", "color=c=blue:size=64x64:rate=5:duration=3700"),
        *("-f", "lavfi", "-i", "sine=frequency=200:duration=3700:sample_rate=8000"),
        *("-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "16k", str(long)),
    )  # fmt: skip
    out["long"] = long
    return out


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def streams(path: Path) -> list[dict]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip
    return json.loads(out)["streams"]


def decodes(path: Path) -> bool:
    r = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-f", "null", "-"],
        capture_output=True, text=True,
    )  # fmt: skip
    return r.returncode == 0 and not r.stderr.strip()


def movies(cfg) -> dict[str, Path]:
    return {p.stem.split(" (")[0]: p for p in cfg.movies_root.rglob("*.mkv")}


def held(cfg, digest: str) -> int:
    return sum(
        sha(p) == digest
        for root in (cfg.input_dir, cfg.archive_dir, cfg.quarantine_dir)
        if root.exists()
        for p in root.rglob("*")
        if p.is_file()
    )


async def states(factory) -> dict[str, FileState]:
    async with factory() as s:
        return {
            Path(str(i.source_path)).name: i.state
            for i in (await s.execute(select(MediaItem))).scalars()
        }


async def log(factory) -> dict[str, str]:
    async with factory() as s:
        return {
            Path(str(i.source_path)).name: f"{i.state.value} {i.error_log}"
            for i in (await s.execute(select(MediaItem))).scalars()
        }


async def plans(factory) -> list:
    from app.models.media import NormalizationPlan

    async with factory() as s:
        return [
            (p.ffmpeg_args, p.needs_transcode)
            for p in (await s.execute(select(NormalizationPlan))).scalars()
            if "Cover" in str(p.target_path)
        ]


async def drive(orch, factory) -> None:
    await orch.run_until_idle()
    async with factory() as s:
        planned = (
            await s.execute(select(MediaItem.id).where(MediaItem.state == FileState.planned))
        ).scalars().all()  # fmt: skip
    for item_id in planned:
        await orch.approve(str(item_id))
    await orch.run_until_idle()


async def test_messy_movie_library_converges_without_loss_or_junk(tmp_path):
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")
    cfg = make_config(tmp_path, enabled_types=frozenset({"movie"}))
    engine, factory = await make_session_factory(tmp_path)
    made = messy_movies(tmp_path / "pristine")
    sources = {p: sha(p) for p in made.values()}
    shutil.copytree(tmp_path / "pristine", cfg.input_dir, dirs_exist_ok=True)
    await import_input(cfg, factory)
    orch = PipelineOrchestrator(factory, cfg)
    await drive(orch, factory)

    # no source is lost: archived after verify, quarantined, or still in input
    assert [p.name for p, d in sources.items() if held(cfg, d) < 1] == []
    out = movies(cfg)
    wanted = {"Multi Audio", "Old Codec", "Ten Bit", "Atmos", "Cover Art", "Long"}
    assert wanted <= set(out), (set(out), await log(factory))
    # whatever is published decodes cleanly
    assert [k for k, v in out.items() if not decodes(v)] == []

    def kinds(p: Path) -> list[tuple[str, str]]:
        return [(s["codec_type"], s["codec_name"]) for s in streams(p)]

    multi = kinds(out["Multi Audio"])
    assert sum(t == "audio" for t, _ in multi) == 2 and ("subtitle", "subrip") in multi
    assert ("video", "h264") in kinds(out["Old Codec"])
    hdr = next(s for s in streams(out["Ten Bit"]) if s["codec_type"] == "video")
    assert hdr["codec_name"] == "hevc" and hdr["pix_fmt"] == "yuv420p10le"
    atmos = kinds(out["Atmos"])
    assert ("audio", "aac") in atmos and ("audio", "eac3") in atmos
    art = kinds(out["Cover Art"])
    assert [k for t, k in art if t == "video"] == ["h264"], await plans(
        factory
    )  # cover art not re-encoded as video

    # damaged files never publish garbage: quarantined, or repaired into something that decodes
    st = await states(factory)
    bad = await log(factory)
    assert (
        st["Corrupt (2007).mkv"] == FileState.error
    )  # ffprobe cannot read it: stays in input
    assert (
        "ffprobe" in bad["Corrupt (2007).mkv"]
        or "Invalid data" in bad["Corrupt (2007).mkv"]
    )
    assert st["Truncated (2006).mkv"] in (FileState.quarantined, FileState.validated), (
        bad
    )

    # idempotence: the same files dropped again change nothing
    before = sorted(
        p.relative_to(cfg.movies_root)
        for p in cfg.movies_root.rglob("*")
        if p.is_file()
    )
    shutil.copytree(tmp_path / "pristine", cfg.input_dir, dirs_exist_ok=True)
    await import_input(cfg, factory)
    await drive(orch, factory)
    assert (
        sorted(
            p.relative_to(cfg.movies_root)
            for p in cfg.movies_root.rglob("*")
            if p.is_file()
        )
        == before
    )
    assert await states(factory) == st
    await engine.dispose()
