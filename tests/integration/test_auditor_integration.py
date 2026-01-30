import asyncio
import json
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.media import Base, MediaItem, FileState, MediaType
from app.services.auditor import IssueDetectorService

@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop

@pytest.fixture(scope="module")
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        yield session
    await engine.dispose()

@pytest.mark.asyncio
async def test_auditor_detects_multiple_issues(db):
    item = MediaItem(
        id="multi1",
        source_path="/media/Bad:Movie.2010.mkv",
        state=FileState.enriched,
        media_type=MediaType.movie,
        video_codec="vc-1",
        audio_codec="dts-hd",
        container="avi"
    )
    db.add(item)
    await db.commit()
    auditor = IssueDetectorService(db)
    issues, status = await auditor.audit("multi1")
    codes = {i["code"] for i in issues}
    assert "ILLEGAL_CHAR" in codes
    assert "UNSUPPORTED_VIDEO_CODEC" in codes
    assert "UNSUPPORTED_AUDIO_CODEC" in codes
    assert "HEAVY_CONTAINER" in codes
    assert status == "needs_fix"
    refreshed = await db.get(MediaItem, "multi1")
    assert refreshed.state == FileState.audited
    assert len(json.loads(refreshed.detected_issues)) >= 4

@pytest.mark.asyncio
async def test_auditor_integration_with_enrichment_data(db):
    enrichment = json.dumps({"artist": "Test Artist", "album": "Test Album", "track_title": "Test Song"})
    item = MediaItem(
        id="music1",
        source_path="/music/01 - Test Song.flac",
        state=FileState.enriched,
        media_type=MediaType.music,
        enrichment_data=enrichment
    )
    db.add(item)
    await db.commit()
    auditor = IssueDetectorService(db)
    issues, status = await auditor.audit("music1")
    codes = {i["code"] for i in issues}
    assert "MISSING_TRACK_NUMBER" in codes
    assert "MISSING_TAGS" in codes
    assert status == "needs_fix"
    refreshed = await db.get(MediaItem, "music1")
    assert refreshed.state == FileState.audited
    assert len(json.loads(refreshed.detected_issues)) >= 2

@pytest.mark.asyncio
async def test_auditor_performance(db):
    import time
    item = MediaItem(
        id="perf1",
        source_path="/media/FastAudit.2010.mkv",
        state=FileState.enriched,
        media_type=MediaType.movie,
        video_codec="h264",
        audio_codec="aac",
        container="mkv",
        year="2010"
    )
    db.add(item)
    await db.commit()
    auditor = IssueDetectorService(db)
    start = time.perf_counter()
    issues, status = await auditor.audit("perf1")
    elapsed = (time.perf_counter() - start) * 1000
    assert issues == []
    assert status == "ok"
    assert elapsed < 100, f"Audit took too long: {elapsed}ms"
