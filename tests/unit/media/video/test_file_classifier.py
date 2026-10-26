"""Tests for file_classifier module."""

from app.media.video.file_classifier import classify_video


class TestClassifyVideo:
    """Tests for classify_video function."""

    def test_classify_h264(self):
        """Test classifying H.264 video."""
        stream = {"codec_name": "h264"}
        assert classify_video(stream) == "h264"

    def test_classify_mpeg1(self):
        """Test classifying MPEG-1 video."""
        stream = {"codec_name": "mpeg1video"}
        assert classify_video(stream) == "mpeg1"

    def test_classify_mpeg2(self):
        """Test classifying MPEG-2 video."""
        stream = {"codec_name": "mpeg2video"}
        assert classify_video(stream) == "mpeg2"

    def test_classify_xvid(self):
        """Test classifying XviD video."""
        stream = {"codec_name": "mpeg4"}
        assert classify_video(stream) == "xvid"

    def test_classify_wmv(self):
        """Test classifying WMV video."""
        stream = {"codec_name": "wmv3"}
        assert classify_video(stream) == "wmv"

    def test_classify_unknown(self):
        """Test classifying unknown codec."""
        stream = {"codec_name": "unknown"}
        assert classify_video(stream) == "other"

    def test_classify_missing_codec(self):
        """Test classifying stream with missing codec name."""
        stream = {}
        assert classify_video(stream) == "other"
