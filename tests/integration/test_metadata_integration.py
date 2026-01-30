import unittest
from src.metadata.metadata import MetadataExtractor
from pathlib import Path


class TestMetadataIntegration(unittest.TestCase):
    def test_integration_with_real_file(self):
        extractor = MetadataExtractor()
        test_file = Path("/path/to/real/media/file.mp3")

        if not test_file.exists():
            self.skipTest("Real media file not available for integration test.")

        metadata = extractor.extract_metadata(str(test_file))

        self.assertTrue(metadata.title or metadata.artist)
        self.assertTrue(metadata.duration > 0)


if __name__ == "__main__":
    unittest.main()
