import pytest
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.tmdb import TMDBService
from app.models.media import MediaItem


class MockTransport(httpx.AsyncBaseTransport):
    def __init__(self, response_data):
        self.response_data = response_data
        self.called = False

    async def handle_async_request(self, request):
        self.called = True
        return httpx.Response(200, json=self.response_data)


@pytest.mark.asyncio
async def test_tmdb_enrichment_success(async_session: AsyncSession):
    # Insert a test media item
    item = MediaItem(
        id="testid",
        source_path="/input/movies/Inception.2010.PROPER.1080p.mkv",
        guessed_title="Inception",
        guessed_year=2010,
        media_type="movie",
        state="audited",
    )
    async_session.add(item)
    await async_session.commit()
    # Mock TMDB response
    mock_data = {
        "results": [
            {
                "title": "Inception",
                "id": 27205,
                "release_date": "2010-07-15",
                "popularity": 100,
                "poster_path": "/poster.jpg",
            }
        ]
    }
    transport = MockTransport(mock_data)
    client = httpx.AsyncClient(transport=transport)
    service = TMDBService(api_key="dummy", client=client)
    result = await service.fetch_movie_metadata(async_session, "testid")
    assert result["canonical_title"] == "Inception"
    assert result["release_year"] == 2010
    assert result["tmdb_id"] == 27205
    assert result["poster_path"] == "/poster.jpg"
    # Check DB update
    db_item = await async_session.get(MediaItem, "testid")
    assert db_item.canonical_title == "Inception"
    assert db_item.release_year == 2010
    assert db_item.tmdb_id == 27205
    assert db_item.poster_path == "/poster.jpg"
    assert db_item.state == "ready_to_plan"
    assert db_item.enrichment_failed is False
