"""Audio validation module.

This module provides comprehensive validation for audio files before and after
conversion, including format detection, header verification, and FFprobe-based
audio stream validation.
"""

import asyncio
import json
import structlog
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Any

from src.audio.format_detector import (
    AudioFormatDetector,
    AudioFormat,
    UnsupportedAudioFormatError,
    CorruptedAudioFileError,
)


@dataclass
class ValidationResult:
    """Result of a validation operation."""

    is_valid: bool
    file_path: Path
    error_message: Optional[str] = None
    troubleshooting_hint: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ValidationError(Exception):
    """Base exception for validation errors."""

    def __init__(self, message: str, troubleshooting_hint: Optional[str] = None):
        super().__init__(message)
        self.troubleshooting_hint = troubleshooting_hint


class PreConversionValidationError(ValidationError):
    """Raised when pre-conversion validation fails."""

    pass


class PostConversionValidationError(ValidationError):
    """Raised when post-conversion validation fails."""

    pass


class FFprobeValidationError(ValidationError):
    """Raised when FFprobe validation fails."""

    pass


class AudioValidator:
    """
    Validates audio files before and after conversion.

    Provides comprehensive validation including:
    - File existence and readability checks
    - Format detection and validation
    - FLAC header verification
    - Audio stream validation
    - FFprobe-based codec, sample rate, and channel verification
    """

    # Supported audio formats for validation
    SUPPORTED_FORMATS = {
        ".mp3",
        ".flac",
        ".aac",
        ".m4a",
        ".ogg",
        ".wav",
        ".opus",
    }

    # FLAC magic number
    FLAC_MAGIC_NUMBER = b"fLaC"

    def __init__(self):
        """Initialize AudioValidator."""
        self.format_detector = AudioFormatDetector()
        self.logger = structlog.get_logger(__name__)

    async def validate_pre_conversion(self, file_path: Path) -> ValidationResult:
        """Validate audio file before conversion.

        Performs the following checks:
        1. File exists
        2. File is readable
        3. File format is valid and supported

        Args:
            file_path: Path to the audio file to validate

        Returns:
            ValidationResult indicating whether validation passed
        """
        log = self.logger.bind(file_path=str(file_path), validation_stage="pre_conversion")
        log.debug("starting_pre_conversion_validation")

        # Check file exists
        if not file_path.exists():
            error_msg = f"File not found: {file_path}"
            hint = "Check that the file path is correct and the file exists"
            log.warning("validation_failed", reason="file_not_found")
            return ValidationResult(
                is_valid=False,
                file_path=file_path,
                error_message=error_msg,
                troubleshooting_hint=hint,
            )

        # Check file is readable
        try:
            with open(file_path, "rb") as f:
                # Try to read first few bytes
                f.read(32)
        except PermissionError:
            error_msg = f"Permission denied: Cannot read file {file_path}"
            hint = "Check file permissions and ensure you have read access"
            log.warning("validation_failed", reason="permission_denied")
            return ValidationResult(
                is_valid=False,
                file_path=file_path,
                error_message=error_msg,
                troubleshooting_hint=hint,
            )
        except Exception as e:
            error_msg = f"Failed to read file: {e}"
            hint = "Ensure the file is not corrupted and is accessible"
            log.warning("validation_failed", reason="read_error", error=str(e))
            return ValidationResult(
                is_valid=False,
                file_path=file_path,
                error_message=error_msg,
                troubleshooting_hint=hint,
            )

        # Check file is not empty
        if file_path.stat().st_size == 0:
            error_msg = f"File is empty: {file_path}"
            hint = "Ensure the file contains valid audio data"
            log.warning("validation_failed", reason="empty_file")
            return ValidationResult(
                is_valid=False,
                file_path=file_path,
                error_message=error_msg,
                troubleshooting_hint=hint,
            )

        # Validate format using format detector
        try:
            detected_format = self.format_detector.detect_from_content(file_path)
            log.debug("format_detected", format=detected_format.value)
        except CorruptedAudioFileError as e:
            error_msg = f"Corrupted audio file: {e}"
            hint = "The file appears to be corrupted. Try re-downloading or re-encoding the file"
            log.warning("validation_failed", reason="corrupted_file", error=str(e))
            return ValidationResult(
                is_valid=False,
                file_path=file_path,
                error_message=error_msg,
                troubleshooting_hint=hint,
            )
        except UnsupportedAudioFormatError as e:
            error_msg = f"Unsupported audio format: {e}"
            hint = f"Supported formats: {', '.join(self.SUPPORTED_FORMATS)}"
            log.warning("validation_failed", reason="unsupported_format", error=str(e))
            return ValidationResult(
                is_valid=False,
                file_path=file_path,
                error_message=error_msg,
                troubleshooting_hint=hint,
            )
        except Exception as e:
            error_msg = f"Format detection failed: {e}"
            hint = "Check that the file is a valid audio file"
            log.error("validation_failed", reason="format_detection_error", error=str(e))
            return ValidationResult(
                is_valid=False,
                file_path=file_path,
                error_message=error_msg,
                troubleshooting_hint=hint,
            )

        log.info("pre_conversion_validation_passed")
        return ValidationResult(is_valid=True, file_path=file_path)

    async def validate_post_conversion(self, file_path: Path) -> ValidationResult:
        """Validate audio file after conversion.

        Performs the following checks:
        1. File exists
        2. FLAC header is valid (if FLAC file)
        3. Audio stream is valid

        Args:
            file_path: Path to the converted audio file

        Returns:
            ValidationResult indicating whether validation passed
        """
        log = self.logger.bind(file_path=str(file_path), validation_stage="post_conversion")
        log.debug("starting_post_conversion_validation")

        # Check file exists
        if not file_path.exists():
            error_msg = f"Output file not found: {file_path}"
            hint = "The conversion may have failed. Check conversion logs"
            log.warning("validation_failed", reason="file_not_found")
            return ValidationResult(
                is_valid=False,
                file_path=file_path,
                error_message=error_msg,
                troubleshooting_hint=hint,
            )

        # Validate FLAC header if it's a FLAC file
        if file_path.suffix.lower() == ".flac":
            if not await self._validate_flac_header(file_path):
                error_msg = f"Invalid FLAC header in file: {file_path}"
                hint = "The FLAC file may be corrupted. Try re-running the conversion"
                log.warning("validation_failed", reason="invalid_flac_header")
                return ValidationResult(
                    is_valid=False,
                    file_path=file_path,
                    error_message=error_msg,
                    troubleshooting_hint=hint,
                )

        # Validate audio stream
        if not await self._validate_audio_stream(file_path):
            error_msg = f"Invalid or corrupted audio stream in file: {file_path}"
            hint = "The audio stream is corrupted. Try re-running the conversion with different settings"
            log.warning("validation_failed", reason="invalid_audio_stream")
            return ValidationResult(
                is_valid=False,
                file_path=file_path,
                error_message=error_msg,
                troubleshooting_hint=hint,
            )

        log.info("post_conversion_validation_passed")
        return ValidationResult(is_valid=True, file_path=file_path)

    async def verify_with_ffprobe(
        self,
        file_path: Path,
        expected_codec: Optional[str] = None,
        expected_sample_rate: Optional[int] = None,
        expected_channels: Optional[int] = None,
    ) -> ValidationResult:
        """Verify audio file properties using FFprobe.

        Args:
            file_path: Path to the audio file
            expected_codec: Expected codec name (e.g., "flac", "mp3")
            expected_sample_rate: Expected sample rate in Hz (e.g., 44100)
            expected_channels: Expected number of channels (e.g., 2 for stereo)

        Returns:
            ValidationResult with metadata if valid
        """
        log = self.logger.bind(file_path=str(file_path), validation_stage="ffprobe")
        log.debug("starting_ffprobe_verification")

        try:
            probe_data = await self._execute_ffprobe(file_path)
        except Exception as e:
            error_msg = f"FFprobe execution failed: {e}"
            hint = "Ensure FFmpeg/FFprobe is installed and accessible"
            log.error("ffprobe_failed", error=str(e))
            return ValidationResult(
                is_valid=False,
                file_path=file_path,
                error_message=error_msg,
                troubleshooting_hint=hint,
            )

        # Find audio stream
        audio_streams = [
            s for s in probe_data.get("streams", [])
            if s.get("codec_type") == "audio"
        ]

        if not audio_streams:
            error_msg = f"No audio stream found in file: {file_path}"
            hint = "The file may be corrupted or not contain audio data"
            log.warning("validation_failed", reason="no_audio_stream")
            return ValidationResult(
                is_valid=False,
                file_path=file_path,
                error_message=error_msg,
                troubleshooting_hint=hint,
            )

        stream = audio_streams[0]
        codec_name = stream.get("codec_name", "unknown")
        sample_rate = stream.get("sample_rate", "unknown")
        channels = stream.get("channels", 0)

        # Verify codec if expected
        if expected_codec and codec_name != expected_codec:
            error_msg = f"Codec mismatch: expected {expected_codec}, got {codec_name}"
            hint = f"Check conversion settings to ensure output codec is set to {expected_codec}"
            log.warning(
                "validation_failed",
                reason="codec_mismatch",
                expected=expected_codec,
                actual=codec_name,
            )
            return ValidationResult(
                is_valid=False,
                file_path=file_path,
                error_message=error_msg,
                troubleshooting_hint=hint,
            )

        # Verify sample rate if expected
        if expected_sample_rate and str(sample_rate) != str(expected_sample_rate):
            error_msg = f"Sample rate mismatch: expected {expected_sample_rate}Hz, got {sample_rate}Hz"
            hint = f"Check conversion settings to ensure sample rate is set to {expected_sample_rate}Hz"
            log.warning(
                "validation_failed",
                reason="sample_rate_mismatch",
                expected=expected_sample_rate,
                actual=sample_rate,
            )
            return ValidationResult(
                is_valid=False,
                file_path=file_path,
                error_message=error_msg,
                troubleshooting_hint=hint,
            )

        # Verify channels if expected
        if expected_channels and channels != expected_channels:
            error_msg = f"Channel count mismatch: expected {expected_channels}, got {channels}"
            hint = f"Check conversion settings to ensure channel count is set to {expected_channels}"
            log.warning(
                "validation_failed",
                reason="channel_mismatch",
                expected=expected_channels,
                actual=channels,
            )
            return ValidationResult(
                is_valid=False,
                file_path=file_path,
                error_message=error_msg,
                troubleshooting_hint=hint,
            )

        # Collect metadata
        metadata = {
            "codec_name": codec_name,
            "sample_rate": sample_rate,
            "channels": channels,
            "bit_rate": stream.get("bit_rate"),
            "duration": stream.get("duration"),
        }

        log.info("ffprobe_verification_passed", metadata=metadata)
        return ValidationResult(
            is_valid=True,
            file_path=file_path,
            metadata=metadata,
        )

    async def _validate_flac_header(self, file_path: Path) -> bool:
        """Validate FLAC file header.

        Args:
            file_path: Path to FLAC file

        Returns:
            True if header is valid, False otherwise
        """
        try:
            with open(file_path, "rb") as f:
                header = f.read(4)
                return header == self.FLAC_MAGIC_NUMBER
        except Exception as e:
            self.logger.warning("flac_header_validation_failed", error=str(e))
            return False

    async def _validate_audio_stream(self, file_path: Path) -> bool:
        """Validate audio stream using FFprobe.

        Args:
            file_path: Path to audio file

        Returns:
            True if stream is valid, False otherwise
        """
        try:
            probe_data = await self._execute_ffprobe(file_path)
            audio_streams = [
                s for s in probe_data.get("streams", [])
                if s.get("codec_type") == "audio"
            ]
            return len(audio_streams) > 0
        except Exception as e:
            self.logger.warning("audio_stream_validation_failed", error=str(e))
            return False

    async def _execute_ffprobe(self, file_path: Path) -> dict:
        """Execute FFprobe to get audio file properties.

        Args:
            file_path: Path to audio file

        Returns:
            Dictionary containing probe results

        Raises:
            Exception: If FFprobe execution fails
        """
        command = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(file_path),
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                raise Exception(f"FFprobe failed: {stderr.decode()}")

            return json.loads(stdout.decode())

        except FileNotFoundError:
            raise Exception("FFprobe not found. Please install FFmpeg.")
        except Exception as e:
            raise Exception(f"FFprobe execution error: {e}")
