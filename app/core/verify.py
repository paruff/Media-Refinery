"""VERIFY stage: generic spec §6 checks (decode, duration, sha256)."""

import asyncio
import hashlib
import shutil
from dataclasses import asdict, dataclass

from app.core.tools import probe_duration, run_tool

AUDIO_TOLERANCE = 0.5  # seconds
VIDEO_TOLERANCE = 1.0
REASONS = {
    "decode": "decode_failed",
    "duration": "duration_mismatch",
    "flac": "flac_test_failed",
}


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str = ""


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


async def _flac_test(output: str) -> Check:
    if shutil.which("flac") is None:  # recorded, not failed (like VMAF without libvmaf)
        return Check("flac", True, "unavailable")
    rc, _, err = await run_tool(["flac", "-t", "-s", output], 3600)
    return Check("flac", rc == 0, err.strip()[:500])


async def verify_output(source: str, output: str, is_audio: bool):
    """Return (checks as dicts, output sha256, quarantine reason or None)."""
    rc, _, err = await run_tool(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", output, "-f", "null", "-"], 3600
    )
    checks = [Check("decode", rc == 0 and not err.strip(), err.strip()[:500])]
    src_dur, out_dur = await probe_duration(source), await probe_duration(output)
    tolerance = AUDIO_TOLERANCE if is_audio else VIDEO_TOLERANCE
    if src_dur is None or out_dur is None:
        checks.append(Check("duration", False, "ffprobe could not read a duration"))
    else:
        delta = abs(src_dur - out_dur)
        checks.append(
            Check(
                "duration",
                delta <= tolerance,
                f"source {src_dur:.2f}s output {out_dur:.2f}s",
            )
        )
    if output.endswith(".flac"):  # R-MUSIC: native integrity test on top of the decode
        checks.append(await _flac_test(output))
    digest = await asyncio.to_thread(sha256_file, output)
    checks.append(Check("sha256", True, digest))
    failed = next((c for c in checks if not c.passed), None)
    return [asdict(c) for c in checks], digest, REASONS[failed.name] if failed else None
