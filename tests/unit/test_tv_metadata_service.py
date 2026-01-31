import pytest
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.tv_metadata import TVMetadataService
from app.models.media import MediaItem


class MockTransport(httpx.AsyncBaseTransport):
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    async def handle_async_request(self, request):
        self.calls.append(request.url.path)
        # Return the right response based on the path
        for path, resp in self.responses.items():
            if path in str(request.url):
                return httpx.Response(resp["status"], json=resp["data"])
        return httpx.Response(404, json={})


@pytest.mark.asyncio
async def test_tv_enrichment_success(async_session: AsyncSession):
    item = MediaItem(
        id="tv1",
        source_path="/input/tv/The.Bear.S01E01.mkv",
        enrichment_data='{"series_title": "The Bear", "season_number": 1, "episode_number": 1, "year": 2022}',
        media_type="series",
        state="audited",
    )
    async_session.add(item)
    await async_session.commit()
    responses = {
        "/search/tv": {
            "status": 200,
            "data": {
                "results": [
                    {"id": 136315, "name": "The Bear", "first_air_date": "2022-06-23"}
                ]
            },
        },
        "/tv/136315/season/1/episode/1": {
            "status": 200,
            "data": {
                "name": "System",
                "episode_number": 1,
                "overview": "Carmy returns to Chicago.",
            },
        },
    }
    client = httpx.AsyncClient(transport=MockTransport(responses))
    service = TVMetadataService(api_key="dummy", client=client)
    result = await service.fetch_series_metadata(async_session, "tv1")
    assert result["canonical_series_name"] == "The Bear"
    assert result["episode_title"] == "System"
    assert result["absolute_number"] == 1
    db_item = await async_session.get(MediaItem, "tv1")
    assert db_item.canonical_series_name == "The Bear"
    assert db_item.episode_title == "System"
    assert db_item.absolute_number == 1
    assert db_item.tmdb_series_id == 136315
    assert db_item.state == "ready_to_plan"
    assert db_item.metadata_mismatch is False


@pytest.mark.asyncio
async def test_tv_enrichment_episode_not_found(async_session: AsyncSession):
    item = MediaItem(
        id="tv2",
        source_path="/input/tv/The.Bear.S01E99.mkv",
        enrichment_data='{"series_title": "The Bear", "season_number": 1, "episode_number": 99, "year": 2022}',
        media_type="series",
        state="audited",
    )
    async_session.add(item)
    await async_session.commit()
    responses = {
        "/search/tv": {
            "status": 200,
            "data": {
                "results": [
                    {"id": 136315, "name": "The Bear", "first_air_date": "2022-06-23"}
                ]
            },
        },
        "/tv/136315/season/1/episode/99": {"status": 404, "data": {}},
    }
    client = httpx.AsyncClient(transport=MockTransport(responses))
    service = TVMetadataService(api_key="dummy", client=client)
    result = await service.fetch_series_metadata(async_session, "tv2")
    assert result is None
    db_item = await async_session.get(MediaItem, "tv2")
    assert db_item.metadata_mismatch is True


@pytest.mark.asyncio
async def test_tv_enrichment_series_not_found(async_session: AsyncSession):
    item = MediaItem(
        id="tv3",
        source_path="/input/tv/UnknownShow.S01E01.mkv",
        enrichment_data='{"series_title": "UnknownShow", "season_number": 1, "episode_number": 1}',
        media_type="series",
        state="audited",
    )
    async_session.add(item)
    await async_session.commit()
    responses = {"/search/tv": {"status": 200, "data": {"results": []}}}
    client = httpx.AsyncClient(transport=MockTransport(responses))
    service = TVMetadataService(api_key="dummy", client=client)
    result = await service.fetch_series_metadata(async_session, "tv3")
    assert result is None
    db_item = await async_session.get(MediaItem, "tv3")
    assert db_item.metadata_mismatch is True


@pytest.mark.asyncio
async def test_tv_enrichment_caching(async_session: AsyncSession):
    # First call populates cache
    item1 = MediaItem(
        id="tv4",
        source_path="/input/tv/The.Bear.S01E01.mkv",
        enrichment_data='{"series_title": "The Bear", "season_number": 1, "episode_number": 1, "year": 2022}',
        media_type="series",
        state="audited",
    )
    item2 = MediaItem(
        id="tv5",
        source_path="/input/tv/The.Bear.S01E02.mkv",
        enrichment_data='{"series_title": "The Bear", "season_number": 1, "episode_number": 2, "year": 2022}',
        media_type="series",
        state="audited",
    )
    async_session.add_all([item1, item2])
    await async_session.commit()
    responses = {
        "/search/tv": {
            "status": 200,
            "data": {
                "results": [
                    {"id": 136315, "name": "The Bear", "first_air_date": "2022-06-23"}
                ]
            },
        },
        "/tv/136315/season/1/episode/1": {
            "status": 200,
            "data": {
                "name": "System",
                "episode_number": 1,
                "overview": "Carmy returns to Chicago.",
            },
        },
        "/tv/136315/season/1/episode/2": {
            "status": 200,
            "data": {
                "name": "Hands",
                "episode_number": 2,
                "overview": "Chaos in the kitchen.",
            },
        },
    }
    client = httpx.AsyncClient(transport=MockTransport(responses))
    service = TVMetadataService(api_key="dummy", client=client)
    # First call (should search)
    await service.fetch_series_metadata(async_session, "tv4")
    # Second call (should use cache, not call /search/tv again)
    await service.fetch_series_metadata(async_session, "tv5")
    # Only one /search/tv call should be made
    search_calls = [c for c in service.client._transport.calls if "/search/tv" in c]
    assert len(search_calls) == 1
    db_item2 = await async_session.get(MediaItem, "tv5")
    assert db_item2.canonical_series_name == "The Bear"
    assert db_item2.episode_title == "Hands"
    assert db_item2.absolute_number == 2
    assert db_item2.tmdb_series_id == 136315
    assert db_item2.state == "ready_to_plan"
    assert db_item2.metadata_mismatch is False
