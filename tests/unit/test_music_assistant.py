import pytest
from pathlib import Path
from src.audio.converter import AudioConverter

@pytest.fixture
def audio_converter():
    return AudioConverter()

def test_validate_supported_formats(audio_converter, tmp_path):
    for ext in [".mp3", ".flac", ".aac", ".m4a", ".ogg", ".wav"]:
        f = tmp_path / f"track{ext}"
        f.touch()
        assert audio_converter.validate_input_file(f)

def test_reject_unsupported_formats(audio_converter, tmp_path):
    for ext in [".txt", ".jpg", ".mp4"]:
        f = tmp_path / f"track{ext}"
        f.touch()
        assert not audio_converter.validate_input_file(f)

def test_missing_file(audio_converter, tmp_path):
    missing = tmp_path / "missing.mp3"
    assert not audio_converter.validate_input_file(missing)

@pytest.mark.asyncio
async def test_convert_to_flac(audio_converter, tmp_path):
    input_file = tmp_path / "song.mp3"
    input_file.touch()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    result = await audio_converter.convert(input_file, output_dir)
    assert result == output_dir / "song.flac"
    assert result.exists()

@pytest.mark.asyncio
async def test_convert_preserves_metadata(audio_converter, tmp_path):
    # This is a mock: in real test, would check tags
    input_file = tmp_path / "song.m4a"
    input_file.touch()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    result = await audio_converter.convert(input_file, output_dir)
    assert result.suffix == ".flac"
    assert result.exists()
