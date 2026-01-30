import pytest
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.tmdb import TMDBService
from app.models.media import MediaItem


@pytest.mark.asyncio
async def test_tmdb_integration_enriches_movie(async_session: AsyncSession):
    # Insert a movie with guessed data
    item = MediaItem(
        id="integration1",
        source_path="/input/movies/Inception.2010.PROPER.1080p.mkv",
        guessed_title="Inception",
        guessed_year=2010,
        media_type="movie",
        state="audited",
    )
    async_session.add(item)
    await async_session.commit()

    # Use a real TMDBService but patch client to mock TMDB
    class MockTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "title": "Inception",
                            "id": 27205,
                            "release_date": "2010-07-15",
                            "popularity": 100,
                            "poster_path": "/poster.jpg",
                        }
                    ]
                },
            )

    client = httpx.AsyncClient(transport=MockTransport())
    service = TMDBService(api_key="dummy", client=client)
    result = await service.fetch_movie_metadata(async_session, "integration1")
    assert result["canonical_title"] == "Inception"
    db_item = await async_session.get(MediaItem, "integration1")
    assert db_item.canonical_title == "Inception"
    assert db_item.release_year == 2010
    assert db_item.tmdb_id == 27205
    assert db_item.state == "planned"
    assert db_item.enrichment_failed is False


@pytest.mark.asyncio
async def test_tmdb_integration_handles_failure(async_session: AsyncSession):
    item = MediaItem(
        id="integration2",
        source_path="/input/movies/NoMatch.2010.mkv",
        guessed_title="NoMatch",
        guessed_year=2010,
        media_type="movie",
        state="audited",
    )
    async_session.add(item)
    await async_session.commit()

    class MockTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            return httpx.Response(200, json={"results": []})

    client = httpx.AsyncClient(transport=MockTransport())
    service = TMDBService(api_key="dummy", client=client)
    result = await service.fetch_movie_metadata(async_session, "integration2")
    assert result is None
    db_item = await async_session.get(MediaItem, "integration2")
    assert db_item.enrichment_failed is True
    assert db_item.state == "audited" or db_item.state == "audited"
