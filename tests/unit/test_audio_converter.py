"""Unit tests for AudioConverter module.

Following TDD principles, these tests define the expected behavior
of the AudioConverter before implementation.
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from src.audio.converter import AudioConverter


class TestAudioConverter:
    """Test suite for AudioConverter class."""

    @pytest.fixture
    def converter(self):
        """Create AudioConverter instance with default settings."""
        return AudioConverter(output_format="flac", compression_level=5)

    @pytest.fixture
    def temp_audio_file(self, tmp_path: Path) -> Path:
        """Create temporary MP3 audio file for testing."""
        audio_file = tmp_path / "test.mp3"
        # Create a file with MP3 magic number
        audio_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
        return audio_file

    # ============================================================================
    # Tests for FFmpeg command building
    # ============================================================================

    def test_build_ffmpeg_command_basic(self, converter: AudioConverter):
        """Test FFmpeg command building with basic options."""
        input_path = Path("/input/song.mp3")
        output_path = Path("/output/song.flac")

        command = converter.build_ffmpeg_command(input_path, output_path)

        assert isinstance(command, list)
        assert "ffmpeg" in command
        assert "-i" in command
        assert str(input_path) in command
        assert str(output_path) in command

    def test_build_ffmpeg_command_with_format(self, converter: AudioConverter):
        """Test FFmpeg command includes correct codec for FLAC."""
        input_path = Path("/input/song.mp3")
        output_path = Path("/output/song.flac")

        command = converter.build_ffmpeg_command(input_path, output_path)

        # Should include audio codec flag for FLAC
        assert "-c:a" in command
        flac_idx = command.index("-c:a")
        assert command[flac_idx + 1] == "flac"

    def test_build_ffmpeg_command_with_compression(self, converter: AudioConverter):
        """Test FFmpeg command includes compression level."""
        input_path = Path("/input/song.mp3")
        output_path = Path("/output/song.flac")

        command = converter.build_ffmpeg_command(
            input_path, output_path, compression_level=8
        )

        # Should include compression level
        assert "-compression_level" in command
        comp_idx = command.index("-compression_level")
        assert command[comp_idx + 1] == "8"

    def test_build_ffmpeg_command_preserve_metadata(self, converter: AudioConverter):
        """Test FFmpeg command preserves metadata when requested."""
        input_path = Path("/input/song.mp3")
        output_path = Path("/output/song.flac")

        command = converter.build_ffmpeg_command(
            input_path, output_path, preserve_metadata=True
        )

        # Should include metadata mapping
        assert "-map_metadata" in command

    def test_build_ffmpeg_command_overwrite(self, converter: AudioConverter):
        """Test FFmpeg command includes overwrite flag."""
        input_path = Path("/input/song.mp3")
        output_path = Path("/output/song.flac")

        command = converter.build_ffmpeg_command(input_path, output_path)

        # Should include -y flag to overwrite without prompting
        assert "-y" in command

    # ============================================================================
    # Tests for checksum calculation
    # ============================================================================

    def test_calculate_checksum_valid_file(self, temp_audio_file: Path):
        """Test SHA256 checksum calculation for valid file."""
        converter = AudioConverter()

        checksum = converter.calculate_checksum(temp_audio_file)

        assert isinstance(checksum, str)
        assert len(checksum) == 64  # SHA256 is 64 hex characters
        # Verify it's a valid hex string
        int(checksum, 16)

    def test_calculate_checksum_consistency(self, temp_audio_file: Path):
        """Test checksum is consistent for same file."""
        converter = AudioConverter()

        checksum1 = converter.calculate_checksum(temp_audio_file)
        checksum2 = converter.calculate_checksum(temp_audio_file)

        assert checksum1 == checksum2

    def test_calculate_checksum_different_files(self, tmp_path: Path):
        """Test different files produce different checksums."""
        converter = AudioConverter()

        file1 = tmp_path / "file1.mp3"
        file2 = tmp_path / "file2.mp3"
        file1.write_bytes(b"content1")
        file2.write_bytes(b"content2")

        checksum1 = converter.calculate_checksum(file1)
        checksum2 = converter.calculate_checksum(file2)

        assert checksum1 != checksum2

    def test_calculate_checksum_nonexistent_file(self, tmp_path: Path):
        """Test checksum calculation raises error for non-existent file."""
        converter = AudioConverter()
        nonexistent = tmp_path / "nonexistent.mp3"

        with pytest.raises(FileNotFoundError):
            converter.calculate_checksum(nonexistent)

    # ============================================================================
    # Tests for atomic file operations
    # ============================================================================

    def test_atomic_write_creates_temp_file(self, tmp_path: Path):
        """Test atomic write creates temporary file first."""
        converter = AudioConverter()
        output_path = tmp_path / "output.flac"
        temp_path = converter.get_temp_path(output_path)

        assert temp_path != output_path
        assert temp_path.suffix == ".tmp"
        assert str(output_path.stem) in str(temp_path)

    def test_get_temp_path_format(self, tmp_path: Path):
        """Test temporary path format is consistent."""
        converter = AudioConverter()
        output_path = tmp_path / "output.flac"

        temp_path = converter.get_temp_path(output_path)

        assert temp_path.parent == output_path.parent
        assert ".tmp" in str(temp_path)

    # ============================================================================
    # Tests for async conversion - mocked
    # ============================================================================

    @pytest.mark.asyncio
    async def test_convert_success_returns_result(
        self, converter: AudioConverter, temp_audio_file: Path, tmp_path: Path
    ):
        """Test successful conversion returns AudioConversionResult."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Mock FFmpeg execution
        with patch.object(
            converter, "_execute_ffmpeg", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.return_value = (0, "", "")

            result = await converter.convert(temp_audio_file, output_dir)

            assert result is not None
            assert hasattr(result, "success")
            assert hasattr(result, "output_path")
            assert hasattr(result, "checksum")
            assert hasattr(result, "duration_ms")
            assert hasattr(result, "size_bytes")

    @pytest.mark.asyncio
    async def test_convert_creates_output_directory(
        self, converter: AudioConverter, temp_audio_file: Path, tmp_path: Path
    ):
        """Test conversion creates output directory if it doesn't exist."""
        output_dir = tmp_path / "nonexistent" / "output"

        with patch.object(
            converter, "_execute_ffmpeg", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.return_value = (0, "", "")

            await converter.convert(temp_audio_file, output_dir)

            assert output_dir.exists()
            assert output_dir.is_dir()

    @pytest.mark.asyncio
    async def test_convert_invalid_input_raises_error(
        self, converter: AudioConverter, tmp_path: Path
    ):
        """Test conversion with non-existent file raises FileNotFoundError."""
        nonexistent = tmp_path / "nonexistent.mp3"
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with pytest.raises(FileNotFoundError) as exc_info:
            await converter.convert(nonexistent, output_dir)

        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_convert_ffmpeg_failure_raises_error(
        self, converter: AudioConverter, temp_audio_file: Path, tmp_path: Path
    ):
        """Test FFmpeg failure returns error result."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Mock FFmpeg failure
        with patch.object(
            converter, "_execute_ffmpeg", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.return_value = (1, "", "FFmpeg error: invalid codec")

            result = await converter.convert(temp_audio_file, output_dir)

            # Should return a failed result
            assert result.success is False
            assert result.error_message is not None
            assert "ffmpeg" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_convert_uses_atomic_operations(
        self, converter: AudioConverter, temp_audio_file: Path, tmp_path: Path
    ):
        """Test conversion uses atomic file operations (temp file → final)."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        temp_files_created = []

        async def mock_execute(cmd):
            # Record which output file was used in command
            for i, arg in enumerate(cmd):
                if ".tmp" in str(arg):
                    temp_files_created.append(arg)
            return (0, "", "")

        with patch.object(converter, "_execute_ffmpeg", side_effect=mock_execute):
            result = await converter.convert(temp_audio_file, output_dir)

            # Should have used temporary file
            assert len(temp_files_created) > 0
            # Final result should not be temp file
            assert ".tmp" not in str(result.output_path)

    @pytest.mark.asyncio
    async def test_convert_calculates_checksum(
        self, converter: AudioConverter, temp_audio_file: Path, tmp_path: Path
    ):
        """Test conversion calculates SHA256 checksum of output."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Create a real output file to be checksummed
        output_file = output_dir / "test.flac"
        temp_file = converter.get_temp_path(output_file)

        async def mock_execute(cmd):
            # Create the temp file so rename works
            temp_file.write_bytes(b"fake flac audio data")
            return (0, "", "")

        with patch.object(converter, "_execute_ffmpeg", side_effect=mock_execute):
            result = await converter.convert(temp_audio_file, output_dir)

            assert result.success is True
            assert result.checksum is not None
            assert len(result.checksum) == 64

    @pytest.mark.asyncio
    async def test_convert_preserves_quality(
        self, converter: AudioConverter, temp_audio_file: Path, tmp_path: Path
    ):
        """Test conversion command preserves audio quality."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        captured_command = []

        async def capture_command(cmd):
            captured_command.extend(cmd)
            return (0, "", "")

        with patch.object(converter, "_execute_ffmpeg", side_effect=capture_command):
            await converter.convert(temp_audio_file, output_dir)

            # Should use lossless codec
            assert "-c:a" in captured_command
            assert "flac" in captured_command

    # ============================================================================
    # Tests for validation
    # ============================================================================

    def test_validate_input_file_exists(self, temp_audio_file: Path):
        """Test validation passes for existing file."""
        converter = AudioConverter()

        is_valid = converter.validate_input_file(temp_audio_file)

        assert is_valid is True

    def test_validate_input_file_not_exists(self, tmp_path: Path):
        """Test validation fails for non-existent file."""
        converter = AudioConverter()
        nonexistent = tmp_path / "nonexistent.mp3"

        is_valid = converter.validate_input_file(nonexistent)

        assert is_valid is False

    def test_validate_input_file_unsupported_format(self, tmp_path: Path):
        """Test validation fails for unsupported format."""
        converter = AudioConverter()
        unsupported = tmp_path / "file.xyz"
        unsupported.touch()

        is_valid = converter.validate_input_file(unsupported)

        assert is_valid is False

    @pytest.mark.parametrize(
        "extension",
        [".mp3", ".flac", ".aac", ".m4a", ".ogg", ".wav", ".opus"],
    )
    def test_validate_supported_formats(self, tmp_path: Path, extension: str):
        """Test validation passes for all supported audio formats."""
        converter = AudioConverter()
        audio_file = tmp_path / f"audio{extension}"
        audio_file.touch()

        is_valid = converter.validate_input_file(audio_file)

        assert is_valid is True
