import json
import pytest
from app.models.media import MediaItem, FileState, MediaType
from app.services.classification import ClassificationService


@pytest.mark.asyncio
async def test_classification_state_transition(async_session):
    import mutagen.flac
    import tempfile
    import shutil

    # Use a real FLAC file if available, else skip test
    flac_path = tempfile.NamedTemporaryFile(suffix=".flac", delete=False).name
    try:
        # Write a minimal valid FLAC header to avoid mutagen errors
        with open(flac_path, "wb") as f:
            f.write(b"fLaC\x00\x00\x00\x22")
        audio = mutagen.flac.FLAC(flac_path)
        audio["artist"] = "Artist"
        audio["album"] = "Album"
        audio["title"] = "Test"
        audio["tracknumber"] = "2"
        audio.save(flac_path)
        item = MediaItem(id="int1", source_path=str(flac_path), state=FileState.scanned)
        async_session.add(item)
        await async_session.commit()
        classifier = ClassificationService(async_session)
        media_type, enrichment = await classifier.classify_file("int1")
        refreshed = await async_session.get(MediaItem, "int1")
        assert refreshed.state == FileState.enriched
        assert refreshed.media_type == MediaType.music
        data = json.loads(refreshed.enrichment_data)
        assert data["track_number"] == 2
    finally:
        shutil.rmtree(tempfile.gettempdir(), ignore_errors=True)
    async_session.add(item)
    await async_session.commit()
    classifier = ClassificationService(async_session)
    media_type, enrichment = await classifier.classify_file("int1")
    refreshed = await async_session.get(MediaItem, "int1")
    assert refreshed.state == FileState.enriched
    assert refreshed.media_type == MediaType.music
    data = json.loads(refreshed.enrichment_data)
    assert data["track_number"] == 2


@pytest.mark.asyncio
async def test_classification_logs_warning_for_unknown(async_session, caplog):
    item = MediaItem(
        id="int2", source_path="/media/unknownfile.abc", state=FileState.scanned
    )
    async_session.add(item)
    await async_session.commit()
    classifier = ClassificationService(async_session)
    with caplog.at_level("WARNING"):
        media_type, enrichment = await classifier.classify_file("int2")
        assert "Could not classify file" in caplog.text
    refreshed = await async_session.get(MediaItem, "int2")
    assert refreshed.media_type == MediaType.unknown
    assert refreshed.state == FileState.scanned


@pytest.mark.asyncio
async def test_classification_overwrites_existing_enrichment(async_session):
    item = MediaItem(
        id="int3",
        source_path="/media/Inception.2010.1080p.mkv",
        state=FileState.scanned,
        enrichment_data=json.dumps({"title": "OldTitle", "year": 1900}),
    )
    async_session.add(item)
    await async_session.commit()
    classifier = ClassificationService(async_session)
    media_type, enrichment = await classifier.classify_file("int3")
    refreshed = await async_session.get(MediaItem, "int3")
    data = json.loads(refreshed.enrichment_data)
    assert data["title"].lower() == "inception"
    assert int(data["year"]) == 2010
