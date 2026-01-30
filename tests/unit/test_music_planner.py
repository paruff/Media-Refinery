import pytest
from unittest.mock import AsyncMock, MagicMock
from app.models.media import MediaItem, MediaType, PlanStatus
from app.services.music_planner import MusicPlanningService


@pytest.mark.asyncio
async def test_music_planner_path_and_tagging():
    # Mock DB session
    db = MagicMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    # MediaItem with all fields
    item = MediaItem(
        id="unit1",
        source_path="/input/Artist-Album-01.flac",
        media_type=MediaType.music,
        album_artist="Test Artist",
        artist="Test Artist",
        album_name="Test Album",
        release_year=1984,
        disc_number=1,
        title="Test Track",
        container="flac",
        state="planned",
    )
    item.track_number = 5
    # Patch DB execute to return item
    db.execute.return_value.scalar_one_or_none = lambda: item
    planner = MusicPlanningService(db)
    plan = await planner.create_plan("unit1")
    assert (
        plan.target_path
        == "/output/music/Test Artist/1984 - Test Album/05 - Test Track.flac"
    )
    assert plan.needs_tagging is True
    assert plan.needs_transcode is False
    assert plan.plan_status == PlanStatus.draft
    assert plan.needs_rename is True


@pytest.mark.asyncio
async def test_music_planner_multidisc_path():
    db = MagicMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    item = MediaItem(
        id="unit2",
        source_path="/input/Artist-Album-Disc2-01.flac",
        media_type=MediaType.music,
        album_artist="Test Artist",
        artist="Test Artist",
        album_name="Test Album",
        release_year=1984,
        disc_number=2,
        title="Disc2 Track",
        container="flac",
        state="planned",
    )
    item.track_number = 1
    db.execute.return_value.scalar_one_or_none = lambda: item
    planner = MusicPlanningService(db)
    plan = await planner.create_plan("unit2")
    assert (
        plan.target_path
        == "/output/music/Test Artist/1984 - Test Album/Disc 02/01 - Disc2 Track.flac"
    )
    assert plan.needs_tagging is True


@pytest.mark.asyncio
async def test_music_planner_missing_fields():
    db = MagicMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    item = MediaItem(
        id="unit3",
        source_path="/input/Unknown.flac",
        media_type=MediaType.music,
        state="planned",
    )
    item.track_number = 0
    db.execute.return_value.scalar_one_or_none = lambda: item
    planner = MusicPlanningService(db)
    plan = await planner.create_plan("unit3")
    # Should fallback to Unknowns and 00
    assert (
        plan.target_path
        == "/output/music/Unknown Artist/0000 - Unknown Album/00 - Unknown Title.flac"
    )
    assert plan.needs_tagging is True


@pytest.mark.asyncio
async def test_music_planner_not_music():
    db = MagicMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    item = MediaItem(
        id="unit4",
        source_path="/input/NotMusic.mkv",
        media_type=MediaType.movie,
        state="planned",
    )
    db.execute.return_value.scalar_one_or_none = lambda: item
    planner = MusicPlanningService(db)
    with pytest.raises(ValueError, match="MediaItem not found or not music"):
        await planner.create_plan("unit4")


@pytest.mark.asyncio
async def test_music_planner_missing_item():
    db = MagicMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.execute.return_value.scalar_one_or_none = lambda: None
    planner = MusicPlanningService(db)
    with pytest.raises(ValueError, match="MediaItem not found or not music"):
        await planner.create_plan("missing")
