"""Audio format detection module.

This module provides functionality to detect audio file formats from file content
(magic numbers) rather than relying on file extensions. It supports multiple
audio formats and includes FFprobe validation.
"""

import asyncio
import json
from enum import Enum
from pathlib import Path
from typing import Optional


class AudioFormat(str, Enum):
    """Supported audio formats."""

    MP3 = "MP3"
    AAC = "AAC"
    M4A = "M4A"
    OGG = "OGG"
    WAV = "WAV"
    OPUS = "OPUS"
    FLAC = "FLAC"


class UnsupportedAudioFormatError(Exception):
    """Raised when audio format is unsupported."""

    pass


class CorruptedAudioFileError(Exception):
    """Raised when audio file is corrupted or invalid."""

    pass


class AudioFormatDetector:
    """Detects audio file formats from content using magic numbers and FFprobe."""

    # Magic number signatures for audio formats
    MAGIC_NUMBERS = {
        # MP3 - ID3v2 tag or MPEG frame sync
        AudioFormat.MP3: [
            b"ID3",  # ID3v2 tag
            b"\xff\xfb",  # MPEG-1 Layer 3
            b"\xff\xf3",  # MPEG-1 Layer 3
            b"\xff\xf2",  # MPEG-2 Layer 3
        ],
        # FLAC - "fLaC" magic number
        AudioFormat.FLAC: [b"fLaC"],
        # OGG - "OggS" magic number (could be Vorbis or Opus)
        AudioFormat.OGG: [b"OggS"],
        # WAV - RIFF container with WAVE format
        AudioFormat.WAV: [b"RIFF"],  # Check for WAVE later
        # M4A/AAC - ISO Base Media File Format (ftyp box)
        AudioFormat.M4A: [
            b"\x00\x00\x00\x20ftypM4A ",
            b"\x00\x00\x00\x20ftypM4B ",
            b"\x00\x00\x00\x1cftypM4A",
            b"\x00\x00\x00\x20ftypmp42",
        ],
        # AAC - ADTS header
        AudioFormat.AAC: [
            b"\xff\xf1",  # ADTS sync word
            b"\xff\xf9",  # ADTS sync word variant
        ],
        # OPUS - in OGG container
        AudioFormat.OPUS: [b"OggS"],  # Requires deeper inspection
    }

    # Minimum file size to read for magic number detection (in bytes)
    MIN_READ_SIZE = 32

    def __init__(self):
        """Initialize AudioFormatDetector."""
        pass

    def detect_from_content(self, file_path: Path) -> AudioFormat:
        """Detect audio format from file content using magic numbers.

        Args:
            file_path: Path to the audio file

        Returns:
            AudioFormat enum value representing the detected format

        Raises:
            FileNotFoundError: If file doesn't exist
            CorruptedAudioFileError: If file is corrupted or too small
            UnsupportedAudioFormatError: If format is not supported
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Read the first bytes of the file
        try:
            with open(file_path, "rb") as f:
                header = f.read(self.MIN_READ_SIZE)
        except Exception as e:
            raise CorruptedAudioFileError(f"Failed to read file {file_path}: {e}")

        if len(header) == 0:
            raise CorruptedAudioFileError(f"File is empty: {file_path}")

        if len(header) < 4:
            raise CorruptedAudioFileError(
                f"File is too small to contain valid audio header: {file_path}"
            )

        # Check magic numbers for each format
        detected_format = self._match_magic_number(header)

        if detected_format is None:
            raise UnsupportedAudioFormatError(
                f"Unsupported or unrecognized audio format in file: {file_path}"
            )

        return detected_format

    def _match_magic_number(self, header: bytes) -> Optional[AudioFormat]:
        """Match header bytes against known magic numbers.

        Args:
            header: First bytes of the file

        Returns:
            AudioFormat if match found, None otherwise
        """
        # Check MP3
        for magic in self.MAGIC_NUMBERS[AudioFormat.MP3]:
            if header.startswith(magic):
                return AudioFormat.MP3

        # Check FLAC
        for magic in self.MAGIC_NUMBERS[AudioFormat.FLAC]:
            if header.startswith(magic):
                return AudioFormat.FLAC

        # Check WAV (RIFF + WAVE)
        if header.startswith(b"RIFF") and b"WAVE" in header[:16]:
            return AudioFormat.WAV

        # Check M4A/AAC container formats
        for magic in self.MAGIC_NUMBERS[AudioFormat.M4A]:
            if magic in header:
                return AudioFormat.M4A

        # Check AAC (ADTS)
        for magic in self.MAGIC_NUMBERS[AudioFormat.AAC]:
            if header.startswith(magic):
                return AudioFormat.AAC

        # Check OGG/OPUS (needs deeper inspection to differentiate)
        if header.startswith(b"OggS"):
            # Try to detect if it's Opus by looking for "OpusHead" in first page
            if b"OpusHead" in header:
                return AudioFormat.OPUS
            else:
                return AudioFormat.OGG

        return None

    async def validate_with_ffprobe(self, file_path: Path) -> bool:
        """Validate audio file using FFprobe.

        Args:
            file_path: Path to the audio file

        Returns:
            True if file is valid audio, False otherwise

        Raises:
            FileNotFoundError: If ffprobe is not installed
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_streams",
                "-show_format",
                str(file_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                return False

            # Parse JSON output
            try:
                probe_data = json.loads(stdout.decode())

                # Check if there's at least one audio stream
                if "streams" in probe_data:
                    audio_streams = [
                        s for s in probe_data["streams"] if s.get("codec_type") == "audio"
                    ]
                    return len(audio_streams) > 0

                return False

            except json.JSONDecodeError:
                return False

        except FileNotFoundError:
            # ffprobe not installed
            raise FileNotFoundError("ffprobe is not installed or not in PATH")

    async def detect_format(self, file_path: Path) -> AudioFormat:
        """Detect audio format using both magic numbers and FFprobe validation.

        This is the main detection method that combines content-based detection
        with FFprobe validation for increased accuracy.

        Args:
            file_path: Path to the audio file

        Returns:
            AudioFormat enum value representing the detected format

        Raises:
            FileNotFoundError: If file doesn't exist
            CorruptedAudioFileError: If file is corrupted
            UnsupportedAudioFormatError: If format is not supported
        """
        # First, detect from content
        format_from_content = self.detect_from_content(file_path)

        # Try to validate with ffprobe if available
        try:
            is_valid = await self.validate_with_ffprobe(file_path)
            if not is_valid:
                raise CorruptedAudioFileError(
                    f"File failed FFprobe validation: {file_path}"
                )
        except FileNotFoundError:
            # ffprobe not available, rely on content detection only
            pass

        return format_from_content

    def get_format_name(self, audio_format: AudioFormat) -> str:
        """Get human-readable format name.

        Args:
            audio_format: AudioFormat enum value

        Returns:
            String representation of the format
        """
        return audio_format.value

    def is_supported_format(self, audio_format: AudioFormat) -> bool:
        """Check if audio format is supported.

        Args:
            audio_format: AudioFormat enum value

        Returns:
            True if format is supported, False otherwise
        """
        return audio_format in AudioFormat
