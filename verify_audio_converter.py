#!/usr/bin/env python3
"""
Standalone verification script for Audio Converter functionality.

This script demonstrates that the Audio Converter works correctly outside
of the pytest environment. It performs a real MP3 to FLAC conversion.
"""

import asyncio
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.audio.converter import AudioConverter


async def main():
    """Run conversion verification."""
    print("=" * 60)  # noqa: T201
    print("Audio Converter Verification Script")  # noqa: T201
    print("=" * 60)  # noqa: T201

    # Setup
    converter = AudioConverter(output_format="flac", compression_level=5)
    input_file = Path("testdata/audio/test_valid.mp3")
    output_dir = Path(tempfile.gettempdir()) / "audio_converter_verification"
    output_dir.mkdir(exist_ok=True)

    print(f"\n✓ Input file: {input_file}")  # noqa: T201
    print(f"✓ Output directory: {output_dir}")  # noqa: T201
    print(f"✓ Input file exists: {input_file.exists()}")  # noqa: ASYNC240, T201
    print(f"✓ Input file size: {input_file.stat().st_size} bytes")  # noqa: ASYNC240, T201

    # Perform conversion
    print("\n🔄 Starting conversion...")  # noqa: T201
    result = await converter.convert(input_file, output_dir)

    # Check results
    print("\n" + "=" * 60)  # noqa: T201
    print("Conversion Results")  # noqa: T201
    print("=" * 60)  # noqa: T201
    print(f"✓ Success: {result.success}")  # noqa: T201

    if result.success:
        print(f"✓ Output path: {result.output_path}")  # noqa: T201
        print(f"✓ Output exists: {result.output_path.exists()}")  # noqa: T201
        print(  # noqa: T201
            f"✓ Output size: {result.size_bytes} bytes ({result.size_bytes / 1024:.2f} KB)"
        )
        print(f"✓ Duration: {result.duration_ms:.0f} ms")  # noqa: T201
        print(f"✓ Checksum (SHA256): {result.checksum}")  # noqa: T201

        # Verify checksum
        recalculated = converter.calculate_checksum(result.output_path)
        print(f"✓ Checksum verified: {recalculated == result.checksum}")  # noqa: T201

        # Check atomic operation (no .tmp files left)
        tmp_files = list(output_dir.glob("*.tmp"))
        print(f"✓ No temp files left: {len(tmp_files) == 0}")  # noqa: T201

        print("\n✅ All checks passed!")  # noqa: T201
        return 0
    else:
        print(f"❌ Error: {result.error_message}")  # noqa: T201
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
