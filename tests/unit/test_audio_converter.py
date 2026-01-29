import pytest
from pathlib import Path
from src.audio.converter import AudioConverter

@pytest.fixture
def audio_converter():
    return AudioConverter()

def test_validate_input_file(audio_converter):
    valid_file = Path("test.mp3")
    invalid_file = Path("test.txt")

    valid_file.touch()
    assert audio_converter.validate_input_file(valid_file) is True
    assert audio_converter.validate_input_file(invalid_file) is False

@pytest.mark.asyncio
async def test_convert(audio_converter, tmp_path):
    input_file = tmp_path / "input.mp3"
    input_file.touch()
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    result = await audio_converter.convert(input_file, output_dir)

    assert result == output_dir / "input.flac"