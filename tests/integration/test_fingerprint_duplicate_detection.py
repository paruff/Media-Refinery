import pytest
from unittest.mock import patch, MagicMock
from app.core.scanner import ScannerService
from app.models.media import MediaItem, FileState


class DummySession:
    def __init__(self, items):
        self.items = items
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def execute(self, query):
        # Simulate duplicate detection
        if hasattr(query, "where") and "audio_fingerprint" in str(query):
            for item in self.items:
                if item.audio_fingerprint == "dupfp" and item.id != "2":
                    # Simulate duplicate found, set state on new item
                    for i in self.items:
                        if i.id == "2":
                            i.state = FileState.error
                            i.error_log = (
                                "Duplicate audio fingerprint detected. Skipping."
                            )
                    return MagicMock(scalar_one_or_none=lambda: item)
        return MagicMock(scalar_one_or_none=lambda: None)

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_duplicate_audio_detection():
    # Existing item with fingerprint
    existing = MediaItem(id="1", source_path="old.mp3")
    existing.audio_fingerprint = "dupfp"
    # New item to scan
    new = MediaItem(id="2", source_path="new.mp3")
    items = [existing, new]

    def session_factory():
        return DummySession(items)

    scanner = ScannerService(session_factory)
    with patch(
        "app.services.fingerprint_service.FingerprintService.fingerprint_audio",
        return_value="dupfp",
    ):
        await scanner.run("2")
    assert new.state == FileState.error
    assert "Duplicate audio fingerprint" in (new.error_log or "")
