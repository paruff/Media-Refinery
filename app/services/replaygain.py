"""ReplayGain via ffmpeg's replaygain filter (R-MUSIC-2); album gain = tracks played back to back."""

import re
from pathlib import Path

from app.core.tools import run_tool

_GAIN = re.compile(r"track_gain = ([+-]?[\d.]+) dB")
_PEAK = re.compile(r"track_peak = ([\d.]+)")


async def measure(paths: list[Path]) -> tuple[str, str] | None:
    """("-3.94 dB", "0.250000") for the paths concatenated; None if ffmpeg cannot tell."""
    inputs = [arg for p in paths for arg in ("-i", str(p))]
    # ponytail: normalised to 48 kHz stereo so mixed albums concat; peak is of that mix
    legs = "".join(
        f"[{i}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}];"
        for i in range(len(paths))
    )
    joined = "".join(f"[a{i}]" for i in range(len(paths)))
    graph = f"{legs}{joined}concat=n={len(paths)}:v=0:a=1,replaygain"
    rc, _, err = await run_tool(
        [
            *("ffmpeg", "-nostdin", "-hide_banner", "-v", "info", *inputs),
            *("-filter_complex", graph, "-f", "null", "-"),
        ],
        3600,
    )
    gain, peak = _GAIN.search(err), _PEAK.search(err)
    if rc != 0 or not gain or not peak:
        return None
    return f"{float(gain.group(1)):+.2f} dB", f"{float(peak.group(1)):.6f}"
