import pytest
import asyncio
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.tmdb import TMDBService
from app.models.media import MediaItem


class MockTransport(httpx.AsyncBaseTransport):
    def __init__(self, response_data, status_code=200):
        self.response_data = response_data
        self.status_code = status_code
        self.called = False

    async def handle_async_request(self, request):
        self.called = True
        return httpx.Response(self.status_code, json=self.response_data)


@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_tmdb_enrichment_success(async_session: AsyncSession):
    item = MediaItem(
        id="testid",
        source_path="/input/movies/Inception.2010.PROPER.1080p.mkv",
        canonical_title="Inception",
        release_year=2010,
        media_type="movie",
        state="audited",
    )
    async_session.add(item)
    await async_session.commit()
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
    async with httpx.AsyncClient(transport=transport, timeout=5.0) as client:
        service = TMDBService(api_key="dummy", client=client)
        result = await asyncio.wait_for(
            service.fetch_movie_metadata(async_session, "testid"), timeout=8
        )
    assert result["canonical_title"] == "Inception"
    assert result["release_year"] == 2010
    assert result["tmdb_id"] == 27205
    assert result["poster_path"] == "/poster.jpg"
    db_item = await async_session.get(MediaItem, "testid")
    assert db_item.canonical_title == "Inception"
    assert db_item.release_year == 2010
    assert db_item.tmdb_id == 27205
    assert db_item.poster_path == "/poster.jpg"
    assert db_item.state == "ready_to_plan"
    assert db_item.enrichment_failed is False


@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_tmdb_enrichment_no_results(async_session: AsyncSession):
    item = MediaItem(
        id="testid2",
        source_path="/input/movies/UnknownMovie.2020.mkv",
        canonical_title="UnknownMovie",
        release_year=2020,
        media_type="movie",
        state="audited",
    )
    async_session.add(item)
    await async_session.commit()
    mock_data = {"results": []}
    transport = MockTransport(mock_data)
    async with httpx.AsyncClient(transport=transport, timeout=5.0) as client:
        service = TMDBService(api_key="dummy", client=client)
        result = await asyncio.wait_for(
            service.fetch_movie_metadata(async_session, "testid2"), timeout=8
        )
    assert result is None
    db_item = await async_session.get(MediaItem, "testid2")
    assert db_item.enrichment_failed is True


@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_tmdb_enrichment_401(async_session: AsyncSession):
    item = MediaItem(
        id="testid3",
        source_path="/input/movies/BadKey.2010.mkv",
        canonical_title="BadKey",
        release_year=2010,
        media_type="movie",
        state="audited",
    )
    async_session.add(item)
    await async_session.commit()
    transport = MockTransport({}, status_code=401)
    async with httpx.AsyncClient(transport=transport, timeout=5.0) as client:
        service = TMDBService(api_key="badkey", client=client)
        result = await asyncio.wait_for(
            service.fetch_movie_metadata(async_session, "testid3"), timeout=8
        )
    assert result is None
    db_item = await async_session.get(MediaItem, "testid3")
    assert db_item.enrichment_failed is True


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_tmdb_enrichment_429(async_session: AsyncSession):
    # NOTE: If this test times out, the asyncio.Lock in TMDBService may remain locked, causing deadlocks in later tests.
    # Always ensure timeouts are handled and TMDBService is re-instantiated per test.
    item = MediaItem(
        id="testid4",
        source_path="/input/movies/RateLimit.2010.mkv",
        canonical_title="RateLimit",
        release_year=2010,
        media_type="movie",
        state="audited",
    )
    async_session.add(item)
    await async_session.commit()

    # Simulate 429 then success
    class FlakyTransport(httpx.AsyncBaseTransport):
        def __init__(self):
            self.calls = 0

        async def handle_async_request(self, request):
            self.calls += 1
            if self.calls == 1:
                return httpx.Response(429, json={})
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "title": "RateLimit",
                            "id": 99999,
                            "release_date": "2010-01-01",
                            "popularity": 99,
                            "poster_path": "/poster2.jpg",
                        }
                    ]
                },
            )

    async with httpx.AsyncClient(transport=FlakyTransport(), timeout=5.0) as client:
        service = TMDBService(api_key="dummy", client=client)
        try:
            result = await asyncio.wait_for(
                service.fetch_movie_metadata(async_session, "testid4"), timeout=12
            )
        except asyncio.TimeoutError:
            pytest.fail(
                "TMDBService.fetch_movie_metadata timed out (possible lock deadlock after cancellation)"
            )
        assert result["canonical_title"] == "RateLimit"
        db_item = await async_session.get(MediaItem, "testid4")
        assert db_item.canonical_title == "RateLimit"
        assert db_item.state == "ready_to_plan"
        assert db_item.enrichment_failed is False


@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_tmdb_enrichment_cache(async_session: AsyncSession):
    item = MediaItem(
        id="testid5",
        source_path="/input/movies/Cached.2010.mkv",
        canonical_title="Cached",
        release_year=2010,
        media_type="movie",
        state="audited",
    )
    async_session.add(item)
    await async_session.commit()
    mock_data = {
        "results": [
            {
                "title": "Cached",
                "id": 88888,
                "release_date": "2010-01-01",
                "popularity": 88,
                "poster_path": "/poster3.jpg",
            }
        ]
    }
    transport = MockTransport(mock_data)
    async with httpx.AsyncClient(transport=transport, timeout=5.0) as client:
        service = TMDBService(api_key="dummy", client=client)
        # First call populates cache
        await asyncio.wait_for(
            service.fetch_movie_metadata(async_session, "testid5"), timeout=8
        )
        # Second call should hit cache, not transport
        item2 = MediaItem(
            id="testid6",
            source_path="/input/movies/Cached2.2010.mkv",  # Use unique source_path to avoid IntegrityError
            canonical_title="Cached",
            release_year=2010,
            media_type="movie",
            state="audited",
        )
        async_session.add(item2)
        await async_session.commit()
        await asyncio.wait_for(
            service.fetch_movie_metadata(async_session, "testid6"), timeout=8
        )
    assert transport.called is True
    db_item2 = await async_session.get(MediaItem, "testid6")
    assert db_item2.canonical_title == "Cached"
    assert db_item2.tmdb_id == 88888
    assert db_item2.state == "ready_to_plan"
    assert db_item2.enrichment_failed is False
