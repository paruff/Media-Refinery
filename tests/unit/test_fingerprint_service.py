from unittest.mock import MagicMock, patch

from app.services.fingerprint_service import FingerprintService


def test_fingerprint_audio_success():
    with (
        patch("shutil.which", return_value="/usr/bin/fpcalc"),
        patch("subprocess.run") as mock_run,
    ):
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
        patch("cv2.cvtColor"),
        patch("imagehash.phash", return_value="ph"),
        patch("PIL.Image.fromarray"),
    ):
        mock_cap = MagicMock()
        mock_cap.get.side_effect = lambda prop: 100 if prop == 7 else 10.0
        mock_cap.read.return_value = (True, "frame")
        mock_cv2.return_value = mock_cap
        fp = FingerprintService.fingerprint_video("test.mp4")
        assert fp == "10-ph-ph-ph-ph-ph"


def test_fingerprint_video_failure():
    with patch("cv2.VideoCapture") as mock_cv2:
        mock_cap = MagicMock()
        mock_cap.get.return_value = 100
        mock_cap.read.return_value = (False, None)
        mock_cv2.return_value = mock_cap
        fp = FingerprintService.fingerprint_video("test.mp4")
        assert fp is None
