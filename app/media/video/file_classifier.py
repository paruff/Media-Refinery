CODEC_CLASSES = {
    "mpeg4": "xvid",
    "h264": "h264",
    "mpeg1video": "mpeg1",
    "mpeg2video": "mpeg2",
    # ffmpeg encodes wmv1/wmv2 but not wmv3; all three need the same packet resync
    "wmv1": "wmv",
    "wmv2": "wmv",
    "wmv3": "wmv",
}


def classify_video(stream: dict) -> str:
    return CODEC_CLASSES.get(stream.get("codec_name", ""), "other")
