import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.series_planner import SeriesPlanningService
from app.models.media import MediaItem, MediaType, PlanStatus


@pytest.mark.asyncio
async def test_series_plan_basic_path():
    db = AsyncMock()
    # Mock MediaItem for a standard episode
    item = MediaItem(
        id="testid",
        media_type=MediaType.series,
        canonical_series_name="The Bear",
        release_year=2022,
        episode_title="System",
        container="mkv",
        video_codec="h264",
        audio_codec="aac",
        source_path="/input/thebear.s01e02.mkv",
    )
    item.season_number = 1
    item.episode_number = 2
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: item))
    db.add = MagicMock()
    db.commit = AsyncMock()

    planner = SeriesPlanningService(db)
    plan = await planner.create_plan("testid")
    assert plan.target_path.endswith(
        "/output/series/The Bear (2022)/Season 01/The Bear (2022) - S01E02 - System.mkv"
    )
    assert plan.plan_status == PlanStatus.draft
    assert plan.needs_rename is True
    assert plan.needs_transcode is False
    assert "-c:v" in plan.ffmpeg_args
    assert "-c:a" in plan.ffmpeg_args


@pytest.mark.asyncio
async def test_series_plan_specials():
    db = AsyncMock()
    item = MediaItem(
        id="testid2",
        media_type=MediaType.series,
        canonical_series_name="Doctor Who",
        release_year=2005,
        episode_title="Christmas Special",
        container="mkv",
        video_codec="mpeg2",
        audio_codec="dts",
        source_path="/input/drwho.special.mkv",
    )
    item.season_number = 0
    item.episode_number = 1
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: item))
    db.add = MagicMock()
    db.commit = AsyncMock()
    planner = SeriesPlanningService(db)
    plan = await planner.create_plan("testid2")
    assert "/Season 00/" in plan.target_path
    # Allow 'Special' in filename, but not in the directory path
    import os

    dir_path, file_name = os.path.split(plan.target_path)
    assert "Special" not in dir_path  # Should be Season 00
    assert "libx264" in plan.ffmpeg_args
    assert "aac" in plan.ffmpeg_args
    assert plan.needs_transcode is True


@pytest.mark.asyncio
async def test_series_plan_multi_episode():
    db = AsyncMock()
    item = MediaItem(
        id="testid3",
        media_type=MediaType.series,
        canonical_series_name="Friends",
        release_year=1999,
        episode_title="The One with Ross's Wedding",
        container="mkv",
        video_codec="h264",
        audio_codec="aac",
        source_path="/input/friends.s05e01e02.mkv",
    )
    item.season_number = 5
    item.episode_number = 1
    item.episode_end = 2
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: item))
    db.add = MagicMock()
    db.commit = AsyncMock()
    planner = SeriesPlanningService(db)
    plan = await planner.create_plan("testid3")
    assert "S05E01-E02" in plan.target_path
    assert plan.needs_transcode is False
    assert plan.plan_status == PlanStatus.draft


@pytest.mark.asyncio
async def test_series_plan_invalid_type():
    db = AsyncMock()
    item = MediaItem(
        id="testid4",
        media_type=MediaType.movie,
        canonical_series_name="NotASeries",
        release_year=2020,
        episode_title="Not an Episode",
        container="mkv",
        video_codec="h264",
        audio_codec="aac",
        source_path="/input/notaseries.mkv",
    )
    item.season_number = 1
    item.episode_number = 1
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: item))
    db.add = MagicMock()
    db.commit = AsyncMock()
    planner = SeriesPlanningService(db)
    with pytest.raises(ValueError):
        await planner.create_plan("testid4")
