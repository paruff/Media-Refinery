

import (
    "testing"

    "github.com/paruff/media-refinery/pkg/audio"
    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/require"
)

// TestFormatDetection_AllFormats tests format detection for all supported types
func TestFormatDetection_AllFormats(t *testing.T) {
    if testing.Short() {
        t.Skip("Skipping integration test in short mode")
    }

    testCases := []struct {
        name       string
        file       string
        wantFormat string
    }{
        {"MP3 file", "testdata/audio/sample.mp3", "mp3"},
        {"AAC file", "testdata/audio/sample.aac", "aac"},
        {"M4A file", "testdata/audio/sample-alac.m4a", "m4a"},
        {"OGG file", "testdata/audio/sample.ogg", "ogg"},
        {"WAV file", "testdata/audio/sample.wav", "wav"},
        {"OPUS file", "testdata/audio/sample.opus", "opus"},
        {"FLAC file", "testdata/audio/sample.flac", "flac"},



































}    }        })            assert.Equal(t, tt.wantFormat, format)            format := detector.DetectFromMagicNumber(tt.magicBytes)        t.Run(tt.format, func(t *testing.T) {    for _, tt := range tests {    detector := audio.NewFormatDetector()    }        {"OGG", []byte{0x4F, 0x67, 0x67, 0x53}, "ogg"},        {"FLAC", []byte{0x66, 0x4C, 0x61, 0x43}, "flac"},        {"WAV", []byte{0x52, 0x49, 0x46, 0x46}, "wav"},        {"MP3", []byte{0xFF, 0xFB}, "mp3"},    }{        wantFormat string        magicBytes []byte        format     string    tests := []struct {func TestFormatDetection_MagicNumbers(t *testing.T) {// TestFormatDetection_MagicNumbers tests detection by file content}    }        })            assert.Equal(t, tc.wantFormat, format)            require.NoError(t, err)            format, err := detector.DetectFormat(tc.file)        t.Run(tc.name, func(t *testing.T) {    for _, tc := range testCases {    detector := audio.NewFormatDetector()    }