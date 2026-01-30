import asyncio
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.musicbrainz import MusicBrainzService
from app.models.media import MediaItem


class MockMusicBrainz:
    def __init__(self, releases):
        self.releases = releases
        self.calls = []
    def search_releases(self, artist, release, limit, includes=None):
        self.calls.append((artist, release))
        return {"release-list": self.releases.get((artist, release), [])}

    def get_release_by_id(self, release_id, includes=None):
        # Find the release by id in self.releases
        for releases in self.releases.values():
            for release in releases:
                if release["id"] == release_id:
                    return {"release": release}
        raise Exception(f"Release id {release_id} not found in mock")

@pytest.mark.asyncio
async def test_musicbrainz_enrichment_success(monkeypatch, async_session: AsyncSession):
    # Mock MusicBrainz
    releases = {
        ("Daft Punk", "Discovery"): [
            {
                "title": "Discovery",
                "id": "release-mbid-123",
                "date": "2001-03-12",
                "artist-credit": [{"artist": {"name": "Daft Punk"}}],
                "medium-list": [
                    {
                        "position": 1,
                        "track-list": [
                            {"number": "1", "recording": {"title": "Intro", "id": "rec-mbid-1"}},
                            {"number": "2", "recording": {"title": "Aerodynamic", "id": "rec-mbid-2"}},
                        ]
                    }
                ]
            }
        ]
    }
    mock = MockMusicBrainz(releases)
    monkeypatch.setattr("musicbrainzngs.search_releases", mock.search_releases)
    monkeypatch.setattr("musicbrainzngs.get_release_by_id", mock.get_release_by_id)
    item = MediaItem(
        id="m1",
        source_path="/music/Daft Punk/Discovery/01 - Intro.flac",
        enrichment_data='{"artist": "Daft Punk", "album": "Discovery", "track_number": 1, "track_title": "Intro"}',
        media_type="music",
        state="audited"
    )
    async_session.add(item)
    await async_session.commit()
    service = MusicBrainzService()
    result = await service.enrich_music(async_session, "m1")
    assert result["album_artist"] == "Daft Punk"
    assert result["album_name"] == "Discovery"
    assert result["release_year"] == 2001
    assert result["disc_number"] == 1
    assert result["mbid"] == "rec-mbid-1"
    assert result["release_mbid"] == "release-mbid-123"
    db_item = await async_session.get(MediaItem, "m1")
    assert db_item.album_artist == "Daft Punk"
    assert db_item.album_name == "Discovery"
    assert db_item.release_year == 2001
    assert db_item.disc_number == 1
    assert db_item.mbid == "rec-mbid-1"
    assert db_item.release_mbid == "release-mbid-123"
    assert db_item.state == "ready_to_plan"
    assert db_item.enrichment_failed is False

@pytest.mark.asyncio
async def test_musicbrainz_enrichment_no_match(monkeypatch, async_session: AsyncSession):
    releases = { ("Unknown Artist", "Unknown Album"): [] }
    mock = MockMusicBrainz(releases)
    monkeypatch.setattr("musicbrainzngs.search_releases", mock.search_releases)
    monkeypatch.setattr("musicbrainzngs.get_release_by_id", mock.get_release_by_id)
    item = MediaItem(
        id="m2",
        source_path="/music/Unknown Artist/Unknown Album/01 - Mystery.flac",
        enrichment_data='{"artist": "Unknown Artist", "album": "Unknown Album", "track_number": 1, "track_title": "Mystery"}',
        media_type="music",
        state="audited"
    )
    async_session.add(item)
    await async_session.commit()
    service = MusicBrainzService()
    result = await service.enrich_music(async_session, "m2")
    assert result is None
    db_item = await async_session.get(MediaItem, "m2")
    assert db_item.enrichment_failed is True

@pytest.mark.asyncio
async def test_musicbrainz_enrichment_multidisc(monkeypatch, async_session: AsyncSession):
    releases = {
        ("Daft Punk", "Alive 2007"): [
            {
                "title": "Alive 2007",
                "id": "release-mbid-456",
                "date": "2007-11-19",
                "artist-credit": [{"artist": {"name": "Daft Punk"}}],
                "medium-list": [
                    {
                        "position": 1,
                        "track-list": [
                            {"number": "1", "recording": {"title": "Robot Rock", "id": "rec-mbid-3"}},
                        ]
                    },
                    {
                        "position": 2,
                        "track-list": [
                            {"number": "4", "recording": {"title": "Human After All", "id": "rec-mbid-4"}},
                        ]
                    }
                ]
            }
        ]
    }
    mock = MockMusicBrainz(releases)
    monkeypatch.setattr("musicbrainzngs.search_releases", mock.search_releases)
    monkeypatch.setattr("musicbrainzngs.get_release_by_id", mock.get_release_by_id)
    item = MediaItem(
        id="m3",
        source_path="/music/Daft Punk/Alive 2007/2-04 - Human After All.flac",
        enrichment_data='{"artist": "Daft Punk", "album": "Alive 2007", "track_number": 4, "track_title": "Human After All"}',
        media_type="music",
        state="audited"
    )
    async_session.add(item)
    await async_session.commit()
    service = MusicBrainzService()
    result = await service.enrich_music(async_session, "m3")
    assert result["disc_number"] == 2
    assert result["mbid"] == "rec-mbid-4"
    db_item = await async_session.get(MediaItem, "m3")
    assert db_item.disc_number == 2
    assert db_item.mbid == "rec-mbid-4"
    assert db_item.state == "ready_to_plan"
    assert db_item.enrichment_failed is False
@pytest.mark.asyncio
async def test_musicbrainz_enrichment_caching(monkeypatch, async_session: AsyncSession):
    releases = {
        ("Daft Punk", "Discovery"): [
            {
                "title": "Discovery",
                "id": "release-mbid-123",
                "date": "2001-03-12",
                "artist-credit": [{"artist": {"name": "Daft Punk"}}],
                "medium-list": [
                    {
                        "position": 1,
                        "track-list": [
                            {"number": "1", "recording": {"title": "Intro", "id": "rec-mbid-1"}},
                        ]
                    }
                ]
            }
        ]
    }
    from app.services.musicbrainz import AlbumCache, MusicBrainzService
    cache = AlbumCache()
    mock = MockMusicBrainz(releases)
    # Patch the service to use the same cache as the mock
    service = MusicBrainzService(cache=cache)
    monkeypatch.setattr("musicbrainzngs.search_releases", mock.search_releases)
    monkeypatch.setattr("musicbrainzngs.get_release_by_id", mock.get_release_by_id)
    item1 = MediaItem(
        id="m4",
        source_path="/music/Daft Punk/Discovery/01 - Intro.flac",
        enrichment_data='{"artist": "Daft Punk", "album": "Discovery", "track_number": 1, "track_title": "Intro"}',
        media_type="music",
        state="audited"
    )
    item2 = MediaItem(
        id="m5",
    source_path="/music/Daft Punk/Discovery/02 - Aerodynamic.flac",
    enrichment_data='{"artist": "Daft Punk", "album": "Discovery", "track_number": 2, "track_title": "Aerodynamic"}',
    media_type="music",
    state="audited"
    )
    async_session.add_all([item1, item2])
    await async_session.commit()
    await service.enrich_music(async_session, "m4")
    await service.enrich_music(async_session, "m5")
    # Only one search call should be made for the album
    assert mock.calls.count(("Daft Punk", "Discovery")) == 1
