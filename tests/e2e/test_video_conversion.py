import pytest
from src.video.converter import VideoConverter, Config


@pytest.fixture
def video_converter():
    config = Config(
        input_dir="/tmp/input",
        output_dir="/tmp/output",
        format="mkv",
        preserve_metadata=True,
        compression_level=5,
        dry_run=True,
        state_dir="/tmp/state",
    )
    return VideoConverter(config=config)


@pytest.mark.e2e
def test_video_conversion_e2e(video_converter, tmp_path):
    # Setup: Create a mock input video file
    input_file = tmp_path / "input.mp4"
    input_file.write_text("mock video content")

    # Setup: Define the output directory
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # Execute: Perform the video conversion
    result = video_converter.convert(input_file, output_dir)

    # Verify: Check if the output file exists and has the correct format
    assert result == output_dir / "input.mkv"
    assert result.exists()

    # Verify: Additional checks can be added for file content or metadata
