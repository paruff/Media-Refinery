"""
Example usage of AudioFormatDetector.

This example demonstrates how to use the audio format detection module
to detect audio file formats from file content.
"""

import asyncio
from pathlib import Path
from src.audio.format_detector import (
    AudioFormatDetector,
    AudioFormat,
    UnsupportedAudioFormatError,
    CorruptedAudioFileError
)


async def main():
    """Demonstrate audio format detection."""
    detector = AudioFormatDetector()
    
    # Example 1: Detect format from content only
    print("Example 1: Basic format detection")
    print("-" * 40)
    
    audio_file = Path("testdata/audio/sample.mp3")
    if audio_file.exists():
        try:
            format_detected = detector.detect_from_content(audio_file)
            print(f"File: {audio_file.name}")
            print(f"Detected format: {format_detected.value}")
            print()
        except (UnsupportedAudioFormatError, CorruptedAudioFileError) as e:
            print(f"Error: {e}")
    
    # Example 2: Detect with FFprobe validation
    print("Example 2: Detection with FFprobe validation")
    print("-" * 40)
    
    try:
        format_detected = await detector.detect_format(audio_file)
        print(f"File: {audio_file.name}")
        print(f"Detected format (validated): {format_detected.value}")
        print()
    except FileNotFoundError:
        print("FFprobe not available, falling back to content detection only")
        format_detected = detector.detect_from_content(audio_file)
        print(f"Detected format (no validation): {format_detected.value}")
        print()
    
    # Example 3: Handle files with wrong extensions
    print("Example 3: File with wrong extension")
    print("-" * 40)
    
    wrong_ext_file = Path("testdata/audio/mp3_as_txt.txt")
    if wrong_ext_file.exists():
        format_detected = detector.detect_from_content(wrong_ext_file)
        print(f"File: {wrong_ext_file.name} (has .txt extension)")
        print(f"Detected format: {format_detected.value} (detected from content)")
        print()
    
    # Example 4: Detect multiple formats
    print("Example 4: Batch detection")
    print("-" * 40)
    
    testdata_dir = Path("testdata/audio")
    for audio_file in testdata_dir.glob("sample.*"):
        if audio_file.suffix not in [".md", ".txt"]:
            try:
                format_detected = detector.detect_from_content(audio_file)
                print(f"{audio_file.name:20} -> {format_detected.value}")
            except UnsupportedAudioFormatError:
                print(f"{audio_file.name:20} -> UNSUPPORTED")
    
    print()
    
    # Example 5: Error handling
    print("Example 5: Error handling")
    print("-" * 40)
    
    # Test with unsupported format
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xyz") as tmp:
        tmp.write(b"INVALID\x00\x00\x00")
        tmp_path = Path(tmp.name)
    
    try:
        detector.detect_from_content(tmp_path)
    except UnsupportedAudioFormatError as e:
        print(f"Unsupported format error: {e}")
    finally:
        tmp_path.unlink()
    
    # Test with empty file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        tmp_path = Path(tmp.name)
    
    try:
        detector.detect_from_content(tmp_path)
    except CorruptedAudioFileError as e:
        print(f"Corrupted file error: {e}")
    finally:
        tmp_path.unlink()
    
    print()
    
    # Example 6: Utility methods
    print("Example 6: Utility methods")
    print("-" * 40)
    
    print(f"Format name for MP3: {detector.get_format_name(AudioFormat.MP3)}")
    print(f"Is FLAC supported? {detector.is_supported_format(AudioFormat.FLAC)}")
    print(f"All supported formats: {', '.join([f.value for f in AudioFormat])}")


if __name__ == "__main__":
    asyncio.run(main())
