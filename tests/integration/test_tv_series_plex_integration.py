import pytest
from app.models.media import MediaItem, FileState, MediaType
from app.services.auditor import IssueDetectorService


@pytest.mark.asyncio
async def test_tv_series_full_integration(async_session):
    # Simulate a full TV series season with multiple episodes
    show = "Show Name"
    season = "Season 01"
    base = f"/TV/{show}/{season}/"
    files = [
        MediaItem(
            id=f"ep{i}",
            source_path=f"{base}{show} - S01E{str(i).zfill(2)} - Ep{i}.mkv",
            state=FileState.enriched,
            media_type=MediaType.series,
            video_codec="h264",
            audio_codec="aac",
            subtitle_format="srt",
        )
        for i in range(1, 4)
    ]
    for item in files:
        async_session.add(item)
    await async_session.commit()
    auditor = IssueDetectorService(async_session)
    for item in files:
        issues, _ = await auditor.audit(item.id)
        assert not issues  # All should be compliant


@pytest.mark.asyncio
async def test_tv_series_with_issues(async_session):
    # Simulate a file with bad codecs and image-based subtitles
    item = MediaItem(
        id="bad1",
        source_path="/TV/Show Name/Season 01/Show Name - S01E01.mkv",
        state=FileState.enriched,
        media_type=MediaType.series,
        video_codec="mpeg2",
        audio_codec="mp2",
        subtitle_format="pgs",
    )
    async_session.add(item)
    await async_session.commit()
    auditor = IssueDetectorService(async_session)
    issues, _ = await auditor.audit("bad1")
    codes = {i["code"] for i in issues}
    assert "UNSUPPORTED_VIDEO_CODEC" in codes
    assert "UNSUPPORTED_AUDIO_CODEC" in codes
    assert "IMAGE_BASED_SUBTITLE" in codes
