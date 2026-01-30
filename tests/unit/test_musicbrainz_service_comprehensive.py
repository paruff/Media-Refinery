import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.musicbrainz import MusicBrainzService
from app.models.media import MediaItem


class DummyRelease:
    def __init__(self, title, id, date, artist, tracks, mediums=1):
        self.data = {
            "title": title,
            "id": id,
            "date": date,
            "artist-credit": [{"artist": {"name": artist}}],
            "medium-list": [
                {
                    "position": i + 1,
                    "track-list": tracks[i] if isinstance(tracks[0], list) else tracks,
                }
                for i in range(mediums)
            ],
        }

    def as_dict(self):
        return self.data


class MockMusicBrainz:
    def __init__(self, releases, full_release=None):
        self.releases = releases
        self.full_release = full_release or {}
        self.calls = []

    def search_releases(self, artist, release, limit):
        self.calls.append((artist, release))
        return {"release-list": self.releases.get((artist, release), [])}

    def get_release_by_id(self, rid, includes):
        return {"release": self.full_release.get(rid)}


@pytest.mark.asyncio
async def test_enrich_success_single_disc(monkeypatch, async_session: AsyncSession):
    tracks = [
        {"number": "1", "recording": {"title": "Intro", "id": "rec-1"}},
        {"number": "2", "recording": {"title": "Song2", "id": "rec-2"}},
    ]
    release = DummyRelease(
        "Test Album", "rel-1", "2020-01-01", "Test Artist", tracks
    ).as_dict()
    mock = MockMusicBrainz(
        {("Test Artist", "Test Album"): [{"id": "rel-1"}]}, {"rel-1": release}
    )
    monkeypatch.setattr("musicbrainzngs.search_releases", mock.search_releases)
    monkeypatch.setattr("musicbrainzngs.get_release_by_id", mock.get_release_by_id)
    item = MediaItem(
        id="t1",
        source_path="/music/Test Artist/Test Album/01 - Intro.flac",
        enrichment_data='{"artist": "Test Artist", "album": "Test Album", "track_number": 1, "track_title": "Intro"}',
        media_type="music",
        state="audited",
    )
    async_session.add(item)
    await async_session.commit()
    service = MusicBrainzService()
    result = await service.enrich_music(async_session, "t1")
    assert result["album_artist"] == "Test Artist"
    assert result["album_name"] == "Test Album"
    assert result["release_year"] == 2020
    assert result["disc_number"] == 1
    assert result["mbid"] == "rec-1"
    assert result["release_mbid"] == "rel-1"
    db_item = await async_session.get(MediaItem, "t1")
    assert db_item.album_artist == "Test Artist"
    assert db_item.album_name == "Test Album"
    assert db_item.release_year == 2020
    assert db_item.disc_number == 1
    assert db_item.mbid == "rec-1"
    assert db_item.release_mbid == "rel-1"
    assert db_item.state == "planned"
    assert db_item.enrichment_failed is False


@pytest.mark.asyncio
async def test_enrich_multidisc(monkeypatch, async_session: AsyncSession):
    tracks = [
        [{"number": "1", "recording": {"title": "Disc1Track1", "id": "rec-1"}}],
        [{"number": "2", "recording": {"title": "Disc2Track2", "id": "rec-2"}}],
    ]
    release = DummyRelease(
        "MultiDisc", "rel-2", "2019-01-01", "Artist", tracks, mediums=2
    ).as_dict()
    mock = MockMusicBrainz(
        {("Artist", "MultiDisc"): [{"id": "rel-2"}]}, {"rel-2": release}
    )
    monkeypatch.setattr("musicbrainzngs.search_releases", mock.search_releases)
    monkeypatch.setattr("musicbrainzngs.get_release_by_id", mock.get_release_by_id)
    item = MediaItem(
        id="t2",
        source_path="/music/Artist/MultiDisc/2-02 - Disc2Track2.flac",
        enrichment_data='{"artist": "Artist", "album": "MultiDisc", "track_number": 2, "track_title": "Disc2Track2"}',
        media_type="music",
        state="audited",
    )
    async_session.add(item)
    await async_session.commit()
    service = MusicBrainzService()
    result = await service.enrich_music(async_session, "t2")
    assert result["disc_number"] == 2
    assert result["mbid"] == "rec-2"
    db_item = await async_session.get(MediaItem, "t2")
    assert db_item.disc_number == 2
    assert db_item.mbid == "rec-2"
    assert db_item.state == "planned"
    assert db_item.enrichment_failed is False


