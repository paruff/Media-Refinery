"""Does a probed file direct-play on a device profile (R-VIDEO-3)? No transcode needed if so."""

from pathlib import Path
from typing import Any

from app.models.device_profile import DeviceProfile


def check_profile(
    path: Path, probe_data: dict[str, Any], profile: DeviceProfile
) -> list[str]:
    """Violations of `profile`; an empty list means the file conforms."""
    streams = probe_data.get("streams", [])
    video = [s for s in streams if s.get("codec_type") == "video"]
    problems = []
    if path.suffix.lstrip(".").lower() not in profile.container:
        problems.append(f"container {path.suffix} not in {profile.container}")
    if not video:
        problems.append("no video stream")
    for v in video:
        if v.get("codec_name") not in profile.supported_video:
            problems.append(
                f"video codec {v.get('codec_name')} not in {profile.supported_video}"
            )
        if v.get("width", 0) > profile.max_resolution.width or (
            v.get("height", 0) > profile.max_resolution.height
        ):
            problems.append(f"resolution {v.get('width')}x{v.get('height')} too large")
    for a in (s for s in streams if s.get("codec_type") == "audio"):
        if a.get("codec_name") not in profile.supported_audio:
            problems.append(
                f"audio codec {a.get('codec_name')} not in {profile.supported_audio}"
            )
    return problems
