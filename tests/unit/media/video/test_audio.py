from app.media.video.audio import atmos_stream_index, audio_args

AAC = {"index": 1, "codec_type": "audio", "codec_name": "aac"}
ATMOS_PROFILE = {
    "index": 5,
    "codec_type": "audio",
    "codec_name": "eac3",
    "profile": "Dolby Atmos",
}
ATMOS_TITLE = {
    "index": 3,
    "codec_type": "audio",
    "codec_name": "eac3",
    "tags": {"title": "English Atmos"},
}
PLAIN_EAC3 = {
    "index": 2,
    "codec_type": "audio",
    "codec_name": "eac3",
    "tags": {"title": "English"},
}
FAKE = {"index": 4, "codec_type": "audio", "codec_name": "ac3", "profile": "Dolby Atmos"}  # fmt: skip


def test_detects_atmos_by_profile_or_title_on_eac3_only():
    assert atmos_stream_index([AAC, ATMOS_PROFILE]) == 5
    assert atmos_stream_index([PLAIN_EAC3, ATMOS_TITLE]) == 3
    assert atmos_stream_index([AAC, PLAIN_EAC3, FAKE]) is None


def test_audio_args_copy_atmos_track_as_second_output():
    args = audio_args([AAC, ATMOS_PROFILE])
    assert args[:4] == ["-map", "0:a:0?", "-c:a:0", "aac"]
    assert args[-4:] == ["-map", "0:5", "-c:a:1", "copy"]
    assert "eac3" not in args  # E-AC3 is only ever copied, never synthesised


def test_audio_args_without_atmos_has_no_copy_track():
    assert "copy" not in audio_args([AAC, PLAIN_EAC3])
