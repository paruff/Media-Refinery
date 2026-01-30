import asyncio
import json
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.media import Base, MediaItem, FileState, MediaType
from app.services.classification import ClassificationService

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
async def test_classify_movie(db):
    item = MediaItem(id="m1", source_path="/movies/Inception.2010.mkv", state=FileState.detected)
    db.add(item)
    await db.commit()
    classifier = ClassificationService(db)
    result = await classifier.classify("m1")
    refreshed = await db.get(MediaItem, "m1")
    assert refreshed.media_type == "movie"
    assert refreshed.state == FileState.enriched
    assert refreshed.enrichment_data is not None

@pytest.mark.asyncio
async def test_classify_series(db):
    item = MediaItem(id="s1", source_path="/tv/Breaking.Bad.S01E01.mkv", state=FileState.detected)
    db.add(item)
    await db.commit()
    classifier = ClassificationService(db)
    result = await classifier.classify("s1")
    refreshed = await db.get(MediaItem, "s1")
    assert refreshed.media_type == "series"
    assert refreshed.state == FileState.enriched
    assert refreshed.enrichment_data is not None

@pytest.mark.asyncio
async def test_classify_music(db):
    item = MediaItem(id="mu1", source_path="/music/01 - Song.flac", state=FileState.detected)
    db.add(item)
    await db.commit()
    classifier = ClassificationService(db)
    result = await classifier.classify("mu1")
    refreshed = await db.get(MediaItem, "mu1")
    assert refreshed.media_type == "music"
    assert refreshed.state == FileState.enriched
    assert refreshed.enrichment_data is not None

@pytest.mark.asyncio
async def test_classify_unknown(db):
    item = MediaItem(id="u1", source_path="/unknown/strange.filetype", state=FileState.detected)
    db.add(item)
    await db.commit()
    classifier = ClassificationService(db)
    result = await classifier.classify("u1")
    refreshed = await db.get(MediaItem, "u1")
    assert refreshed.media_type == "unknown"
    assert refreshed.state == FileState.enriched
    assert refreshed.enrichment_data is not None

@pytest.mark.asyncio
async def test_classify_regex_fallback(db):
    item = MediaItem(id="r1", source_path="/movies/SomeMovie.2020.avi", state=FileState.detected)
    db.add(item)
    await db.commit()
    classifier = ClassificationService(db)
    result = await classifier.classify("r1")
    refreshed = await db.get(MediaItem, "r1")
    assert refreshed.media_type in ("movie", "unknown")
    assert refreshed.state == FileState.enriched
    assert refreshed.enrichment_data is not None
