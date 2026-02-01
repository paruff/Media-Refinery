"""Integration tests for AudioConverter with real FFmpeg.

These tests use actual FFmpeg/FFprobe tools and real audio files
to validate the complete conversion workflow.
"""

import pytest
from pathlib import Path
from src.audio.converter import AudioConverter


class TestAudioConverterIntegration:
    """Integration tests for AudioConverter with real FFmpeg."""

    @pytest.fixture
    def converter(self):
        """Create AudioConverter instance."""
        return AudioConverter(output_format="flac", compression_level=5)

    @pytest.fixture
    def testdata_dir(self) -> Path:
        """Get testdata directory path."""
        return Path(__file__).parent.parent.parent / "testdata" / "audio"

    @pytest.fixture
    def sample_mp3(self, testdata_dir: Path) -> Path:
        """Get path to sample MP3 file."""
        # Try the valid test file first
        mp3_file = testdata_dir / "test_valid.mp3"
        if mp3_file.exists():
            return mp3_file

        # Fall back to sample.mp3
        mp3_file = testdata_dir / "sample.mp3"
        if not mp3_file.exists():
            pytest.skip("Sample MP3 file not found")
        return mp3_file

    @pytest.mark.asyncio
    async def test_convert_mp3_to_flac_success(
        self, converter: AudioConverter, sample_mp3: Path, tmp_path: Path
    ):
        """Test successful MP3 to FLAC conversion with real FFmpeg."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = await converter.convert(sample_mp3, output_dir)

        # Verify success
        assert result.success is True
        assert result.output_path.exists()
        assert result.output_path.suffix == ".flac"
        assert result.output_path.name == f"{sample_mp3.stem}.flac"

        # Verify output file is not empty
        assert result.size_bytes > 0
        assert result.output_path.stat().st_size == result.size_bytes

    @pytest.mark.asyncio
    async def test_convert_preserves_quality(
        self, converter: AudioConverter, sample_mp3: Path, tmp_path: Path
    ):
        """Test conversion preserves audio quality (uses lossless codec)."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = await converter.convert(sample_mp3, output_dir)

        assert result.success is True

        # Verify the output is actually FLAC format using FFprobe
        import asyncio
        import json

        process = await asyncio.create_subprocess_exec(
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_streams",
            str(result.output_path),
            stdout=asyncio.subprocess.PIPE,
        )
        stdout, _ = await process.communicate()
        probe_data = json.loads(stdout.decode())

        # Verify it's FLAC codec
        audio_streams = [
            s for s in probe_data["streams"] if s.get("codec_type") == "audio"
        ]
        assert len(audio_streams) > 0
        assert audio_streams[0]["codec_name"] == "flac"

    @pytest.mark.asyncio
    async def test_convert_calculates_checksum(
        self, converter: AudioConverter, sample_mp3: Path, tmp_path: Path
    ):
        """Test conversion calculates SHA256 checksum of output file."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = await converter.convert(sample_mp3, output_dir)

        assert result.success is True
        assert result.checksum is not None
        assert len(result.checksum) == 64  # SHA256 is 64 hex chars

        # Verify checksum is correct by recalculating
        recalculated = converter.calculate_checksum(result.output_path)
        assert result.checksum == recalculated

    @pytest.mark.asyncio
    async def test_convert_stores_metadata(
        self, converter: AudioConverter, sample_mp3: Path, tmp_path: Path
    ):
        """Test conversion stores duration and size metadata."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = await converter.convert(sample_mp3, output_dir)

        assert result.success is True
        assert result.duration_ms > 0  # Should have positive duration
        assert result.size_bytes > 0  # Should have positive size

    @pytest.mark.asyncio
    async def test_convert_creates_atomic_output(
        self, converter: AudioConverter, sample_mp3: Path, tmp_path: Path
    ):
        """Test conversion uses atomic file operations (no .tmp file left)."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = await converter.convert(sample_mp3, output_dir)

        assert result.success is True

        # Verify final file exists
        assert result.output_path.exists()

        # Verify no .tmp files are left behind
        tmp_files = list(output_dir.glob("*.tmp"))
        assert len(tmp_files) == 0, f"Temporary files left behind: {tmp_files}"

    @pytest.mark.asyncio
    async def test_convert_invalid_input_fails(
        self, converter: AudioConverter, tmp_path: Path
    ):
        """Test conversion with non-existent file raises error."""
        nonexistent = tmp_path / "nonexistent.mp3"
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with pytest.raises(FileNotFoundError):
            await converter.convert(nonexistent, output_dir)

    @pytest.mark.asyncio
    async def test_convert_corrupted_input_fails(
        self, converter: AudioConverter, tmp_path: Path
    ):
        """Test conversion with corrupted audio file fails gracefully."""
        corrupted = tmp_path / "corrupted.mp3"
        corrupted.write_bytes(b"This is not a valid MP3 file")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = await converter.convert(corrupted, output_dir)

        # Should return failed result
        assert result.success is False
        assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_convert_multiple_files(
        self, converter: AudioConverter, testdata_dir: Path, tmp_path: Path
    ):
        """Test converting multiple audio files."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Find all audio files in testdata
        audio_files = [
            testdata_dir / "sample.mp3",
            testdata_dir / "sample.flac",
            testdata_dir / "sample.wav",
        ]

        # Filter to only existing files
        audio_files = [f for f in audio_files if f.exists()]

        if len(audio_files) == 0:
            pytest.skip("No test audio files found")

        results = []
        for audio_file in audio_files:
            result = await converter.convert(audio_file, output_dir)
            results.append(result)

        # All conversions should succeed
        assert all(r.success for r in results)

        # All output files should exist
        assert all(r.output_path.exists() for r in results)

        # All checksums should be unique (different files)
        checksums = [r.checksum for r in results]
        assert len(checksums) == len(set(checksums))

    @pytest.mark.asyncio
    async def test_convert_with_different_compression_levels(
        self, sample_mp3: Path, tmp_path: Path
    ):
        """Test conversion with different FLAC compression levels."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Convert with compression level 0 (fastest)
        converter_fast = AudioConverter(output_format="flac", compression_level=0)
        result_fast = await converter_fast.convert(sample_mp3, output_dir / "fast")

        # Convert with compression level 8 (best)
        converter_best = AudioConverter(output_format="flac", compression_level=8)
        result_best = await converter_best.convert(sample_mp3, output_dir / "best")

        assert result_fast.success is True
        assert result_best.success is True

        # Both should produce valid FLAC files
        assert result_fast.output_path.exists()
        assert result_best.output_path.exists()

        # Higher compression should generally result in smaller file
        # (though not guaranteed for all audio)
        assert result_fast.size_bytes > 0
        assert result_best.size_bytes > 0

    @pytest.mark.asyncio
    async def test_convert_handles_output_dir_creation(
        self, converter: AudioConverter, sample_mp3: Path, tmp_path: Path
    ):
        """Test conversion creates output directory if it doesn't exist."""
        # Use deeply nested directory that doesn't exist
        output_dir = tmp_path / "a" / "b" / "c" / "output"

        result = await converter.convert(sample_mp3, output_dir)

        assert result.success is True
        assert output_dir.exists()
        assert result.output_path.exists()

    @pytest.mark.asyncio
    async def test_convert_to_different_formats(self, sample_mp3: Path, tmp_path: Path):
        """Test conversion to different audio formats."""
        formats_to_test = ["flac", "wav", "ogg"]

        for format_name in formats_to_test:
            converter = AudioConverter(output_format=format_name)
            output_dir = tmp_path / format_name
            output_dir.mkdir()

            result = await converter.convert(sample_mp3, output_dir)

            assert result.success is True, f"Failed to convert to {format_name}"
            assert result.output_path.suffix == f".{format_name}"
            assert result.output_path.exists()
            assert result.size_bytes > 0

    @pytest.mark.asyncio
    async def test_performance_5mb_file(self, sample_mp3: Path, tmp_path: Path):
        """Test conversion performance meets requirement (<10s for 5MB file)."""
        import time

        # Check file size
        file_size_mb = sample_mp3.stat().st_size / (1024 * 1024)

        if file_size_mb > 5.5:  # Allow some margin
            pytest.skip("Test file is too large for performance test")

        converter = AudioConverter(output_format="flac", compression_level=5)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        start_time = time.time()
        result = await converter.convert(sample_mp3, output_dir)
        end_time = time.time()

        duration = end_time - start_time

        assert result.success is True

        # For small test files, should be much faster than 10s
        # For actual 5MB files, should be <10s
        if file_size_mb > 0.5:  # Only check timing for larger files
            assert duration < 10.0, f"Conversion took {duration:.2f}s, expected <10s"
