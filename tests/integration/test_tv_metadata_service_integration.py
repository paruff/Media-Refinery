import pytest
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.tv_metadata import TVMetadataService
from app.models.media import MediaItem


@pytest.mark.asyncio
async def test_tv_integration_enriches_episode(async_session: AsyncSession):
    item = MediaItem(
        id="tvint1",
        source_path="/input/tv/The.Bear.S01E01.mkv",
        enrichment_data='{"series_title": "The Bear", "season_number": 1, "episode_number": 1, "year": 2022}',
        media_type="series",
        state="audited",
    )
    async_session.add(item)
    await async_session.commit()

    class MockTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            if "/search/tv" in str(request.url):
                return httpx.Response(
                    200,
                    json={
                        "results": [
                            {
                                "id": 136315,
                                "name": "The Bear",
                                "first_air_date": "2022-06-23",
                            }
                        ]
                    },
                )
            if "/tv/136315/season/1/episode/1" in str(request.url):
                return httpx.Response(
                    200,
                    json={
                        "name": "System",
                        "episode_number": 1,
                        "overview": "Carmy returns to Chicago.",
                    },
                )
            return httpx.Response(404, json={})

    client = httpx.AsyncClient(transport=MockTransport())
    service = TVMetadataService(api_key="dummy", client=client)
    result = await service.fetch_series_metadata(async_session, "tvint1")
    assert result["canonical_series_name"] == "The Bear"
    db_item = await async_session.get(MediaItem, "tvint1")
    assert db_item.episode_title == "System"
    assert db_item.absolute_number == 1
    assert db_item.tmdb_series_id == 136315
    assert db_item.state == "ready_to_plan"
    assert db_item.metadata_mismatch is False


@pytest.mark.asyncio
async def test_tv_integration_episode_not_found(async_session: AsyncSession):
    item = MediaItem(
        id="tvint2",
        source_path="/input/tv/The.Bear.S01E99.mkv",
        enrichment_data='{"series_title": "The Bear", "season_number": 1, "episode_number": 99, "year": 2022}',
        media_type="series",
        state="audited",
    )
    async_session.add(item)
    await async_session.commit()

    class MockTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            if "/search/tv" in str(request.url):
                return httpx.Response(
                    200,
                    json={
                        "results": [
                            {
                                "id": 136315,
                                "name": "The Bear",
                                "first_air_date": "2022-06-23",
                            }
                        ]
                    },
                )
            if "/tv/136315/season/1/episode/99" in str(request.url):
                return httpx.Response(404, json={})
            return httpx.Response(404, json={})

    client = httpx.AsyncClient(transport=MockTransport())
    service = TVMetadataService(api_key="dummy", client=client)
    result = await service.fetch_series_metadata(async_session, "tvint2")
    assert result is None
    db_item = await async_session.get(MediaItem, "tvint2")
    assert db_item.metadata_mismatch is True
