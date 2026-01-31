from app.models.media import MediaItem


def test_mediaitem_fingerprint_fields():
    item = MediaItem(source_path="foo.mp3")
    item.audio_fingerprint = "abc123"
    item.video_fingerprint = "def456"
    assert item.audio_fingerprint == "abc123"
    assert item.video_fingerprint == "def456"
