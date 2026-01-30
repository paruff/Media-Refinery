import unittest
import subprocess
from src.metadata.metadata import MetadataExtractor
from unittest.mock import patch


class TestMetadataExtractor(unittest.TestCase):
    @patch("subprocess.check_output")
    def test_extract_metadata_with_ffprobe(self, mock_subprocess):
        mock_subprocess.return_value = '{"format": {"tags": {"title": "Test Title", "artist": "Test Artist"}, "duration": "120.5", "bit_rate": "320000"}, "streams": [{"codec_type": "audio", "sample_rate": "44100", "channels": 2}]}'

        extractor = MetadataExtractor()
        metadata = extractor.extract_metadata("test.mp3")

        self.assertEqual(metadata.title, "Test Title")
        self.assertEqual(metadata.artist, "Test Artist")
        self.assertEqual(metadata.duration, 120.5)
        self.assertEqual(metadata.bitrate, 320000)
        self.assertEqual(metadata.sample_rate, 44100)
        self.assertEqual(metadata.channels, 2)

    @patch(
        "subprocess.check_output",
        side_effect=subprocess.CalledProcessError(1, "ffprobe"),
    )
    def test_extract_metadata_with_fallback(self, mock_subprocess):
        extractor = MetadataExtractor()
        metadata = extractor.extract_metadata("Show.Name.S01E02.mp4")

        self.assertEqual(metadata.show, "Show Name")
        self.assertEqual(metadata.season, "01")
        self.assertEqual(metadata.episode, "02")
        self.assertEqual(metadata.title, "Show Name")

    def test_clean_tag(self):
        extractor = MetadataExtractor(cleanup_tags=True)
        self.assertEqual(extractor.clean_tag("  Test Title  "), "Test Title")
        self.assertEqual(extractor.clean_tag(None), None)


if __name__ == "__main__":
    unittest.main()
