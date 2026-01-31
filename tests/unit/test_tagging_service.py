from unittest.mock import MagicMock
from app.services.tagging_service import TaggingService


def make_metadata():
    return {
        "artist": "Daft Punk",
        "album_artist": "Various Artists",
        "album": "Discovery",
        "title": "One More Time",
        "track_number": 1,
        "track_total": 10,
        "disc_number": 1,
        "disc_total": 1,
        "year": "2001",
        "release_date": "2001-03-12",
        "musicbrainz_trackid": "mbid-track-123",
        "musicbrainz_albumid": "mbid-album-456",
    }


def test_apply_tags_flac(monkeypatch):
    svc = TaggingService()
    fake_audio = MagicMock()
    monkeypatch.setattr("mutagen.File", lambda f, easy=False: fake_audio)
    monkeypatch.setattr(fake_audio, "__class__", type("FLAC", (), {}))
    monkeypatch.setattr(svc, "_tag_flac", lambda a, m, c: True)
    assert svc.apply_tags("song.flac", make_metadata())


def test_apply_tags_mp3(monkeypatch):
    svc = TaggingService()
    fake_audio = MagicMock()
    monkeypatch.setattr("mutagen.File", lambda f, easy=False: fake_audio)
    monkeypatch.setattr(fake_audio, "tags", MagicMock())
    monkeypatch.setattr(fake_audio.tags, "__class__", type("ID3", (), {}))
    monkeypatch.setattr(svc, "_tag_mp3", lambda a, m, c: True)
    assert svc.apply_tags("song.mp3", make_metadata())


def test_apply_tags_mp4(monkeypatch):
    svc = TaggingService()
    fake_audio = MagicMock()
    monkeypatch.setattr("mutagen.File", lambda f, easy=False: fake_audio)
    monkeypatch.setattr(fake_audio, "__class__", type("MP4", (), {}))
    monkeypatch.setattr(svc, "_tag_mp4", lambda a, m, c: True)
    assert svc.apply_tags("song.m4a", make_metadata())


def test_tag_flac_sets_tags(monkeypatch):
    svc = TaggingService()
    fake_audio = MagicMock()
    fake_audio.delete = MagicMock()
    fake_audio.save = MagicMock()
    meta = make_metadata()
    svc._tag_flac(fake_audio, meta, clean=True)
    # Check that tags are set
    assert fake_audio.__setitem__.call_count > 0
    fake_audio.save.assert_called()


def test_tag_mp3_sets_tags(monkeypatch):
    svc = TaggingService()
    fake_audio = MagicMock()
    fake_audio.delete = MagicMock()
    fake_audio.save = MagicMock()
    meta = make_metadata()
    # Patch add to just record calls
    fake_audio.add = MagicMock()
    svc._tag_mp3(fake_audio, meta, clean=True)
    assert fake_audio.add.call_count > 0
    fake_audio.save.assert_called()


def test_tag_mp4_sets_tags(monkeypatch):
    svc = TaggingService()
    fake_audio = MagicMock()
    fake_audio.delete = MagicMock()
    fake_audio.save = MagicMock()
    meta = make_metadata()
    svc._tag_mp4(fake_audio, meta, clean=True)
    assert fake_audio.save.called


def test_apply_tags_unsupported(monkeypatch):
    svc = TaggingService()
    monkeypatch.setattr("mutagen.File", lambda f, easy=False: None)
    assert not svc.apply_tags("song.xyz", make_metadata())
