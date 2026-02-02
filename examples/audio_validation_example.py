"""Example demonstrating audio validation usage.

This example shows how to use the AudioValidator to validate audio files
before and after conversion.
"""

import asyncio
from pathlib import Path
from src.audio.validator import AudioValidator
from src.audio.converter import AudioConverter


async def validate_and_convert_example():
    """Example of validating input and output files during conversion."""
    
    # Initialize validator and converter
    validator = AudioValidator()
    converter = AudioConverter(output_format="flac", compression_level=8)
    
    # Example input file
    input_file = Path("sample_media/test.mp3")
    output_dir = Path("output")
    
    print("=" * 60)
    print("Audio Validation Example")
    print("=" * 60)
    
    # Step 1: Pre-conversion validation
    print("\n[1] Pre-conversion Validation")
    print("-" * 60)
    
    pre_result = await validator.validate_pre_conversion(input_file)
    
    if not pre_result.is_valid:
        print(f"❌ Validation failed: {pre_result.error_message}")
        print(f"💡 Hint: {pre_result.troubleshooting_hint}")
        return
    
    print("✅ Pre-conversion validation passed!")
    print(f"   File: {input_file}")
    
    # Step 2: Perform conversion (simulate)
    print("\n[2] Audio Conversion")
    print("-" * 60)
    print("Converting audio file...")
    # In a real scenario:
    # result = await converter.convert(input_file, output_dir)
    
    # For demonstration, assume output file was created
    output_file = output_dir / f"{input_file.stem}.flac"
    print(f"✅ Conversion complete: {output_file}")
    
    # Step 3: Post-conversion validation
    print("\n[3] Post-conversion Validation")
    print("-" * 60)
    
    # Assuming the file was created
    if not output_file.exists():
        print("⚠️  Output file not found (this is a demo)")
        print("   In production, this would validate the actual output")
        return
    
    post_result = await validator.validate_post_conversion(output_file)
    
    if not post_result.is_valid:
        print(f"❌ Validation failed: {post_result.error_message}")
        print(f"💡 Hint: {post_result.troubleshooting_hint}")
        return
    
    print("✅ Post-conversion validation passed!")
    
    # Step 4: FFprobe verification (optional but recommended)
    print("\n[4] FFprobe Verification")
    print("-" * 60)
    
    ffprobe_result = await validator.verify_with_ffprobe(
        output_file,
        expected_codec="flac",
        expected_sample_rate=44100,
        expected_channels=2
    )
    
    if not ffprobe_result.is_valid:
        print(f"❌ FFprobe verification failed: {ffprobe_result.error_message}")
        print(f"💡 Hint: {ffprobe_result.troubleshooting_hint}")
        return
    
    print("✅ FFprobe verification passed!")
    if ffprobe_result.metadata:
        print(f"   Codec: {ffprobe_result.metadata['codec_name']}")
        print(f"   Sample Rate: {ffprobe_result.metadata['sample_rate']} Hz")
        print(f"   Channels: {ffprobe_result.metadata['channels']}")
    
    print("\n" + "=" * 60)
    print("🎉 All validation checks passed!")
    print("=" * 60)


async def batch_validation_example():
    """Example of validating multiple files efficiently."""
    
    validator = AudioValidator()
    
    print("\n" + "=" * 60)
    print("Batch Validation Example")
    print("=" * 60)
    
    # List of files to validate
    files_to_validate = [
        Path("sample_media/sample.mp3"),
        Path("sample_media/sample.wav"),
        Path("sample_media/sample.ogg"),
    ]
    
    print(f"\nValidating {len(files_to_validate)} files...")
    
    # Validate all files concurrently
    results = await asyncio.gather(
        *[validator.validate_pre_conversion(f) for f in files_to_validate],
        return_exceptions=True
    )
    
    # Display results
    valid_count = 0
    invalid_count = 0
    
    for file_path, result in zip(files_to_validate, results):
        if isinstance(result, Exception):
            print(f"❌ {file_path.name}: Exception - {result}")
            invalid_count += 1
        elif result.is_valid:
            print(f"✅ {file_path.name}: Valid")
            valid_count += 1
        else:
            print(f"❌ {file_path.name}: {result.error_message}")
            invalid_count += 1
    
    print(f"\nSummary: {valid_count} valid, {invalid_count} invalid")


async def error_handling_example():
    """Example of handling validation errors gracefully."""
    
    validator = AudioValidator()
    
    print("\n" + "=" * 60)
    print("Error Handling Example")
    print("=" * 60)
    
    # Example of different error scenarios
    test_cases = [
        ("Non-existent file", Path("nonexistent.mp3")),
        ("Empty file", Path("empty.mp3")),
        ("Invalid format", Path("document.pdf")),
    ]
    
    for description, file_path in test_cases:
        print(f"\n[Test] {description}")
        print("-" * 60)
        
        result = await validator.validate_pre_conversion(file_path)
        
        if result.is_valid:
            print(f"✅ Validation passed")
        else:
            print(f"❌ Error: {result.error_message}")
            if result.troubleshooting_hint:
                print(f"💡 Troubleshooting hint:")
                print(f"   {result.troubleshooting_hint}")


if __name__ == "__main__":
    print("\n🎵 Media-Refinery Audio Validation Examples\n")
    
    # Run examples
    asyncio.run(validate_and_convert_example())
    asyncio.run(batch_validation_example())
    asyncio.run(error_handling_example())
    
    print("\n✨ Examples completed!\n")
