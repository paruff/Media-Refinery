import pytest
import pytest_asyncio
import json
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.media import Base, MediaItem, FileState, MediaType
from app.services.auditor import IssueDetectorService


@pytest_asyncio.fixture(scope="function")
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    session = async_session()
    yield session
    await session.close()
    await engine.dispose()


@pytest.mark.asyncio
async def test_filename_rule(db):
    item = MediaItem(
        id="f1",
        source_path="/media/Bad:Movie.2010.mkv",
        state=FileState.enriched,
        media_type=MediaType.movie,
    )
    db.add(item)
    await db.commit()
    auditor = IssueDetectorService(db)
    issues, status = await auditor.audit("f1")
    assert any(i["code"] == "ILLEGAL_CHAR" for i in issues)
    refreshed = await db.get(MediaItem, "f1")
    assert refreshed.state == FileState.audited


@pytest.mark.asyncio
async def test_codec_rule(db):
    item = MediaItem(
        id="c1",
        source_path="/media/CodecTest.2010.mkv",
        state=FileState.enriched,
        media_type=MediaType.movie,
        video_codec="vc-1",
        audio_codec="dts-hd",
        container="avi",
    )
    db.add(item)
    await db.commit()
    auditor = IssueDetectorService(db)
    issues, status = await auditor.audit("c1")
    codes = {i["code"] for i in issues}
    assert "UNSUPPORTED_VIDEO_CODEC" in codes
    assert "UNSUPPORTED_AUDIO_CODEC" in codes
    assert "HEAVY_CONTAINER" in codes
    refreshed = await db.get(MediaItem, "c1")
    assert refreshed.state == FileState.audited


@pytest.mark.asyncio
async def test_subtitle_rule(db):
    item = MediaItem(
        id="s1",
        source_path="/media/NoSubs.2010.mkv",
        state=FileState.enriched,
        media_type=MediaType.movie,
    )
    db.add(item)
    await db.commit()
    auditor = IssueDetectorService(db)
    issues, status = await auditor.audit("s1")
    # The implementation emits 'MISSING_SUB_LANG' if has_subtitles and not subtitle_language
    # So we simulate that:
    item.has_subtitles = True
    item.subtitle_language = None
    await db.commit()
    issues, status = await auditor.audit("s1")
    assert any(i["code"] == "MISSING_SUB_LANG" for i in issues)
    refreshed = await db.get(MediaItem, "s1")
    assert refreshed.state == FileState.audited


@pytest.mark.asyncio
async def test_metadata_rule(db):
    enrichment = json.dumps(
        {"artist": "Test Artist", "album": "Test Album", "track_title": "Test Song"}
    )
    item = MediaItem(
        id="m1",
        source_path="/music/01 - Test Song.flac",
        state=FileState.enriched,
        media_type=MediaType.music,
        enrichment_data=enrichment,
    )
    db.add(item)
    await db.commit()
    auditor = IssueDetectorService(db)
    issues, status = await auditor.audit("m1")
    codes = {i["code"] for i in issues}
    assert "MISSING_TRACK_NUMBER" in codes
    assert "MISSING_TAGS" in codes
    refreshed = await db.get(MediaItem, "m1")
    assert refreshed.state == FileState.audited


@pytest.mark.asyncio
async def test_state_transitions(db):
    item = MediaItem(
        id="st1",
        source_path="/media/StateTest.2010.mkv",
        state=FileState.enriched,
        media_type=MediaType.movie,
    )
    db.add(item)
    await db.commit()
    auditor = IssueDetectorService(db)
    issues, status = await auditor.audit("st1")
    refreshed = await db.get(MediaItem, "st1")
    assert refreshed.state == FileState.audited
    # Re-audit should not change state
    issues2, status2 = await auditor.audit("st1")
    refreshed2 = await db.get(MediaItem, "st1")
    assert refreshed2.state == FileState.audited
