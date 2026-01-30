import pytest
from app.models.media import MediaItem, FileState, MediaType
from app.services.auditor import IssueDetectorService
import json

@pytest.mark.asyncio
def test_movie_directory_layout(db):
    item = MediaItem(id="m1", source_path="/movies/Inception (2010)/Inception (2010).mkv", state=FileState.enriched, media_type=MediaType.movie)
    db.add(item)
    await db.commit()
    # Directory structure check
    assert "/movies/Inception (2010)/" in item.source_path
    fname = item.source_path.split("/")[-1]
    assert fname.startswith("Inception (2010)")
    assert fname.endswith(".mkv")

@pytest.mark.asyncio
def test_movie_supported_codecs(db):
    item = MediaItem(id="m2", source_path="/movies/Inception (2010)/Inception (2010).mkv", state=FileState.enriched, media_type=MediaType.movie, video_codec="h264", audio_codec="aac")
    db.add(item)
    await db.commit()
    auditor = IssueDetectorService(db)
    issues, _ = await auditor.audit("m2")
    codes = {i["code"] for i in issues}
    assert "UNSUPPORTED_VIDEO_CODEC" not in codes
    assert "UNSUPPORTED_AUDIO_CODEC" not in codes

@pytest.mark.asyncio
def test_movie_unsupported_codecs(db):
    item = MediaItem(id="m3", source_path="/movies/Inception (2010)/Inception (2010).mkv", state=FileState.enriched, media_type=MediaType.movie, video_codec="mpeg2", audio_codec="mp2")
    db.add(item)
    await db.commit()
    auditor = IssueDetectorService(db)
    issues, _ = await auditor.audit("m3")
    codes = {i["code"] for i in issues}
    assert "UNSUPPORTED_VIDEO_CODEC" in codes
    assert "UNSUPPORTED_AUDIO_CODEC" in codes

@pytest.mark.asyncio
def test_movie_subtitle_compatibility(db):
    # Supported
    item = MediaItem(id="m4", source_path="/movies/Inception (2010)/Inception (2010).mkv", state=FileState.enriched, media_type=MediaType.movie, subtitle_format="srt")
    db.add(item)
    await db.commit()
    auditor = IssueDetectorService(db)
    issues, _ = await auditor.audit("m4")
    codes = {i["code"] for i in issues}
    assert "IMAGE_BASED_SUBTITLE" not in codes
    # Not supported
    item2 = MediaItem(id="m5", source_path="/movies/Inception (2010)/Inception (2010).mkv", state=FileState.enriched, media_type=MediaType.movie, subtitle_format="pgs")
    db.add(item2)
    await db.commit()
    issues2, _ = await auditor.audit("m5")
    codes2 = {i["code"] for i in issues2}
    assert "IMAGE_BASED_SUBTITLE" in codes2

@pytest.mark.asyncio
def test_movie_naming_and_year(db):
    item = MediaItem(id="m6", source_path="/movies/Inception (2010)/Inception (2010).mkv", state=FileState.enriched, media_type=MediaType.movie, year="2010")
    db.add(item)
    await db.commit()
    # Check year in filename and metadata
    fname = item.source_path.split("/")[-1]
    assert "2010" in fname
    assert item.year == "2010"
