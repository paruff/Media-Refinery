import pytest
from app.models.media import MediaItem, MediaType, PlanStatus
from app.services.movie_planner import MoviePlanningService


@pytest.mark.asyncio
async def test_movie_planner_creates_plan_integration(async_session):
    item = MediaItem(
        id="movie_integ1",
        source_path="/input/Matrix.1999.DTS-HD.mkv",
        media_type=MediaType.movie,
        title="The Matrix",
        year="1999",
        video_codec="h264",
        audio_codec="dts-hd",
        container="mkv",
        state="planned",
    )
    async_session.add(item)
    await async_session.commit()
    planner = MoviePlanningService(async_session)
    plan = await planner.create_plan("movie_integ1")
    assert plan.target_path == "/output/movies/The Matrix (1999)/The Matrix (1999).mkv"
    assert "-c:a" in plan.ffmpeg_args and "aac" in plan.ffmpeg_args
    assert plan.status == PlanStatus.planned


@pytest.mark.asyncio
async def test_movie_planner_handles_missing_item(async_session):
    planner = MoviePlanningService(async_session)
    plan = await planner.create_plan("nonexistent_id")
    assert plan is None


@pytest.mark.asyncio
async def test_movie_planner_integration_transcode(async_session):
    item = MediaItem(
        id="movie_integ2",
        source_path="/input/Classic.1980.VC1.DTS.mkv",
        media_type=MediaType.movie,
        title="Classic",
        year="1980",
        video_codec="vc-1",
        audio_codec="dts",
        container="mkv",
        state="planned",
    )
    async_session.add(item)
    await async_session.commit()
    planner = MoviePlanningService(async_session)
    plan = await planner.create_plan("movie_integ2")
    assert plan.target_path == "/output/movies/Classic (1980)/Classic (1980).mkv"
    assert "libx264" in plan.ffmpeg_args
    assert "-c:a" in plan.ffmpeg_args and "aac" in plan.ffmpeg_args
    assert plan.status == PlanStatus.planned
