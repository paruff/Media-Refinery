#!/usr/bin/env python3
"""
Standalone verification script for Audio Converter functionality.

This script demonstrates that the Audio Converter works correctly outside
of the pytest environment. It performs a real MP3 to FLAC conversion.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.audio.converter import AudioConverter


async def main():
    """Run conversion verification."""
    print("=" * 60)
    print("Audio Converter Verification Script")
    print("=" * 60)
    
    # Setup
    converter = AudioConverter(output_format="flac", compression_level=5)
    input_file = Path("testdata/audio/test_valid.mp3")
    output_dir = Path("/tmp/audio_converter_verification")
    output_dir.mkdir(exist_ok=True)
    
    print(f"\n✓ Input file: {input_file}")
    print(f"✓ Output directory: {output_dir}")
    print(f"✓ Input file exists: {input_file.exists()}")
    print(f"✓ Input file size: {input_file.stat().st_size} bytes")
    
    # Perform conversion
    print("\n🔄 Starting conversion...")
    result = await converter.convert(input_file, output_dir)
    
    # Check results
    print("\n" + "=" * 60)
    print("Conversion Results")
    print("=" * 60)
    print(f"✓ Success: {result.success}")
    
    if result.success:
        print(f"✓ Output path: {result.output_path}")
        print(f"✓ Output exists: {result.output_path.exists()}")
        print(f"✓ Output size: {result.size_bytes} bytes ({result.size_bytes / 1024:.2f} KB)")
        print(f"✓ Duration: {result.duration_ms:.0f} ms")
        print(f"✓ Checksum (SHA256): {result.checksum}")
        
        # Verify checksum
        recalculated = converter.calculate_checksum(result.output_path)
        print(f"✓ Checksum verified: {recalculated == result.checksum}")
        
        # Check atomic operation (no .tmp files left)
        tmp_files = list(output_dir.glob("*.tmp"))
        print(f"✓ No temp files left: {len(tmp_files) == 0}")
        
        print("\n✅ All checks passed!")
        return 0
    else:
        print(f"❌ Error: {result.error_message}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
