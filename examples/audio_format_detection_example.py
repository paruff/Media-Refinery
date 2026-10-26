"""
Example usage of AudioFormatDetector.

This example demonstrates how to use the audio format detection module
to detect audio file formats from file content.
"""

import asyncio
from pathlib import Path

from src.audio.format_detector import (
    AudioFormat,
    AudioFormatDetector,
    CorruptedAudioFileError,
    UnsupportedAudioFormatError,
)


async def main():
    """Demonstrate audio format detection."""
    detector = AudioFormatDetector()

    # Example 1: Detect format from content only
    print("Example 1: Basic format detection")  # noqa: T201
    print("-" * 40)  # noqa: T201

    audio_file = Path("testdata/audio/sample.mp3")
    if audio_file.exists():  # noqa: ASYNC240
        try:
            format_detected = detector.detect_from_content(audio_file)
            print(f"File: {audio_file.name}")  # noqa: T201
            print(f"Detected format: {format_detected.value}")  # noqa: T201
            print()  # noqa: T201
        except (UnsupportedAudioFormatError, CorruptedAudioFileError) as e:
            print(f"Error: {e}")  # noqa: T201

    # Example 2: Detect with FFprobe validation
    print("Example 2: Detection with FFprobe validation")  # noqa: T201
    print("-" * 40)  # noqa: T201

    try:
        format_detected = await detector.detect_format(audio_file)
        print(f"File: {audio_file.name}")  # noqa: T201
        print(f"Detected format (validated): {format_detected.value}")  # noqa: T201
        print()  # noqa: T201
    except FileNotFoundError:
        print("FFprobe not available, falling back to content detection only")  # noqa: T201
        format_detected = detector.detect_from_content(audio_file)
        print(f"Detected format (no validation): {format_detected.value}")  # noqa: T201
        print()  # noqa: T201

    # Example 3: Handle files with wrong extensions
    print("Example 3: File with wrong extension")  # noqa: T201
    print("-" * 40)  # noqa: T201

    wrong_ext_file = Path("testdata/audio/mp3_as_txt.txt")
    if wrong_ext_file.exists():  # noqa: ASYNC240
        format_detected = detector.detect_from_content(wrong_ext_file)
        print(f"File: {wrong_ext_file.name} (has .txt extension)")  # noqa: T201
        print(f"Detected format: {format_detected.value} (detected from content)")  # noqa: T201
        print()  # noqa: T201

    # Example 4: Detect multiple formats
    print("Example 4: Batch detection")  # noqa: T201
    print("-" * 40)  # noqa: T201

    testdata_dir = Path("testdata/audio")
    for audio_file in testdata_dir.glob("sample.*"):  # noqa: ASYNC240
        if audio_file.suffix not in [".md", ".txt"]:
            try:
                format_detected = detector.detect_from_content(audio_file)
                print(f"{audio_file.name:20} -> {format_detected.value}")  # noqa: T201
            except UnsupportedAudioFormatError:
                print(f"{audio_file.name:20} -> UNSUPPORTED")  # noqa: T201

    print()  # noqa: T201

    # Example 5: Error handling
    print("Example 5: Error handling")  # noqa: T201
    print("-" * 40)  # noqa: T201

    # Test with unsupported format
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xyz") as tmp:
        tmp.write(b"INVALID\x00\x00\x00")
        tmp_path = Path(tmp.name)

    try:
        detector.detect_from_content(tmp_path)
    except UnsupportedAudioFormatError as e:
        print(f"Unsupported format error: {e}")  # noqa: T201
    finally:
        tmp_path.unlink()  # noqa: ASYNC240

    # Test with empty file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        tmp_path = Path(tmp.name)

    try:
        detector.detect_from_content(tmp_path)
    except CorruptedAudioFileError as e:
        print(f"Corrupted file error: {e}")  # noqa: T201
    finally:
        tmp_path.unlink()

    print()  # noqa: T201

    # Example 6: Utility methods
    print("Example 6: Utility methods")  # noqa: T201
    print("-" * 40)  # noqa: T201

    print(f"Format name for MP3: {detector.get_format_name(AudioFormat.MP3)}")  # noqa: T201
    print(f"Is FLAC supported? {detector.is_supported_format(AudioFormat.FLAC)}")  # noqa: T201
    print(f"All supported formats: {', '.join([f.value for f in AudioFormat])}")  # noqa: T201


if __name__ == "__main__":
    asyncio.run(main())
