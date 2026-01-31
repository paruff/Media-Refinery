from unittest.mock import patch, MagicMock
from app.services.fingerprint_service import FingerprintService


def test_fingerprint_audio_success():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout='{"fingerprint": "abc123"}', returncode=0
        )
        fp = FingerprintService.fingerprint_audio("test.mp3")
        assert fp == "abc123"


def test_fingerprint_audio_failure():
    with patch("subprocess.run", side_effect=Exception("fail")):
        fp = FingerprintService.fingerprint_audio("test.mp3")
        assert fp is None


def test_fingerprint_video_success():
    with (
        patch("cv2.VideoCapture") as mock_cv2,
        patch("imagehash.phash", return_value="phash123"),
        patch("PIL.Image.fromarray"),
    ):
        mock_cap = MagicMock()
        mock_cap.read.return_value = (True, "frame")
        mock_cv2.return_value = mock_cap
        fp = FingerprintService.fingerprint_video("test.mp4")
        assert fp == "phash123"


def test_fingerprint_video_failure():
    with patch("cv2.VideoCapture") as mock_cv2:
        mock_cap = MagicMock()
        mock_cap.read.return_value = (False, None)
        mock_cv2.return_value = mock_cap
        fp = FingerprintService.fingerprint_video("test.mp4")
        assert fp is None
