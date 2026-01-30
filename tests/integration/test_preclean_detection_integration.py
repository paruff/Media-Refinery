import pytest
import json
from app.services.auditor import IssueDetectorService
from app.models.media import MediaItem, FileState, MediaType

@pytest.mark.asyncio
async def test_integration_detects_all_preclean_issues(db):
    # Movie missing year
    item1 = MediaItem(id="int1", source_path="/Media/NoYear.mkv", state=FileState.enriched, media_type=MediaType.movie)
    # Music missing tags
    item2 = MediaItem(id="int2", source_path="/Media/track.flac", state=FileState.enriched, media_type=MediaType.music)
    # File with illegal char
    item3 = MediaItem(id="int3", source_path="/Media/bad:file.mkv", state=FileState.enriched, media_type=MediaType.movie)
    # Unknown type
    item4 = MediaItem(id="int4", source_path="/Media/unknownfile.bin", state=FileState.enriched, media_type=MediaType.unknown)
    db.add_all([item1, item2, item3, item4])
    await db.commit()
    auditor = IssueDetectorService(db)
    issues1, _ = await auditor.audit("int1")
    issues2, _ = await auditor.audit("int2")
    issues3, _ = await auditor.audit("int3")
    issues4, _ = await auditor.audit("int4")
    assert any(i["code"] == "MISSING_YEAR" for i in issues1)
    assert any(i["code"] == "MISSING_TAGS" for i in issues2)
    assert any(i["code"] == "ILLEGAL_CHAR" for i in issues3)
    assert any(i["code"] == "UNKNOWN_TYPE" for i in issues4)

@pytest.mark.asyncio
async def test_integration_auditor_commits_detected_issues(db):
    item = MediaItem(id="int5", source_path="/Media/Bad:File.mkv", state=FileState.enriched, media_type=MediaType.movie)
    db.add(item)
    await db.commit()
    auditor = IssueDetectorService(db)
    issues, _ = await auditor.audit("int5")
    refreshed = await db.get(MediaItem, "int5")
    assert refreshed.state == FileState.audited
    decoded = json.loads(refreshed.detected_issues)
    assert any(i["code"] == "ILLEGAL_CHAR" for i in decoded)
