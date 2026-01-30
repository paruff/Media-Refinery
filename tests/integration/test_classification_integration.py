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
async def test_classification_state_transition(db):
    import mutagen.flac
    flac_path = "/tmp/02 - Test.flac"
    audio = mutagen.flac.FLAC()
    audio["artist"] = "Artist"
    audio["album"] = "Album"
    audio["title"] = "Test"
    audio["tracknumber"] = "2"
    audio.save(str(flac_path))
    item = MediaItem(
        id="int1",
        source_path=str(flac_path),
        state=FileState.scanned
    )
    db.add(item)
    await db.commit()
    classifier = ClassificationService(db)
    media_type, enrichment = await classifier.classify_file("int1")
    refreshed = await db.get(MediaItem, "int1")
    assert refreshed.state == FileState.enriched
    assert refreshed.media_type == MediaType.music
    data = json.loads(refreshed.enrichment_data)
    assert data["track_number"] == 2

@pytest.mark.asyncio
async def test_classification_logs_warning_for_unknown(db, caplog):
    item = MediaItem(
        id="int2",
        source_path="/media/unknownfile.abc",
        state=FileState.scanned
    )
    db.add(item)
    await db.commit()
    classifier = ClassificationService(db)
    with caplog.at_level("WARNING"):
        media_type, enrichment = await classifier.classify_file("int2")
        assert "Could not classify file" in caplog.text
    refreshed = await db.get(MediaItem, "int2")
    assert refreshed.media_type == MediaType.unknown
    assert refreshed.state == FileState.scanned

@pytest.mark.asyncio
async def test_classification_overwrites_existing_enrichment(db):
    item = MediaItem(
        id="int3",
        source_path="/media/Inception.2010.1080p.mkv",
        state=FileState.scanned,
        enrichment_data=json.dumps({"title": "OldTitle", "year": 1900})
    )
    db.add(item)
    await db.commit()
    classifier = ClassificationService(db)
    media_type, enrichment = await classifier.classify_file("int3")
    refreshed = await db.get(MediaItem, "int3")
    data = json.loads(refreshed.enrichment_data)
    assert data["title"].lower() == "inception"
    assert int(data["year"]) == 2010
