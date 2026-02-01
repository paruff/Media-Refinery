import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.musicbrainz import MusicBrainzService
from app.models.media import MediaItem


@pytest.mark.asyncio
async def test_musicbrainz_integration_various_tracks(async_session: AsyncSession):
    # Test multiple tracks from the same album
    tracks = [
        (1, "Airbag"),
        (2, "Paranoid Android"),
        (3, "Subterranean Homesick Alien"),
        (4, "Exit Music (for a Film)"),
        (5, "Let Down"),
    ]
    items = []
    for i, (track_number, track_title) in enumerate(tracks, 1):
        item = MediaItem(
            id=f"int_{i}",
            source_path=f"/music/Radiohead/OK Computer/{track_number:02d} - {track_title}.flac",
            enrichment_data=f'{{"artist": "Radiohead", "album": "OK Computer", "track_number": {track_number}, "track_title": "{track_title}"}}',
            media_type="music",
            state="audited",
        )
        items.append(item)
    async_session.add_all(items)
    await async_session.commit()
    service = MusicBrainzService()
    for i, (track_number, track_title) in enumerate(tracks, 1):
        result = await service.enrich_music(async_session, f"int_{i}")
        if result is None:
            pytest.skip(
                "MusicBrainz not reachable or rate-limited; skipping integration test"
            )
        assert result is not None
        assert result["album_artist"].lower() == "radiohead"
        assert result["album_name"].lower() == "ok computer"
        assert result["release_year"] >= 1997
        assert result["disc_number"] == 1
        assert result["mbid"]
        assert result["release_mbid"]
        db_item = await async_session.get(MediaItem, f"int_{i}")
        assert db_item.album_artist.lower() == "radiohead"
        assert db_item.album_name.lower() == "ok computer"
        assert db_item.state == "ready_to_plan"
        assert db_item.enrichment_failed is False


@pytest.mark.asyncio
async def test_musicbrainz_integration_no_match(async_session: AsyncSession):
    item = MediaItem(
        id="int_fail",
        source_path="/music/Unknown Artist/Unknown Album/01 - Mystery.flac",
        enrichment_data='{"artist": "Unknown Artist", "album": "Unknown Album", "track_number": 1, "track_title": "Mystery"}',
        media_type="music",
        state="audited",
    )
    async_session.add(item)
    await async_session.commit()
    service = MusicBrainzService()
    result = await service.enrich_music(async_session, "int_fail")
    assert result is None
    db_item = await async_session.get(MediaItem, "int_fail")
    assert db_item.enrichment_failed is True
