# app/core/ffmpeg_profiles.py
"""
Centralized FFMPEG profiles for transcoding to target device standards.
"""

SAMSUNG_SERIES_65 = {
    "4k": [
        "-c:v",
        "libx265",
        "-tag:v",
        "hvc1",
        "-pix_fmt",
        "yuv420p10le",
        "-crf",
        "20",
    ],
    "1080p": [
        "-c:v",
        "libx264",
        "-profile:v",
        "high",
        "-level",
        "4.1",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        "18",
    ],
    "audio_stereo": ["-c:a", "aac", "-ac", "2", "-b:a", "192k"],
    "audio_surround": ["-c:a", "ac3", "-ac", "6", "-b:a", "640k"],
    "container": [".mkv", ".mp4"],
    "map_all": ["-map", "0"],
}

PROFILE_MAP = {
    "Samsung_Series_65": SAMSUNG_SERIES_65,
}


def get_ffmpeg_args(profile: str, resolution: str, surround: bool = False) -> list:
    """
    Returns ffmpeg argument list for the given profile and resolution.
    """
    p = PROFILE_MAP[profile]
    args = []
    if resolution == "4k":
        args += p["4k"]
    else:
        args += p["1080p"]
    if surround:
        args += p["audio_surround"]
    else:
        args += p["audio_stereo"]
    args += p["map_all"]
    return args
