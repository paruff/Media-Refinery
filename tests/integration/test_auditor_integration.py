import json
import pytest
from app.models.media import MediaItem, FileState, MediaType
from app.services.auditor import IssueDetectorService


@pytest.mark.asyncio
async def test_auditor_detects_multiple_issues(async_session):
    item = MediaItem(
        id="multi1",
        source_path="/media/Bad:Movie.2010.mkv",
        state=FileState.enriched,
        media_type=MediaType.movie,
        video_codec="vc-1",
        audio_codec="dts-hd",
        container="avi",
    )
    async_session.add(item)
    await async_session.commit()
    auditor = IssueDetectorService(async_session)
    issues, status = await auditor.audit("multi1")
    codes = {i["code"] for i in issues}
    assert "ILLEGAL_CHAR" in codes
    assert "UNSUPPORTED_VIDEO_CODEC" in codes
    assert "UNSUPPORTED_AUDIO_CODEC" in codes
    assert "HEAVY_CONTAINER" in codes
    assert status == "needs_fix"
    refreshed = await async_session.get(MediaItem, "multi1")
    assert refreshed.state == FileState.audited
    assert len(json.loads(refreshed.detected_issues)) >= 4


@pytest.mark.asyncio
async def test_auditor_integration_with_enrichment_data(async_session):
    enrichment = json.dumps(
        {"artist": "Test Artist", "album": "Test Album", "track_title": "Test Song"}
    )
    item = MediaItem(
        id="music1",
        source_path="/music/01 - Test Song.flac",
        state=FileState.enriched,
        media_type=MediaType.music,
        enrichment_data=enrichment,
    )
    async_session.add(item)
    await async_session.commit()
    auditor = IssueDetectorService(async_session)
    issues, status = await auditor.audit("music1")
    codes = {i["code"] for i in issues}
    assert "MISSING_TRACK_NUMBER" in codes
    assert "MISSING_TAGS" in codes
    assert status == "needs_fix"
    refreshed = await async_session.get(MediaItem, "music1")
    assert refreshed.state == FileState.audited
    assert len(json.loads(refreshed.detected_issues)) >= 2


@pytest.mark.asyncio
async def test_auditor_performance(async_session):
    import time

    item = MediaItem(
        id="perf1",
        source_path="/media/FastAudit.2010.mkv",
        state=FileState.enriched,
        media_type=MediaType.movie,
        video_codec="h264",
        audio_codec="aac",
        container="mkv",
        year="2010",
    )
    async_session.add(item)
    await async_session.commit()
    auditor = IssueDetectorService(async_session)
    start = time.perf_counter()
    issues, status = await auditor.audit("perf1")
    elapsed = (time.perf_counter() - start) * 1000
    assert issues == []
    assert status == "ok"
    assert elapsed < 100, f"Audit took too long: {elapsed}ms"
