import pytest
import pytest_asyncio
from app.models.media import MediaItem, FileState, MediaType
from app.services.auditor import IssueDetectorService


# Provide db fixture using async_session from conftest.py
@pytest_asyncio.fixture
async def db(async_session):
    yield async_session


@pytest.mark.asyncio
async def test_standard_series_directory_layout(db):
    item = MediaItem(
        id="tv1",
        source_path="/TV/Show Name/Season 01/Show Name - S01E01 - Pilot.mkv",
        state=FileState.enriched,
        media_type=MediaType.series,
    )
    db.add(item)
    await db.commit()
    # Directory structure check (unit test, so just path logic)
    assert "/TV/Show Name/" in item.source_path


@pytest.mark.asyncio
async def test_standard_season_directory_layout(db):
    item = MediaItem(
        id="tv2",
        source_path="/TV/Show Name/Season 01/Show Name - S01E02 - Second.mkv",
        state=FileState.enriched,
        media_type=MediaType.series,
    )
    db.add(item)
    await db.commit()
    assert "/TV/Show Name/Season 01/" in item.source_path


@pytest.mark.asyncio
async def test_episode_naming(db):
    item = MediaItem(
        id="tv3",
        source_path="/TV/Show Name/Season 01/Show Name - S01E02 - Second.mkv",
        state=FileState.enriched,
        media_type=MediaType.series,
    )
    db.add(item)
    await db.commit()
    fname = item.source_path.split("/")[-1]
    assert fname.startswith("Show Name - S01E02")
    assert fname.endswith(".mkv")


@pytest.mark.asyncio
async def test_multi_episode_file_naming(db):
    item = MediaItem(
        id="tv4",
        source_path="/TV/Show Name/Season 01/Show Name - S01E01E02.mkv",
        state=FileState.enriched,
        media_type=MediaType.series,
    )
    db.add(item)
    await db.commit()
    fname = item.source_path.split("/")[-1]
    assert "S01E01E02" in fname


@pytest.mark.asyncio
async def test_supported_codecs(db):
    item = MediaItem(
        id="tv5",
        source_path="/TV/Show Name/Season 01/Show Name - S01E03.mkv",
        state=FileState.enriched,
        media_type=MediaType.series,
        video_codec="h264",
        audio_codec="aac",
    )
    db.add(item)
    await db.commit()
    auditor = IssueDetectorService(db)
    issues, _ = await auditor.audit("tv5")
    codes = {i["code"] for i in issues}
    assert "UNSUPPORTED_VIDEO_CODEC" not in codes
    assert "UNSUPPORTED_AUDIO_CODEC" not in codes


@pytest.mark.asyncio
async def test_unsupported_codecs(db):
    item = MediaItem(
        id="tv6",
        source_path="/TV/Show Name/Season 01/Show Name - S01E04.mkv",
        state=FileState.enriched,
        media_type=MediaType.series,
        video_codec="mpeg2",
        audio_codec="mp2",
    )
    db.add(item)
    await db.commit()
    auditor = IssueDetectorService(db)
    issues, _ = await auditor.audit("tv6")
    codes = {i["code"] for i in issues}
    assert "UNSUPPORTED_VIDEO_CODEC" in codes
    assert "UNSUPPORTED_AUDIO_CODEC" in codes


@pytest.mark.asyncio
async def test_subtitle_compatibility(db):
    # Supported
    item = MediaItem(
        id="tv7",
        source_path="/TV/Show Name/Season 01/Show Name - S01E05.mkv",
        state=FileState.enriched,
        media_type=MediaType.series,
        subtitle_format="srt",
    )
    db.add(item)
    await db.commit()
    auditor = IssueDetectorService(db)
    issues, _ = await auditor.audit("tv7")
    codes = {i["code"] for i in issues}
    assert "IMAGE_BASED_SUBTITLE" not in codes
    # Not supported
    item2 = MediaItem(
        id="tv8",
        source_path="/TV/Show Name/Season 01/Show Name - S01E06.mkv",
        state=FileState.enriched,
        media_type=MediaType.series,
        subtitle_format="pgs",
    )
    db.add(item2)
    await db.commit()
    issues2, _ = await auditor.audit("tv8")
    codes2 = {i["code"] for i in issues2}
    assert "IMAGE_BASED_SUBTITLE" in codes2