@pytest.mark.asyncio
async def test_enrich_no_match(monkeypatch, async_session: AsyncSession):
    mock = MockMusicBrainz({("X", "Y"): []})
    monkeypatch.setattr("musicbrainzngs.search_releases", mock.search_releases)
    monkeypatch.setattr("musicbrainzngs.get_release_by_id", mock.get_release_by_id)
    item = MediaItem(
        id="t3",
        source_path="/music/X/Y/01 - Z.flac",
        enrichment_data='{"artist": "X", "album": "Y", "track_number": 1, "track_title": "Z"}',
        media_type="music",
        state="audited",
    )
    async_session.add(item)
    await async_session.commit()
    service = MusicBrainzService()
    result = await service.enrich_music(async_session, "t3")
    assert result is None
    db_item = await async_session.get(MediaItem, "t3")
    assert db_item.enrichment_failed is True


@pytest.mark.asyncio
async def test_enrich_track_fuzzy(monkeypatch, async_session: AsyncSession):
    tracks = [
        {"number": "1", "recording": {"title": "Intro (Remastered)", "id": "rec-1"}},
        {"number": "2", "recording": {"title": "Aerodynamic", "id": "rec-2"}},
    ]
    release = DummyRelease(
        "Discovery", "rel-3", "2001-03-12", "Daft Punk", tracks
    ).as_dict()
    mock = MockMusicBrainz(
        {("Daft Punk", "Discovery"): [{"id": "rel-3"}]}, {"rel-3": release}
    )
    monkeypatch.setattr("musicbrainzngs.search_releases", mock.search_releases)
    monkeypatch.setattr("musicbrainzngs.get_release_by_id", mock.get_release_by_id)
    item = MediaItem(
        id="t4",
        source_path="/music/Daft Punk/Discovery/01 - Intro.flac",
        enrichment_data='{"artist": "Daft Punk", "album": "Discovery", "track_number": 1, "track_title": "Intro"}',
        media_type="music",
        state="audited",
    )
    async_session.add(item)
    await async_session.commit()
    service = MusicBrainzService()
    result = await service.enrich_music(async_session, "t4")
    assert result["mbid"] == "rec-1"
    db_item = await async_session.get(MediaItem, "t4")
    assert db_item.mbid == "rec-1"
    assert db_item.state == "planned"
    assert db_item.enrichment_failed is False


@pytest.mark.asyncio
async def test_enrich_caching(monkeypatch, async_session: AsyncSession):
    tracks = [
        {"number": "1", "recording": {"title": "Intro", "id": "rec-1"}},
    ]
    release = DummyRelease(
        "Discovery", "rel-4", "2001-03-12", "Daft Punk", tracks
    ).as_dict()
    mock = MockMusicBrainz(
        {("Daft Punk", "Discovery"): [{"id": "rel-4"}]}, {"rel-4": release}
    )
    monkeypatch.setattr("musicbrainzngs.search_releases", mock.search_releases)
    monkeypatch.setattr("musicbrainzngs.get_release_by_id", mock.get_release_by_id)
    item1 = MediaItem(
        id="t5",
        source_path="/music/Daft Punk/Discovery/01 - Intro.flac",
        enrichment_data='{"artist": "Daft Punk", "album": "Discovery", "track_number": 1, "track_title": "Intro"}',
        media_type="music",
        state="audited",
    )
    item2 = MediaItem(
        id="t6",
        source_path="/music/Daft Punk/Discovery/02 - Aerodynamic.flac",
        enrichment_data='{"artist": "Daft Punk", "album": "Discovery", "track_number": 2, "track_title": "Aerodynamic"}',
        media_type="music",
        state="audited",
    )
    async_session.add_all([item1, item2])
    await async_session.commit()
    service = MusicBrainzService()
    await service.enrich_music(async_session, "t5")
    await service.enrich_music(async_session, "t6")
    # Only one search call should be made for the album
    assert mock.calls.count(("Daft Punk", "Discovery")) == 1
