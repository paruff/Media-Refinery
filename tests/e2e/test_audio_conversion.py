import pytest
from pathlib import Path
from src.audio.converter import AudioConverter

@pytest.fixture
def audio_converter():
    return AudioConverter()

@pytest.mark.asyncio
@pytest.mark.e2e
async def test_audio_conversion_e2e(audio_converter, tmp_path):
    # Setup: Create a mock input audio file
    input_file = tmp_path / "input.mp3"
    input_file.write_text("mock audio content")

    # Setup: Define the output directory
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # Execute: Perform the audio conversion
    result = await audio_converter.convert(input_file, output_dir)

    # Verify: Check if the output file exists and has the correct format
    assert result == output_dir / "input.flac"
    assert result.exists()

    # Verify: Additional checks can be added for file content or metadata