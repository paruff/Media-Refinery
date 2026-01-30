import pytest
from app.models.media import MediaItem, MediaType, PlanStatus
from app.services.music_planner import MusicPlanningService


@pytest.mark.asyncio
async def test_music_planner_creates_plan_integration(async_session):
    item = MediaItem(
        id="music_integ1",
        source_path="/input/DaftPunk-Discovery-01.flac",
        media_type=MediaType.music,
        album_artist="Daft Punk",
        artist="Daft Punk",
        album_name="Discovery",
        release_year=2001,
        disc_number=1,
        title="One More Time",
        container="flac",
        state="planned",
    )
    item.track_number = 1
    async_session.add(item)
    await async_session.commit()
    planner = MusicPlanningService(async_session)
    plan = await planner.create_plan("music_integ1")
    assert (
        plan.target_path
        == "/output/music/Daft Punk/2001 - Discovery/01 - One More Time.flac"
    )
    assert plan.plan_status == PlanStatus.draft
    assert plan.needs_tagging is True
    assert plan.needs_transcode is False
    assert plan.needs_rename is True


@pytest.mark.asyncio
async def test_music_planner_multidisc(async_session):
    item = MediaItem(
        id="music_integ2",
        source_path="/input/DaftPunk-Discovery-Disc2-01.flac",
        media_type=MediaType.music,
        album_artist="Daft Punk",
        artist="Daft Punk",
        album_name="Discovery",
        release_year=2001,
        disc_number=2,
        title="Aerodynamic",
        container="flac",
        state="planned",
    )
    item.track_number = 1
    async_session.add(item)
    await async_session.commit()
    planner = MusicPlanningService(async_session)
    plan = await planner.create_plan("music_integ2")
    assert (
        plan.target_path
        == "/output/music/Daft Punk/2001 - Discovery/Disc 02/01 - Aerodynamic.flac"
    )
    assert plan.needs_tagging is True


@pytest.mark.asyncio
async def test_music_planner_handles_missing_item(async_session):
    planner = MusicPlanningService(async_session)
    with pytest.raises(ValueError, match="MediaItem not found or not music"):
        await planner.create_plan("nonexistent_id")
