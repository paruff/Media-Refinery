import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.musicbrainz import MusicBrainzService
from app.models.media import MediaItem


@pytest.mark.asyncio
async def test_musicbrainz_integration(async_session: AsyncSession):
    # This test will hit the real MusicBrainz API (rate-limited, slow)
    # Use a real, well-known album/track for reliability
    item = MediaItem(
        id="int1",
        source_path="/music/Radiohead/OK Computer/01 - Airbag.flac",
        enrichment_data='{"artist": "Radiohead", "album": "OK Computer", "track_number": 1, "track_title": "Airbag"}',
        media_type="music",
        state="audited",
    )
    async_session.add(item)
    await async_session.commit()
    service = MusicBrainzService()
    result = await service.enrich_music(async_session, "int1")
    assert result is not None
    assert result["album_artist"].lower() == "radiohead"
    assert result["album_name"].lower() == "ok computer"
    assert result["release_year"] >= 1997
    assert result["disc_number"] == 1
    assert result["mbid"]
    assert result["release_mbid"]
    db_item = await async_session.get(MediaItem, "int1")
    assert db_item.album_artist.lower() == "radiohead"
    assert db_item.album_name.lower() == "ok computer"
    assert db_item.state == "planned"
    assert db_item.enrichment_failed is False
