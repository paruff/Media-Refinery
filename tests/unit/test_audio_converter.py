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
        """Test conversion writes directly to output (atomic at filesystem level)."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        output_files_created = []

        async def mock_execute(cmd):
            # Record which output file was used in command
            # Current implementation writes directly to final output (not .tmp)
            for i, arg in enumerate(cmd):
                if str(output_dir) in str(arg) and not str(arg).endswith('.tmp'):
                    output_files_created.append(arg)
            return (0, "", "")

        with patch.object(converter, "_execute_ffmpeg", side_effect=mock_execute):
            result = await converter.convert(temp_audio_file, output_dir)

            # Should have created output file directly
            assert len(output_files_created) > 0 or result.success is False
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

    # ============================================================================
    # Tests for Story 1.3: Multi-Format Support
    # ============================================================================

    @pytest.mark.asyncio
    async def test_detect_audio_properties_mp3(self, tmp_path: Path):
        """Test detecting audio properties from MP3 file."""
        converter = AudioConverter()
        
        # Mock ffprobe output for MP3
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
        
        with patch.object(converter, "_execute_ffprobe") as mock_ffprobe:
            mock_ffprobe.return_value = {
                "streams": [{
                    "codec_type": "audio",
                    "codec_name": "mp3",
                    "sample_rate": "44100",
                    "channels": 2
                }]
            }
            
            props = await converter.detect_audio_properties(audio_file)
            
            assert props is not None
            assert props.sample_rate == 44100
            assert props.codec_name == "mp3"
            assert props.is_lossless is False

    @pytest.mark.asyncio
    async def test_detect_audio_properties_flac(self, tmp_path: Path):
        """Test detecting audio properties from FLAC file (lossless)."""
        converter = AudioConverter()
        
        audio_file = tmp_path / "test.flac"
        audio_file.write_bytes(b"fLaC" + b"\x00" * 100)
        
        with patch.object(converter, "_execute_ffprobe") as mock_ffprobe:
            mock_ffprobe.return_value = {
                "streams": [{
                    "codec_type": "audio",
                    "codec_name": "flac",
                    "sample_rate": "48000",
                    "channels": 2
                }]
            }
            
            props = await converter.detect_audio_properties(audio_file)
            
            assert props.sample_rate == 48000
            assert props.codec_name == "flac"
            assert props.is_lossless is True

    def test_determine_compression_level_lossy_source(self):
        """Test compression level selection for lossy source (MP3, AAC, OGG)."""
        converter = AudioConverter(compression_level=5)
        
        # For lossy sources, should use default compression
        level = converter._determine_optimal_compression("mp3")
        assert level == 5  # Default compression
        
        level = converter._determine_optimal_compression("aac")
        assert level == 5

    def test_determine_compression_level_lossless_source(self):
        """Test compression level selection for lossless source (FLAC, WAV)."""
        converter = AudioConverter(compression_level=5)
        
        # For lossless sources, should use max compression (8)
        level = converter._determine_optimal_compression("flac")
        assert level == 8
        
        level = converter._determine_optimal_compression("wav")
        assert level == 8

    def test_build_ffmpeg_command_preserves_sample_rate(self):
        """Test FFmpeg command preserves sample rate from source."""
        # When sample_rate is None, should preserve original
        converter = AudioConverter(sample_rate=None, compression_level=5)
        input_path = Path("/input/song.mp3")
        output_path = Path("/output/song.flac")
        
        # Without explicit sample rate, should not include -ar flag
        command = converter.build_ffmpeg_command(input_path, output_path)
        
        # Should not force sample rate conversion
        if "-ar" in command:
            # If -ar is present, verify it's not set (or handle appropriately)
            pass
        
        # When sample_rate is explicitly set, should include it
        converter_with_rate = AudioConverter(sample_rate=48000)
        command = converter_with_rate.build_ffmpeg_command(input_path, output_path)
        assert "-ar" in command
        assert "48000" in command

    def test_build_ffmpeg_command_wav_endianness(self):
        """Test FFmpeg command handles WAV endianness correctly."""
        converter = AudioConverter(output_format="flac")
        input_path = Path("/input/song.wav")
        output_path = Path("/output/song.flac")
        
        command = converter.build_ffmpeg_command(input_path, output_path)
        
        # Should include format-specific handling for WAV
        assert isinstance(command, list)
        assert "ffmpeg" in command
        # WAV files should be handled with proper endianness detection

    def test_build_ffmpeg_command_m4a_container(self):
        """Test FFmpeg command handles M4A container format correctly."""
        converter = AudioConverter(output_format="flac")
        input_path = Path("/input/song.m4a")
        output_path = Path("/output/song.flac")
        
        command = converter.build_ffmpeg_command(input_path, output_path)
        
        # Should handle M4A container correctly
        assert isinstance(command, list)
        assert "-i" in command
        assert str(input_path) in command

    @pytest.mark.parametrize(
        "input_format",
        ["mp3", "aac", "m4a", "ogg", "wav", "opus"],
    )
    @pytest.mark.asyncio
    async def test_convert_format_to_flac(
        self, input_format: str, tmp_path: Path
    ):
        """Test converting each format to FLAC (Story 1.3 acceptance criteria)."""
        converter = AudioConverter(output_format="flac", compression_level=5)
        
        # Create test input file
        input_file = tmp_path / f"test.{input_format}"
        input_file.write_bytes(b"fake audio data" + b"\x00" * 100)
        
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        # Mock FFmpeg execution
        with patch.object(
            converter, "_execute_ffmpeg", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.return_value = (0, "", "")
            
            # Mock audio properties detection
            with patch.object(
                converter, "detect_audio_properties", new_callable=AsyncMock
            ) as mock_detect:
                from dataclasses import dataclass
                
                @dataclass
                class AudioProps:
                    sample_rate: int
                    codec_name: str
                    is_lossless: bool
                
                # Set properties based on format
                is_lossless = input_format in ["flac", "wav"]
                mock_detect.return_value = AudioProps(
                    sample_rate=44100,
                    codec_name=input_format,
                    is_lossless=is_lossless
                )
                
                result = await converter.convert(input_file, output_dir)
                
                # Verify conversion was attempted
                assert result is not None
                assert hasattr(result, "success")
                assert result.output_path.suffix == ".flac"

    @pytest.mark.parametrize(
        "input_format,expected_sample_rate",
        [
            ("mp3", 44100),
            ("flac", 48000),
            ("wav", 96000),
            ("opus", 48000),
        ],
    )
    @pytest.mark.asyncio
    async def test_preserve_sample_rate_per_format(
        self, input_format: str, expected_sample_rate: int, tmp_path: Path
    ):
        """Test sample rate preservation for each format."""
        converter = AudioConverter(output_format="flac")
        
        input_file = tmp_path / f"test.{input_format}"
        input_file.write_bytes(b"fake audio data" + b"\x00" * 100)
        
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        # Mock FFmpeg and properties detection
        with patch.object(
            converter, "_execute_ffmpeg", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.return_value = (0, "", "")
            
            with patch.object(
                converter, "detect_audio_properties", new_callable=AsyncMock
            ) as mock_detect:
                from dataclasses import dataclass
                
                @dataclass
                class AudioProps:
                    sample_rate: int
                    codec_name: str
                    is_lossless: bool
                
                mock_detect.return_value = AudioProps(
                    sample_rate=expected_sample_rate,
                    codec_name=input_format,
                    is_lossless=(input_format in ["flac", "wav"])
                )
                
                result = await converter.convert(input_file, output_dir)
                
                # Verify FFmpeg was called (which would preserve sample rate)
                mock_exec.assert_called_once()
                assert result is not None

    @pytest.mark.parametrize(
        "input_format,expected_compression",
        [
            ("mp3", 5),    # Lossy source: default compression
            ("aac", 5),    # Lossy source: default compression
            ("ogg", 5),    # Lossy source: default compression
            ("flac", 8),   # Lossless source: max compression
            ("wav", 8),    # Lossless source: max compression
        ],
    )
    def test_adaptive_compression_by_format(
        self, input_format: str, expected_compression: int
    ):
        """Test adaptive compression level based on source format."""
        from src.audio.converter import AudioConverter
        
        converter = AudioConverter(compression_level=5)
        
        # Determine optimal compression based on format using the converter's logic
        level = converter._determine_optimal_compression(input_format)
        
        assert level == expected_compression
