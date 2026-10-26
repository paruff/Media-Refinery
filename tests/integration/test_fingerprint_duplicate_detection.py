from unittest.mock import MagicMock, patch

import pytest

from app.core.scanner import ScannerService
from app.models.media import FileState, MediaItem


@pytest.mark.asyncio
async def test_duplicate_audio_detection(async_session, make_audio, tmp_path):
    song = make_audio(tmp_path / "new.mp3")
    existing = MediaItem(id="1", source_path="old.mp3", audio_fingerprint="dupfp")
    new = MediaItem(id="2", source_path=str(song), state=FileState.scanning)
    async_session.add_all([existing, new])
    await async_session.commit()

    factory = MagicMock()
    factory.return_value.__aenter__.return_value = async_session
    factory.return_value.__aexit__.return_value = False
    with patch(
        "app.services.fingerprint_service.FingerprintService.fingerprint_audio",
        return_value="dupfp",
    ):
        await ScannerService(factory).run("2")

    assert new.state == FileState.error
    assert "Duplicate audio fingerprint" in (new.error_log or "")
