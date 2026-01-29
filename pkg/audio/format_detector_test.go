package audio_test

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/paruff/Media-Refinery/pkg/audio"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestFormatDetector_SupportedFormats tests format support checking
func TestFormatDetector_SupportedFormats(t *testing.T) {
	detector := audio.NewFormatDetector()
	tests := []struct {
		format        string
		wantSupported bool
	}{
		{"mp3", true},
		{"aac", true},
		{"m4a", true},
		{"ogg", true},
		{"wav", true},
		{"flac", true},
		{"opus", true},
		{"wma", false},
		{"ape", false},
		{"mp4", false},
	}
	for _, tt := range tests {
		t.Run(tt.format, func(t *testing.T) {
			supported := detector.IsSupported(tt.format)
			assert.Equal(t, tt.wantSupported, supported)
		})
	}
}

// TestFormatDetector_ExtensionDetection tests format from extension
func TestFormatDetector_ExtensionDetection(t *testing.T) {
	detector := audio.NewFormatDetector()
	tests := []struct {
		filename   string
		wantFormat string
		wantErr    bool
	}{
		{"song.mp3", "mp3", false},
		{"song.MP3", "mp3", false},
		{"song.aac", "aac", false},
		{"song.unknown", "", true},
		{"no_extension", "", true},
	}
	for _, tt := range tests {
		t.Run(tt.filename, func(t *testing.T) {
			format, err := detector.DetectFromExtension(tt.filename)
			if tt.wantErr {
				assert.Error(t, err)
			} else {
				assert.NoError(t, err)
				assert.Equal(t, tt.wantFormat, format)
			}
		})
	}
}

// TestFormatDetector_MagicNumberDetection tests content-based detection
func TestFormatDetector_MagicNumberDetection(t *testing.T) {
	detector := audio.NewFormatDetector()
	tempDir := t.TempDir()
	tests := []struct {
		name       string
		content    []byte
		wantFormat string
	}{
		{"MP3 file", append([]byte{0xFF, 0xFB}, make([]byte, 100)...), "mp3"},
		{"FLAC file", append([]byte("fLaC"), make([]byte, 100)...), "flac"},
		{"WAV file", append([]byte("RIFF"), make([]byte, 100)...), "wav"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			testFile := filepath.Join(tempDir, "test")
			require.NoError(t, os.WriteFile(testFile, tt.content, 0644))
			format, err := detector.DetectFromContent(testFile)
			require.NoError(t, err)
			assert.Equal(t, tt.wantFormat, format)
		})
	}
}
