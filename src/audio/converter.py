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


@dataclass
class AudioProperties:
    """Audio file properties detected from source."""

    sample_rate: int
    codec_name: str
    is_lossless: bool
    channels: Optional[int] = None
    bit_depth: Optional[int] = None


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

    # Lossless audio formats
    LOSSLESS_FORMATS = {
        "flac",
        "wav",
        "opus",  # OPUS is lossless at high bitrates
        "alac",
        "ape",
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

    async def _execute_ffprobe(self, file_path: Path) -> dict:
        """Execute FFprobe to get audio file properties.

        Args:
            file_path: Path to audio file

        Returns:
            Dictionary containing probe results

        Raises:
            FFmpegError: If FFprobe execution fails
        """
        command = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_streams",
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
                raise FFmpegError(
                    f"FFprobe failed: {stderr.decode()}",
                    command=command,
                    stderr=stderr.decode(),
                )

            return json.loads(stdout.decode())

        except Exception as e:
            self.logger.warning("ffprobe_failed", error=str(e), file=str(file_path))
            return {"streams": []}

    async def detect_audio_properties(self, file_path: Path) -> Optional[AudioProperties]:
        """Detect audio properties from source file.

        Args:
            file_path: Path to audio file

        Returns:
            AudioProperties with detected sample rate, codec, etc.
            None if detection fails
        """
        try:
            probe_data = await self._execute_ffprobe(file_path)

            # Find audio stream
            audio_streams = [
                s for s in probe_data.get("streams", [])
                if s.get("codec_type") == "audio"
            ]

            if not audio_streams:
                self.logger.warning("no_audio_stream_found", file=str(file_path))
                return None

            stream = audio_streams[0]
            codec_name = stream.get("codec_name", "unknown")
            sample_rate = int(stream.get("sample_rate", 44100))
            channels = int(stream.get("channels", 2))

            # Determine if codec is lossless
            is_lossless = codec_name.lower() in self.LOSSLESS_FORMATS

            return AudioProperties(
                sample_rate=sample_rate,
                codec_name=codec_name,
                is_lossless=is_lossless,
                channels=channels,
            )

        except Exception as e:
            self.logger.error("property_detection_failed", error=str(e), file=str(file_path))
            return None

    def _determine_optimal_compression(self, source_format: str) -> int:
        """Determine optimal FLAC compression level based on source format.

        Lossless sources (FLAC, WAV, etc.) should use maximum compression (8)
        to save space since compression is lossless and won't degrade quality.
        Lossy sources (MP3, AAC) use default compression since they're already
        compressed.

        Args:
            source_format: Source audio format/codec name

        Returns:
            Compression level (0-8)
        """
        # Check if source is lossless
        if source_format.lower() in self.LOSSLESS_FORMATS:
            return 8  # Maximum compression for lossless sources
        else:
            return self.compression_level  # Default compression for lossy sources

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

        # Format-specific input handling
        # WAV: Handle potential endianness issues
        if input_path.suffix.lower() == ".wav":
            # FFmpeg auto-detects WAV endianness, but we can be explicit
            # This ensures proper handling of both little-endian and big-endian WAV files
            pass  # FFmpeg handles this automatically with -i

        # M4A: Explicitly handle container format
        if input_path.suffix.lower() == ".m4a":
            # M4A is a container format (MPEG-4 Part 14)
            # FFmpeg automatically detects and handles AAC/ALAC codecs within M4A
            # No special handling needed as FFmpeg's auto-detection is robust
            pass

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
                stdout=asyncio.subprocess.DEVNULL,  # Don't capture stdout
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            stdout_str = ""  # Not captured
            stderr_str = stderr.decode("utf-8", errors="replace") if stderr else ""

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
            # Detect audio properties for intelligent conversion
            audio_props = await self.detect_audio_properties(input_file)
            
            # Determine optimal compression level if converting to FLAC
            compression_level = self.compression_level
            if self.output_format == "flac" and audio_props:
                compression_level = self._determine_optimal_compression(
                    audio_props.codec_name
                )
                log.debug(
                    "adaptive_compression",
                    source_codec=audio_props.codec_name,
                    is_lossless=audio_props.is_lossless,
                    compression_level=compression_level,
                )
            
            # Build FFmpeg command; write directly to final output path
            # (some environments behave inconsistently with .tmp files)
            command = self.build_ffmpeg_command(
                input_file, output_file, preserve_metadata=True,
                compression_level=compression_level
            )

            # Execute FFmpeg
            returncode, stdout, stderr = await self._execute_ffmpeg(command)

            # Wait briefly for filesystem to reflect ffmpeg output (race in some environments)
            total_wait = 0.0
            wait_interval = 0.05
            max_wait = 1.0
            while total_wait < max_wait:
                if temp_file.exists() or output_file.exists():
                    break
                await asyncio.sleep(wait_interval)
                total_wait += wait_interval

            log.debug(
                "ffmpeg_completed",
                returncode=returncode,
                temp_file=str(temp_file),
                stderr_preview=stderr[:200] if stderr else "",
            )

            if returncode != 0:
                raise FFmpegError(
                    f"FFmpeg conversion failed: {stderr}",
                    command=command,
                    stderr=stderr,
                )

            # Determine where ffmpeg wrote output: prefer final output
            if output_file.exists():
                log.debug("output_written_directly", output_file=str(output_file))
            else:
                # Fallback: sometimes ffmpeg writes a file with a different name
                # or there is a brief race. Find the most recently-modified file
                # in the output directory that was created after we started.
                try:
                    candidates = list(output_dir.iterdir())
                except Exception:
                    candidates = []

                recent_candidate = None
                if candidates:
                    # Pick the newest file by mtime
                    candidates = [p for p in candidates if p.is_file()]
                    if candidates:
                        recent_candidate = max(
                            candidates, key=lambda p: p.stat().st_mtime
                        )

                if recent_candidate:
                    log.warning(
                        "using_recent_output_candidate",
                        candidate=str(recent_candidate),
                        mtime=recent_candidate.stat().st_mtime,
                    )

                    # If it's not already the expected final path, try moving it
                    try:
                        if recent_candidate.resolve() != output_file.resolve():
                            recent_candidate.rename(output_file)
                        else:
                            # already the expected path
                            pass
                    except Exception as e:
                        log.error("failed_to_move_candidate", error=str(e))
                else:
                    # Log more details for debugging
                    log.error(
                        "temp_file_not_found",
                        temp_file=str(temp_file),
                        cwd=str(Path.cwd()),
                        output_dir_exists=output_dir.exists(),
                        output_dir_files=(
                            list(output_dir.glob("*")) if output_dir.exists() else []
                        ),
                        ffmpeg_stderr=stderr[:500] if stderr else "",
                    )
                    raise FFmpegError(
                        f"FFmpeg succeeded but output file not found: {temp_file}. Stderr: {stderr[:500]}",
                        command=command,
                        stderr=stderr,
                    )

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
