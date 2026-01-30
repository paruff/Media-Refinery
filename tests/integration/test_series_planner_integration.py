import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.media import Base, MediaItem, MediaType
from app.services.series_planner import SeriesPlanningService
import uuid


@pytest.mark.asyncio
async def test_series_planner_integration():
    # Setup in-memory SQLite DB
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        # Insert a MediaItem
        media_id = str(uuid.uuid4())
        item = MediaItem(
            id=media_id,
            media_type=MediaType.series,
            canonical_series_name="The Bear",
            release_year=2022,
            episode_title="System",
            container="mkv",
            video_codec="h264",
            audio_codec="aac",
            source_path="/input/thebear.s01e02.mkv",
        )
        # Set season_number and episode_number as attributes for planner logic (not DB columns)
        item.season_number = 1
        item.episode_number = 2
        session.add(item)
        await session.commit()
        # Plan
        planner = SeriesPlanningService(session)
        plan = await planner.create_plan(media_id)
        assert plan.target_path.endswith(
            "/output/series/The Bear (2022)/Season 01/The Bear (2022) - S01E02 - System.mkv"
        )
        assert plan.media_item_id == media_id
        assert plan.plan_status.name == "draft"
        # Check DB
        result = await session.get(type(plan), plan.id)
        assert result is not None
        assert result.target_path == plan.target_path
        assert result.ffmpeg_args == plan.ffmpeg_args
        # MediaItem state updated
        updated_item = await session.get(MediaItem, media_id)
        assert updated_item.state == "planned"
