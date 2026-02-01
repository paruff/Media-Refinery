"""Unit tests for audio format detection module."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from src.audio.format_detector import (
    AudioFormatDetector,
    UnsupportedAudioFormatError,
    CorruptedAudioFileError,
    AudioFormat,
)


class TestAudioFormatDetector:
    """Test suite for AudioFormatDetector class."""

    @pytest.fixture
    def detector(self):
        """Create AudioFormatDetector instance."""
        return AudioFormatDetector()

    @pytest.fixture
    def tmp_audio_file(self, tmp_path: Path) -> Path:
        """Create temporary audio file path."""
        return tmp_path / "test_audio.mp3"

    def test_detect_mp3_from_magic_number(self, detector: AudioFormatDetector, tmp_path: Path):
        """Test MP3 detection from ID3v2 magic number."""
        mp3_file = tmp_path / "test.mp3"
        # ID3v2 magic number
        mp3_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00")

        format_result = detector.detect_from_content(mp3_file)

        assert format_result == AudioFormat.MP3

    def test_detect_mp3_from_mpeg_sync(self, detector: AudioFormatDetector, tmp_path: Path):
        """Test MP3 detection from MPEG frame sync."""
        mp3_file = tmp_path / "test.mp3"
        # MPEG frame sync (0xFF 0xFB)
        mp3_file.write_bytes(b"\xff\xfb\x90\x00\x00\x00\x00\x00")

        format_result = detector.detect_from_content(mp3_file)

        assert format_result == AudioFormat.MP3

    def test_detect_flac_from_magic_number(self, detector: AudioFormatDetector, tmp_path: Path):
        """Test FLAC detection from magic number."""
        flac_file = tmp_path / "test.flac"
        # FLAC magic number
        flac_file.write_bytes(b"fLaC\x00\x00\x00\x22")

        format_result = detector.detect_from_content(flac_file)

        assert format_result == AudioFormat.FLAC

    def test_detect_ogg_from_magic_number(self, detector: AudioFormatDetector, tmp_path: Path):
        """Test OGG detection from magic number."""
        ogg_file = tmp_path / "test.ogg"
        # OGG magic number
        ogg_file.write_bytes(b"OggS\x00\x02\x00\x00")

        format_result = detector.detect_from_content(ogg_file)

        assert format_result in [AudioFormat.OGG, AudioFormat.OPUS]

    def test_detect_wav_from_magic_number(self, detector: AudioFormatDetector, tmp_path: Path):
        """Test WAV detection from magic number."""
        wav_file = tmp_path / "test.wav"
        # RIFF WAVE magic number
        wav_file.write_bytes(b"RIFF\x00\x00\x00\x00WAVEfmt ")

        format_result = detector.detect_from_content(wav_file)

        assert format_result == AudioFormat.WAV

    def test_detect_m4a_from_magic_number(self, detector: AudioFormatDetector, tmp_path: Path):
        """Test M4A/AAC detection from magic number."""
        m4a_file = tmp_path / "test.m4a"
        # ftyp box with M4A
        m4a_file.write_bytes(b"\x00\x00\x00\x20ftypM4A ")

        format_result = detector.detect_from_content(m4a_file)

        assert format_result in [AudioFormat.M4A, AudioFormat.AAC]

    def test_detect_aac_from_magic_number(self, detector: AudioFormatDetector, tmp_path: Path):
        """Test AAC detection from ADTS sync."""
        aac_file = tmp_path / "test.aac"
        # ADTS sync word (0xFF 0xF1)
        aac_file.write_bytes(b"\xff\xf1\x50\x80\x00\x1f\xfc")

        format_result = detector.detect_from_content(aac_file)

        assert format_result == AudioFormat.AAC

    def test_detect_with_wrong_extension(self, detector: AudioFormatDetector, tmp_path: Path):
        """Test detection works with wrong file extension."""
        # File has .txt extension but MP3 content
        wrong_ext_file = tmp_path / "audio.txt"
        wrong_ext_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00")

        format_result = detector.detect_from_content(wrong_ext_file)

        assert format_result == AudioFormat.MP3

    def test_unsupported_format_error(self, detector: AudioFormatDetector, tmp_path: Path):
        """Test error raised for unsupported format."""
        unsupported_file = tmp_path / "test.xyz"
        unsupported_file.write_bytes(b"RANDOM\x00\x00\x00\x00")

        with pytest.raises(UnsupportedAudioFormatError) as exc_info:
            detector.detect_from_content(unsupported_file)

        assert "unsupported" in str(exc_info.value).lower()

    def test_corrupted_file_error(self, detector: AudioFormatDetector, tmp_path: Path):
        """Test error raised for corrupted file."""
        corrupted_file = tmp_path / "test.mp3"
        # File too small to have valid header
        corrupted_file.write_bytes(b"ID")

        with pytest.raises(CorruptedAudioFileError) as exc_info:
            detector.detect_from_content(corrupted_file)

        assert "corrupted" in str(exc_info.value).lower()

    def test_file_not_found_error(self, detector: AudioFormatDetector, tmp_path: Path):
        """Test FileNotFoundError for non-existent file."""
        nonexistent = tmp_path / "nonexistent.mp3"

        with pytest.raises(FileNotFoundError):
            detector.detect_from_content(nonexistent)

    @pytest.mark.asyncio
    async def test_validate_with_ffprobe_success(
        self, detector: AudioFormatDetector, tmp_path: Path
    ):
        """Test FFprobe validation succeeds for valid audio."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00")

        # Mock ffprobe output
        mock_output = b'{"streams":[{"codec_type":"audio","codec_name":"mp3"}],"format":{"format_name":"mp3"}}'

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(mock_output, b""))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            is_valid = await detector.validate_with_ffprobe(audio_file)

            assert is_valid is True
            mock_subprocess.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_with_ffprobe_failure(
        self, detector: AudioFormatDetector, tmp_path: Path
    ):
        """Test FFprobe validation fails for invalid audio."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"INVALID")

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(b"", b"Invalid data"))
            mock_process.returncode = 1
            mock_subprocess.return_value = mock_process

            is_valid = await detector.validate_with_ffprobe(audio_file)

            assert is_valid is False

    @pytest.mark.asyncio
    async def test_detect_format_full_pipeline(
        self, detector: AudioFormatDetector, tmp_path: Path
    ):
        """Test full detection pipeline with content detection and FFprobe validation."""
        mp3_file = tmp_path / "test.mp3"
        mp3_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00")

        mock_output = b'{"streams":[{"codec_type":"audio","codec_name":"mp3"}],"format":{"format_name":"mp3"}}'

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(mock_output, b""))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            format_result = await detector.detect_format(mp3_file)

            assert format_result == AudioFormat.MP3

    @pytest.mark.asyncio
    async def test_detect_format_ffprobe_mismatch(
        self, detector: AudioFormatDetector, tmp_path: Path
    ):
        """Test detection when content and FFprobe disagree."""
        audio_file = tmp_path / "test.mp3"
        # Write FLAC magic number but name it .mp3
        audio_file.write_bytes(b"fLaC\x00\x00\x00\x22")

        mock_output = b'{"streams":[{"codec_type":"audio","codec_name":"flac"}],"format":{"format_name":"flac"}}'

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(mock_output, b""))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            format_result = await detector.detect_format(audio_file)

            # Should detect as FLAC based on content
            assert format_result == AudioFormat.FLAC

    def test_get_format_name(self, detector: AudioFormatDetector):
        """Test getting format name as string."""
        assert detector.get_format_name(AudioFormat.MP3) == "MP3"
        assert detector.get_format_name(AudioFormat.FLAC) == "FLAC"
        assert detector.get_format_name(AudioFormat.AAC) == "AAC"

    def test_is_supported_format(self, detector: AudioFormatDetector):
        """Test checking if format is supported."""
        assert detector.is_supported_format(AudioFormat.MP3) is True
        assert detector.is_supported_format(AudioFormat.FLAC) is True
        assert detector.is_supported_format(AudioFormat.WAV) is True

    @pytest.mark.parametrize(
        "magic_bytes,expected_format",
        [
            (b"ID3\x04\x00\x00\x00\x00\x00\x00", AudioFormat.MP3),
            (b"\xff\xfb\x90\x00\x00\x00\x00\x00", AudioFormat.MP3),
            (b"fLaC\x00\x00\x00\x22", AudioFormat.FLAC),
            (b"OggS\x00\x02\x00\x00", AudioFormat.OGG),
            (b"RIFF\x00\x00\x00\x00WAVEfmt ", AudioFormat.WAV),
            (b"\xff\xf1\x50\x80\x00\x1f\xfc", AudioFormat.AAC),
        ],
    )
    def test_magic_number_detection_parametrized(
        self, detector: AudioFormatDetector, tmp_path: Path, magic_bytes: bytes, expected_format: AudioFormat
    ):
        """Parametrized test for various magic number detections."""
        test_file = tmp_path / "test_audio"
        test_file.write_bytes(magic_bytes)

        format_result = detector.detect_from_content(test_file)

        assert format_result == expected_format

    def test_empty_file_error(self, detector: AudioFormatDetector, tmp_path: Path):
        """Test error raised for empty file."""
        empty_file = tmp_path / "empty.mp3"
        empty_file.write_bytes(b"")

        with pytest.raises(CorruptedAudioFileError) as exc_info:
            detector.detect_from_content(empty_file)

        assert "empty" in str(exc_info.value).lower() or "corrupted" in str(exc_info.value).lower()
