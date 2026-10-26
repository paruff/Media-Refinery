"""Tests for ffprobe_utils module."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

from app.media.video.ffprobe_utils import probe


class TestProbe:
    """Tests for probe function."""

    def test_probe_success(self):
        """Test successful probe."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {
                "streams": [
                    {
                        "codec_type": "video",
                        "codec_name": "h264",
                        "width": 1920,
                        "height": 1080,
                    }
                ],
                "format": {"filename": "test.mp4"},
            }
        )

        with patch("subprocess.run", return_value=mock_result):
            result = probe(Path("test.mp4"))

        assert result is not None
        assert "streams" in result
        assert "format" in result
        assert result["streams"][0]["codec_name"] == "h264"

    def test_probe_failure(self):
        """Test probe failure."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error"

        with patch("subprocess.run", return_value=mock_result):
            result = probe(Path("nonexistent.mp4"))

        assert result is None

    def test_probe_invalid_json(self):
        """Test probe with invalid JSON output."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "invalid json"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = probe(Path("test.mp4"))

        # Should return None due to JSON parse error
        assert result is None

    def test_probe_dry_run(self):
        """Test probe in dry-run mode."""
        result = probe(Path("test.mp4"), dry_run=True)

        assert result is not None
        assert "streams" in result
        assert len(result["streams"]) == 1
        assert result["streams"][0]["codec_type"] == "video"
        assert result["streams"][0]["codec_name"] == "h264"

    def test_probe_missing_fields(self):
        """Test probe with missing required fields."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {
                "streams": [
                    {
                        "codec_type": "video",
                        # Missing codec_name, height, width, etc.
                    }
                ],
                "format": {},
            }
        )

        with patch("subprocess.run", return_value=mock_result):
            result = probe(Path("test.mp4"))

        # Should still return the data even with missing fields
        assert result is not None
        assert "streams" in result
        assert result["streams"][0]["codec_type"] == "video"

    def test_probe_corrupted_metadata_malformed(self):
        """Test probe with malformed metadata (incomplete JSON)."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = '{"streams": [{"codec_type": "video"'  # Incomplete JSON

        with patch("subprocess.run", return_value=mock_result):
            result = probe(Path("test.mp4"))

        # Should return None due to JSON parse error
        assert result is None

    def test_probe_corrupted_metadata_invalid_types(self):
        """Test probe with invalid data types in metadata."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {
                "streams": [
                    {
                        "codec_type": "video",
                        "codec_name": "h264",
                        "height": "not_a_number",  # Invalid type
                        "width": None,
                    }
                ],
                "format": {"bit_rate": "invalid"},
            }
        )

        with patch("subprocess.run", return_value=mock_result):
            result = probe(Path("test.mp4"))

        # Should still return the data; consumers will handle invalid types
        assert result is not None
        assert result["streams"][0]["height"] == "not_a_number"

    def test_probe_multiple_streams(self):
        """Test probe with multiple video and audio streams."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {
                "streams": [
                    {
                        "codec_type": "video",
                        "codec_name": "h264",
                        "width": 1920,
                        "height": 1080,
                        "r_frame_rate": "30/1",
                    },
                    {
                        "codec_type": "audio",
                        "codec_name": "aac",
                        "sample_rate": "48000",
                        "channels": 2,
                    },
                    {
                        "codec_type": "video",
                        "codec_name": "h264",
                        "width": 1280,
                        "height": 720,
                        "r_frame_rate": "30/1",
                    },
                    {
                        "codec_type": "audio",
                        "codec_name": "ac3",
                        "sample_rate": "48000",
                        "channels": 6,
                    },
                ],
                "format": {"filename": "test.mkv", "bit_rate": "5000000"},
            }
        )

        with patch("subprocess.run", return_value=mock_result):
            result = probe(Path("test.mkv"))

        assert result is not None
        assert len(result["streams"]) == 4
        # Verify video streams
        video_streams = [s for s in result["streams"] if s["codec_type"] == "video"]
        assert len(video_streams) == 2
        assert video_streams[0]["height"] == 1080
        assert video_streams[1]["height"] == 720
        # Verify audio streams
        audio_streams = [s for s in result["streams"] if s["codec_type"] == "audio"]
        assert len(audio_streams) == 2
        assert audio_streams[0]["codec_name"] == "aac"
        assert audio_streams[1]["codec_name"] == "ac3"

    def test_probe_empty_streams(self):
        """Test probe with no streams."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {"streams": [], "format": {"filename": "empty.mp4"}}
        )

        with patch("subprocess.run", return_value=mock_result):
            result = probe(Path("empty.mp4"))

        assert result is not None
        assert "streams" in result
        assert len(result["streams"]) == 0

    def test_probe_missing_format_section(self):
        """Test probe with missing format section."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {"streams": [{"codec_type": "video", "codec_name": "h264"}]}
        )

        with patch("subprocess.run", return_value=mock_result):
            result = probe(Path("test.mp4"))

        assert result is not None
        assert "streams" in result
        # format section should be missing or empty
        assert "format" not in result or result.get("format") is None

    def test_probe_with_subprocess_exception(self):
        """Test probe when subprocess raises an exception."""
        with patch(
            "subprocess.run", side_effect=FileNotFoundError("ffprobe not found")
        ):
            result = probe(Path("test.mp4"))

        # Should return None when subprocess fails
        assert result is None
