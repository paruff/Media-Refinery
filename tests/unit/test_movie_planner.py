import pytest
from app.models.media import MediaItem, MediaType, PlanStatus
from app.services.movie_planner import MoviePlanningService


@pytest.mark.asyncio
async def test_movie_planner_path_and_codec(async_session):
    item = MediaItem(
        id="movie1",
        source_path="/input/Inception.2010.DTS-HD.mkv",
        media_type=MediaType.movie,
        title="Inception",
        year="2010",
        video_codec="h264",
        audio_codec="dts-hd",
        container="mkv",
        state="planned",
    )
    async_session.add(item)
    await async_session.commit()
    planner = MoviePlanningService(async_session)
    plan = await planner.create_plan("movie1")
    assert plan.target_path == "/output/movies/Inception (2010)/Inception (2010).mkv"
    assert "-c:a" in plan.ffmpeg_args and "aac" in plan.ffmpeg_args
    assert plan.plan_status == PlanStatus.draft


@pytest.mark.asyncio
async def test_movie_planner_transcode_flags(async_session):
    item = MediaItem(
        id="movie2",
        source_path="/input/OldMovie.1999.VC1.DTS.mkv",
        media_type=MediaType.movie,
        title="Old:Movie",
        year="1999",
        video_codec="vc-1",
        audio_codec="dts",
        container="mkv",
        state="planned",
    )
    async_session.add(item)
    await async_session.commit()
    planner = MoviePlanningService(async_session)
    plan = await planner.create_plan("movie2")
    assert plan.target_path == "/output/movies/Old-Movie (1999)/Old-Movie (1999).mkv"
    assert "libx264" in plan.ffmpeg_args
    assert "-c:a" in plan.ffmpeg_args and "aac" in plan.ffmpeg_args
    assert plan.plan_status == PlanStatus.draft


@pytest.mark.asyncio
async def test_movie_planner_subtitle_flag(async_session):
    item = MediaItem(
        id="movie3",
        source_path="/input/PGSsubs.2015.mkv",
        media_type=MediaType.movie,
        title="PGSsubs",
        year="2015",
        video_codec="h264",
        audio_codec="aac",
        container="mkv",
        subtitles='["pgs"]',
        state="planned",
    )
    async_session.add(item)
    await async_session.commit()
    planner = MoviePlanningService(async_session)
    plan = await planner.create_plan("movie3")
    assert plan.needs_subtitle_conversion is True
    assert plan.plan_status == PlanStatus.draft
