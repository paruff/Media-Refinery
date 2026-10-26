"""Tests for repair module."""

from pathlib import Path
from unittest.mock import Mock, patch

from app.media.video.repair import (
    RepairDispatcher,
    repair_h264_avi,
    repair_mpeg,
    repair_mpeg2,
    repair_wmv,
    repair_xvid,
)


class TestRepairMpeg:
    """Tests for repair_mpeg function."""

    def test_repair_mpeg(self):
        """Test MPEG-1 repair."""
        input_path = Path("/test/video.mpg")

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = repair_mpeg(input_path)

        assert result.name == "video_fixed.mkv"


class TestRepairMpeg2:
    """Tests for repair_mpeg2 function."""

    def test_repair_mpeg2(self):
        """Test MPEG-2 repair."""
        input_path = Path("/test/video.mpg")

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = repair_mpeg2(input_path)

        assert result.name == "video_fixed.mkv"


class TestRepairWmv:
    """Tests for repair_wmv function."""

    def test_repair_wmv(self):
        """Test WMV repair."""
        input_path = Path("/test/video.wmv")

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = repair_wmv(input_path)

        assert result.name == "video_fixed.mkv"


class TestRepairXvid:
    """Tests for repair_xvid function."""

    def test_repair_xvid(self):
        """Test XviD repair."""
        input_path = Path("/test/video.avi")

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = repair_xvid(input_path)

        assert result.name == "video_fixed.avi"


class TestRepairH264Avi:
    """Tests for repair_h264_avi function."""

    def test_repair_h264_avi(self):
        """Test H.264-in-AVI repair."""
        input_path = Path("/test/video.avi")

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = repair_h264_avi(input_path)

        assert result.name == "video_fixed.mkv"


class TestRepairDispatcher:
    """Tests for RepairDispatcher class."""

    def test_needs_repair_mpeg1(self):
        """Test needs_repair for MPEG-1."""
        dispatcher = RepairDispatcher()
        assert dispatcher.needs_repair("mpeg1") is True

    def test_needs_repair_mpeg2(self):
        """Test needs_repair for MPEG-2."""
        dispatcher = RepairDispatcher()
        assert dispatcher.needs_repair("mpeg2") is True

    def test_needs_repair_wmv(self):
        """Test needs_repair for WMV."""
        dispatcher = RepairDispatcher()
        assert dispatcher.needs_repair("wmv") is True

    def test_needs_repair_xvid(self):
        """Test needs_repair for XviD."""
        dispatcher = RepairDispatcher()
        assert dispatcher.needs_repair("xvid") is True

    def test_needs_repair_h264(self):
        """Test needs_repair for H.264-in-AVI."""
        dispatcher = RepairDispatcher()
        assert dispatcher.needs_repair("h264") is True

    def test_needs_repair_other(self):
        """Test needs_repair for unsupported codec."""
        dispatcher = RepairDispatcher()
        assert dispatcher.needs_repair("other") is False

    def test_dispatch_mpeg1(self):
        """Test dispatch for MPEG-1."""
        dispatcher = RepairDispatcher()
        input_path = Path("/test/video.mpg")
        stream = {"codec_name": "mpeg1video"}

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = dispatcher.dispatch(input_path, stream)

        assert result.name == "video_fixed.mkv"

    def test_dispatch_mpeg2(self):
        """Test dispatch for MPEG-2."""
        dispatcher = RepairDispatcher()
        input_path = Path("/test/video.mpg")
        stream = {"codec_name": "mpeg2video"}

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = dispatcher.dispatch(input_path, stream)

        assert result.name == "video_fixed.mkv"

    def test_dispatch_wmv(self):
        """Test dispatch for WMV."""
        dispatcher = RepairDispatcher()
        input_path = Path("/test/video.wmv")
        stream = {"codec_name": "wmv3"}

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = dispatcher.dispatch(input_path, stream)

        assert result.name == "video_fixed.mkv"

    def test_dispatch_xvid(self):
        """Test dispatch for XviD."""
        dispatcher = RepairDispatcher()
        input_path = Path("/test/video.avi")
        stream = {"codec_name": "mpeg4"}

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = dispatcher.dispatch(input_path, stream)

        assert result.name == "video_fixed.avi"

    def test_dispatch_h264_avi(self):
        """Test dispatch for H.264-in-AVI."""
        dispatcher = RepairDispatcher()
        input_path = Path("/test/video.avi")
        stream = {"codec_name": "h264"}

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = dispatcher.dispatch(input_path, stream)

        assert result.name == "video_fixed.mkv"

    def test_dispatch_no_repair_needed(self):
        """Test dispatch for codec that doesn't need repair."""
        dispatcher = RepairDispatcher()
        input_path = Path("/test/video.mp4")
        stream = {"codec_name": "vp9"}

        result = dispatcher.dispatch(input_path, stream)

        assert result == input_path
