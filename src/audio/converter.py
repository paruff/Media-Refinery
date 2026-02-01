"""Audio file conversion module.

This module provides functionality for converting audio files between different formats
using FFmpeg, with support for checksum calculation, atomic file operations, and 
structured logging.
"""

import asyncio
import hashlib
import json
import structlog
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass
class AudioConversionResult:
    """Result of an audio conversion operation."""

    success: bool
    output_path: Path
    checksum: str
    duration_ms: float
    size_bytes: int
    error_message: Optional[str] = None


class FFmpegError(Exception):
    """Raised when FFmpeg execution fails."""

    def __init__(self, message: str, command: List[str], stderr: str):
        super().__init__(message)
        self.command = command
        self.stderr = stderr


class AudioConverter:
    """
    Handles audio file conversion tasks using FFmpeg.
    
    Supports async conversion, checksum calculation, atomic file operations,
    and structured logging.
    """

    # Supported audio formats
    SUPPORTED_FORMATS = {
        ".mp3",
        ".flac",
        ".aac",
        ".m4a",
        ".ogg",
        ".wav",
        ".opus",
    }

    def __init__(
        self,
        output_format: str = "flac",
        sample_rate: Optional[int] = None,
        bit_depth: Optional[int] = None,
        compression_level: int = 5,
    ):
        """Initialize AudioConverter.

        Args:
            output_format: Target audio format (default: flac)
            sample_rate: Target sample rate in Hz (None = preserve original)
            bit_depth: Target bit depth (None = preserve original)
            compression_level: Compression level for FLAC (0-8, default: 5)
        """
        self.output_format = output_format
        self.sample_rate = sample_rate
        self.bit_depth = bit_depth
        self.compression_level = compression_level
        self.logger = structlog.get_logger(__name__)

    def build_ffmpeg_command(
        self,
        input_path: Path,
        output_path: Path,
        preserve_metadata: bool = True,
        compression_level: Optional[int] = None,
    ) -> List[str]:
        """Build FFmpeg command for audio conversion.

        Args:
            input_path: Path to input audio file
            output_path: Path to output audio file
            preserve_metadata: Whether to preserve metadata tags
            compression_level: Override default compression level

        Returns:
            List of command arguments for FFmpeg
        """
        command = [
            "ffmpeg",
            "-y",  # Overwrite output files without asking
            "-i",
            str(input_path),
        ]

        # Preserve metadata if requested
        if preserve_metadata:
            command.extend(["-map_metadata", "0"])

        # Set audio codec based on output format
        codec_map = {
            "flac": "flac",
            "mp3": "libmp3lame",
            "aac": "aac",
            "ogg": "libvorbis",
            "opus": "libopus",
            "wav": "pcm_s16le",
        }

        codec = codec_map.get(self.output_format, self.output_format)
        command.extend(["-c:a", codec])

        # Add format-specific options
        if self.output_format == "flac":
            comp_level = compression_level or self.compression_level
            command.extend(["-compression_level", str(comp_level)])

        # Set sample rate if specified
        if self.sample_rate:
            command.extend(["-ar", str(self.sample_rate)])

        # Set bit depth if specified (for PCM formats)
        if self.bit_depth and self.output_format in ["wav", "flac"]:
            if self.bit_depth == 16:
                command.extend(["-sample_fmt", "s16"])
            elif self.bit_depth == 24:
                command.extend(["-sample_fmt", "s24"])

        # Explicitly specify output format if output path has .tmp extension
        # This is needed for atomic file operations
        if str(output_path).endswith(".tmp"):
            command.extend(["-f", self.output_format])

        # Add output path
        command.append(str(output_path))

        return command

    async def _execute_ffmpeg(self, command: List[str]) -> Tuple[int, str, str]:
        """Execute FFmpeg command asynchronously.

        Args:
            command: FFmpeg command as list of arguments

        Returns:
            Tuple of (return_code, stdout, stderr)

        Raises:
            FFmpegError: If FFmpeg execution fails
        """
        self.logger.debug("executing_ffmpeg", command=" ".join(command))

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            return process.returncode, stdout_str, stderr_str

        except Exception as e:
            raise FFmpegError(
                f"Failed to execute FFmpeg: {e}", command=command, stderr=str(e)
            )

    def calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of a file.

        Args:
            file_path: Path to file

        Returns:
            Hexadecimal SHA256 checksum

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        sha256_hash = hashlib.sha256()

        with open(file_path, "rb") as f:
            # Read in chunks to handle large files
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)

        return sha256_hash.hexdigest()

    def get_temp_path(self, output_path: Path) -> Path:
        """Get temporary path for atomic file operations.

        Args:
            output_path: Final output path

        Returns:
            Temporary path with .tmp extension
        """
        return output_path.parent / f"{output_path.name}.tmp"

    async def _get_audio_duration(self, file_path: Path) -> float:
        """Get audio duration in milliseconds using FFprobe.

        Args:
            file_path: Path to audio file

        Returns:
            Duration in milliseconds
        """
        try:
            command = [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                str(file_path),
            ]

            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, _ = await process.communicate()

            if process.returncode == 0:
                data = json.loads(stdout.decode())
                duration_sec = float(data.get("format", {}).get("duration", 0))
                return duration_sec * 1000  # Convert to milliseconds

        except Exception as e:
            self.logger.warning("failed_to_get_duration", error=str(e))

        return 0.0

    async def convert(
        self, input_file: Path, output_dir: Path
    ) -> AudioConversionResult:
        """
        Converts an audio file to the specified format.

        Uses atomic file operations (write to .tmp, then rename) and
        calculates checksum of the output file.

        Args:
            input_file: Path to the input audio file
            output_dir: Directory where the converted file will be saved

        Returns:
            AudioConversionResult with success status and metadata

        Raises:
            FileNotFoundError: If input file doesn't exist
            FFmpegError: If conversion fails
        """
        # Validate input file
        if not input_file.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")

        # Create output directory if it doesn't exist
        output_dir.mkdir(parents=True, exist_ok=True)

        # Determine output path
        output_file = output_dir / f"{input_file.stem}.{self.output_format}"
        temp_file = self.get_temp_path(output_file)

        log = self.logger.bind(
            input_file=str(input_file),
            output_file=str(output_file),
            format=self.output_format,
        )

        log.info("starting_conversion")

        try:
            # Build FFmpeg command
            command = self.build_ffmpeg_command(
                input_file, temp_file, preserve_metadata=True
            )

            # Execute FFmpeg
            returncode, stdout, stderr = await self._execute_ffmpeg(command)

            log.debug("ffmpeg_completed", returncode=returncode, temp_file=str(temp_file), stderr_preview=stderr[:200] if stderr else "")

            if returncode != 0:
                raise FFmpegError(
                    f"FFmpeg conversion failed: {stderr}",
                    command=command,
                    stderr=stderr,
                )

            # Check if temp file was created
            if not temp_file.exists():
                # Log more details for debugging
                log.error(
                    "temp_file_not_found",
                    temp_file=str(temp_file),
                    cwd=str(Path.cwd()),
                    output_dir_exists=output_dir.exists(),
                    output_dir_files=list(output_dir.glob("*")) if output_dir.exists() else [],
                    ffmpeg_stderr=stderr[:500] if stderr else "",
                )
                raise FFmpegError(
                    f"FFmpeg succeeded but output file not found: {temp_file}. Stderr: {stderr[:500]}",
                    command=command,
                    stderr=stderr,
                )

            # Atomic rename: temp → final
            temp_file.rename(output_file)

            # Calculate checksum
            checksum = self.calculate_checksum(output_file)

            # Get file size
            size_bytes = output_file.stat().st_size

            # Get duration
            duration_ms = await self._get_audio_duration(output_file)

            log.info(
                "conversion_complete",
                size_bytes=size_bytes,
                duration_ms=duration_ms,
                checksum=checksum,
            )

            return AudioConversionResult(
                success=True,
                output_path=output_file,
                checksum=checksum,
                duration_ms=duration_ms,
                size_bytes=size_bytes,
            )

        except Exception as e:
            # Clean up temp file if it exists
            if temp_file.exists():
                temp_file.unlink()

            log.error("conversion_failed", error=str(e))

            return AudioConversionResult(
                success=False,
                output_path=output_file,
                checksum="",
                duration_ms=0.0,
                size_bytes=0,
                error_message=str(e),
            )

    def validate_input_file(self, input_file: Path) -> bool:
        """
        Validates the input audio file.

        Args:
            input_file: Path to the input audio file

        Returns:
            True if the file is valid, False otherwise
        """
        if not input_file.exists():
            self.logger.debug("validation_failed", reason="file_not_found")
            return False

        if input_file.suffix.lower() not in self.SUPPORTED_FORMATS:
            self.logger.debug(
                "validation_failed",
                reason="unsupported_format",
                format=input_file.suffix,
            )
            return False

        return True
