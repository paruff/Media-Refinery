"""Unit tests for AudioValidator module.

Following TDD principles, these tests define the expected behavior
of the AudioValidator before implementation.
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from src.audio.validator import (
    AudioValidator,
    ValidationResult,
    ValidationError,
    PreConversionValidationError,
    PostConversionValidationError,
    FFprobeValidationError,
)


class TestAudioValidator:
    """Test suite for AudioValidator class."""

    @pytest.fixture
    def validator(self):
        """Create AudioValidator instance."""
        return AudioValidator()

    @pytest.fixture
    def temp_audio_file(self, tmp_path: Path) -> Path:
        """Create temporary MP3 audio file for testing."""
        audio_file = tmp_path / "test.mp3"
        # Create a file with MP3 magic number
        audio_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
        return audio_file

    @pytest.fixture
    def temp_flac_file(self, tmp_path: Path) -> Path:
        """Create temporary FLAC audio file for testing."""
        flac_file = tmp_path / "test.flac"
        # Create a file with FLAC magic number
        flac_file.write_bytes(b"fLaC\x00\x00\x00\x22" + b"\x00" * 100)
        return flac_file

    # ============================================================================
    # Tests for Pre-conversion Validation
    # ============================================================================

    @pytest.mark.asyncio
    async def test_validate_pre_conversion_success(
        self, validator: AudioValidator, temp_audio_file: Path
    ):
        """Test pre-conversion validation succeeds for valid file."""
        result = await validator.validate_pre_conversion(temp_audio_file)

        assert result.is_valid is True
        assert result.error_message is None
        assert result.troubleshooting_hint is None

    @pytest.mark.asyncio
    async def test_validate_pre_conversion_file_not_found(
        self, validator: AudioValidator, tmp_path: Path
    ):
        """Test pre-conversion validation fails for non-existent file."""
        nonexistent_file = tmp_path / "nonexistent.mp3"

        result = await validator.validate_pre_conversion(nonexistent_file)

        assert result.is_valid is False
        assert "not found" in result.error_message.lower()
        assert result.troubleshooting_hint is not None
        assert "check" in result.troubleshooting_hint.lower()

    @pytest.mark.asyncio
    async def test_validate_pre_conversion_file_not_readable(
        self, validator: AudioValidator, temp_audio_file: Path
    ):
        """Test pre-conversion validation fails for unreadable file."""
        # Make file unreadable (Unix permissions)
        temp_audio_file.chmod(0o000)

        result = await validator.validate_pre_conversion(temp_audio_file)

        # Clean up - restore permissions
        temp_audio_file.chmod(0o644)

        assert result.is_valid is False
        assert "permission" in result.error_message.lower() or "read" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_validate_pre_conversion_invalid_format(
        self, validator: AudioValidator, tmp_path: Path
    ):
        """Test pre-conversion validation fails for invalid audio format."""
        invalid_file = tmp_path / "invalid.mp3"
        # Write non-audio data
        invalid_file.write_bytes(b"This is not audio data")

        result = await validator.validate_pre_conversion(invalid_file)

        assert result.is_valid is False
        assert "format" in result.error_message.lower() or "invalid" in result.error_message.lower()
        assert result.troubleshooting_hint is not None

    @pytest.mark.asyncio
    async def test_validate_pre_conversion_empty_file(
        self, validator: AudioValidator, tmp_path: Path
    ):
        """Test pre-conversion validation fails for empty file."""
        empty_file = tmp_path / "empty.mp3"
        empty_file.touch()

        result = await validator.validate_pre_conversion(empty_file)

        assert result.is_valid is False
        assert "empty" in result.error_message.lower() or "corrupted" in result.error_message.lower()

    # ============================================================================
    # Tests for Post-conversion Validation
    # ============================================================================

    @pytest.mark.asyncio
    async def test_validate_post_conversion_success(
        self, validator: AudioValidator, temp_flac_file: Path
    ):
        """Test post-conversion validation succeeds for valid FLAC file."""
        result = await validator.validate_post_conversion(temp_flac_file)

        assert result.is_valid is True
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_validate_post_conversion_file_not_found(
        self, validator: AudioValidator, tmp_path: Path
    ):
        """Test post-conversion validation fails for non-existent file."""
        nonexistent_file = tmp_path / "nonexistent.flac"

        result = await validator.validate_post_conversion(nonexistent_file)

        assert result.is_valid is False
        assert "not found" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_validate_post_conversion_invalid_flac_header(
        self, validator: AudioValidator, tmp_path: Path
    ):
        """Test post-conversion validation fails for invalid FLAC header."""
        invalid_flac = tmp_path / "invalid.flac"
        # Write invalid FLAC header
        invalid_flac.write_bytes(b"INVALID_HEADER" + b"\x00" * 100)

        result = await validator.validate_post_conversion(invalid_flac)

        assert result.is_valid is False
        assert "header" in result.error_message.lower() or "invalid" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_validate_post_conversion_corrupted_audio_stream(
        self, validator: AudioValidator, tmp_path: Path
    ):
        """Test post-conversion validation fails for corrupted audio stream."""
        corrupted_file = tmp_path / "corrupted.flac"
        # Write FLAC header but corrupted stream data
        corrupted_file.write_bytes(b"fLaC" + b"\xff" * 100)

        with patch.object(
            validator, "_validate_audio_stream", return_value=False
        ):
            result = await validator.validate_post_conversion(corrupted_file)

            assert result.is_valid is False

    # ============================================================================
    # Tests for FFprobe Verification
    # ============================================================================

    @pytest.mark.asyncio
    async def test_verify_with_ffprobe_success(
        self, validator: AudioValidator, temp_flac_file: Path
    ):
        """Test FFprobe verification succeeds for valid audio file."""
        # Mock FFprobe output
        mock_probe_data = {
            "streams": [
                {
                    "codec_type": "audio",
                    "codec_name": "flac",
                    "sample_rate": "44100",
                    "channels": 2,
                }
            ]
        }

        with patch.object(
            validator, "_execute_ffprobe", return_value=mock_probe_data
        ):
            result = await validator.verify_with_ffprobe(temp_flac_file)

            assert result.is_valid is True
            assert result.metadata is not None
            assert result.metadata["codec_name"] == "flac"
            assert result.metadata["sample_rate"] == "44100"
            assert result.metadata["channels"] == 2

    @pytest.mark.asyncio
    async def test_verify_with_ffprobe_no_audio_stream(
        self, validator: AudioValidator, tmp_path: Path
    ):
        """Test FFprobe verification fails when no audio stream found."""
        test_file = tmp_path / "test.mp3"
        test_file.write_bytes(b"ID3" + b"\x00" * 100)

        # Mock FFprobe output with no audio streams
        mock_probe_data = {"streams": []}

        with patch.object(
            validator, "_execute_ffprobe", return_value=mock_probe_data
        ):
            result = await validator.verify_with_ffprobe(test_file)

            assert result.is_valid is False
            assert "audio stream" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_verify_with_ffprobe_invalid_codec(
        self, validator: AudioValidator, tmp_path: Path
    ):
        """Test FFprobe verification detects codec mismatches."""
        test_file = tmp_path / "test.flac"
        test_file.write_bytes(b"fLaC" + b"\x00" * 100)

        # Mock FFprobe output with unexpected codec
        mock_probe_data = {
            "streams": [
                {
                    "codec_type": "audio",
                    "codec_name": "mp3",  # Wrong codec for .flac extension
                    "sample_rate": "44100",
                    "channels": 2,
                }
            ]
        }

        with patch.object(
            validator, "_execute_ffprobe", return_value=mock_probe_data
        ):
            result = await validator.verify_with_ffprobe(
                test_file, expected_codec="flac"
            )

            assert result.is_valid is False
            assert "codec" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_verify_with_ffprobe_invalid_sample_rate(
        self, validator: AudioValidator, tmp_path: Path
    ):
        """Test FFprobe verification detects sample rate mismatches."""
        test_file = tmp_path / "test.flac"
        test_file.write_bytes(b"fLaC" + b"\x00" * 100)

        # Mock FFprobe output with unexpected sample rate
        mock_probe_data = {
            "streams": [
                {
                    "codec_type": "audio",
                    "codec_name": "flac",
                    "sample_rate": "22050",  # Wrong sample rate
                    "channels": 2,
                }
            ]
        }

        with patch.object(
            validator, "_execute_ffprobe", return_value=mock_probe_data
        ):
            result = await validator.verify_with_ffprobe(
                test_file, expected_sample_rate=44100
            )

            assert result.is_valid is False
            assert "sample rate" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_verify_with_ffprobe_invalid_channels(
        self, validator: AudioValidator, tmp_path: Path
    ):
        """Test FFprobe verification detects channel mismatches."""
        test_file = tmp_path / "test.flac"
        test_file.write_bytes(b"fLaC" + b"\x00" * 100)

        # Mock FFprobe output with unexpected channels
        mock_probe_data = {
            "streams": [
                {
                    "codec_type": "audio",
                    "codec_name": "flac",
                    "sample_rate": "44100",
                    "channels": 1,  # Mono instead of stereo
                }
            ]
        }

        with patch.object(
            validator, "_execute_ffprobe", return_value=mock_probe_data
        ):
            result = await validator.verify_with_ffprobe(
                test_file, expected_channels=2
            )

            assert result.is_valid is False
            assert "channel" in result.error_message.lower()

    # ============================================================================
    # Tests for Complete Validation
    # ============================================================================

    @pytest.mark.asyncio
    async def test_validate_complete_workflow_success(
        self, validator: AudioValidator, temp_audio_file: Path, temp_flac_file: Path
    ):
        """Test complete validation workflow from input to output."""
        # Validate input
        pre_result = await validator.validate_pre_conversion(temp_audio_file)
        assert pre_result.is_valid is True

        # Validate output
        post_result = await validator.validate_post_conversion(temp_flac_file)
        assert post_result.is_valid is True

    # ============================================================================
    # Tests for ValidationResult
    # ============================================================================

    def test_validation_result_success(self):
        """Test ValidationResult for successful validation."""
        result = ValidationResult(
            is_valid=True,
            file_path=Path("/test/file.mp3"),
        )

        assert result.is_valid is True
        assert result.error_message is None
        assert result.troubleshooting_hint is None
        assert result.metadata is None

    def test_validation_result_failure(self):
        """Test ValidationResult for failed validation."""
        result = ValidationResult(
            is_valid=False,
            file_path=Path("/test/file.mp3"),
            error_message="File is corrupted",
            troubleshooting_hint="Try re-downloading the file",
        )

        assert result.is_valid is False
        assert result.error_message == "File is corrupted"
        assert result.troubleshooting_hint == "Try re-downloading the file"

    # ============================================================================
    # Tests for Error Classes
    # ============================================================================

    def test_validation_error_base(self):
        """Test base ValidationError exception."""
        error = ValidationError("Test error", troubleshooting_hint="Fix it")

        assert str(error) == "Test error"
        assert error.troubleshooting_hint == "Fix it"

    def test_pre_conversion_validation_error(self):
        """Test PreConversionValidationError exception."""
        error = PreConversionValidationError(
            "File not found", troubleshooting_hint="Check file path"
        )

        assert str(error) == "File not found"
        assert error.troubleshooting_hint == "Check file path"
        assert isinstance(error, ValidationError)

    def test_post_conversion_validation_error(self):
        """Test PostConversionValidationError exception."""
        error = PostConversionValidationError(
            "Invalid FLAC header", troubleshooting_hint="Re-run conversion"
        )

        assert str(error) == "Invalid FLAC header"
        assert error.troubleshooting_hint == "Re-run conversion"
        assert isinstance(error, ValidationError)

    def test_ffprobe_validation_error(self):
        """Test FFprobeValidationError exception."""
        error = FFprobeValidationError(
            "Codec mismatch", troubleshooting_hint="Check encoding settings"
        )

        assert str(error) == "Codec mismatch"
        assert error.troubleshooting_hint == "Check encoding settings"
        assert isinstance(error, ValidationError)

    # ============================================================================
    # Tests for Performance
    # ============================================================================

    @pytest.mark.asyncio
    async def test_validation_performance_pre_conversion(
        self, validator: AudioValidator, temp_audio_file: Path
    ):
        """Test that pre-conversion validation completes quickly."""
        import time

        start_time = time.time()
        await validator.validate_pre_conversion(temp_audio_file)
        elapsed_time = time.time() - start_time

        # Should complete in less than 1 second
        assert elapsed_time < 1.0

    @pytest.mark.asyncio
    async def test_validation_performance_post_conversion(
        self, validator: AudioValidator, temp_flac_file: Path
    ):
        """Test that post-conversion validation completes quickly."""
        import time

        start_time = time.time()
        await validator.validate_post_conversion(temp_flac_file)
        elapsed_time = time.time() - start_time

        # Should complete in less than 1 second
        assert elapsed_time < 1.0
