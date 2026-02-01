# Test Audio Files

This directory contains minimal but valid audio files for testing the audio format detector.

## Files

- `sample.mp3` - MP3 file with ID3v2 header and MPEG-1 Layer 3 frame sync
- `sample.flac` - FLAC file with proper fLaC signature
- `sample.wav` - WAV file with RIFF/WAVE headers
- `sample.ogg` - OGG Vorbis file with OggS signature
- `sample.m4a` - M4A file with ftyp box
- `sample.aac` - AAC file with ADTS header
- `sample.opus` - OPUS file in OGG container with OpusHead marker
- `mp3_as_txt.txt` - MP3 content with wrong file extension (for testing extension-independent detection)

## Purpose

These files are used for integration testing of the audio format detection module. They are minimal valid files containing the proper magic numbers and headers required for format identification.

## Creation

Files are created programmatically with the correct magic numbers and minimal structure. They are not playable audio files but contain enough valid header information to be recognized by format detection tools like `file` command and FFprobe.
