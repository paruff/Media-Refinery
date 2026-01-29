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



























































































}	}		})			assert.Equal(t, tt.wantFormat, format)			require.NoError(t, err)			format, err := detector.DetectFromContent(testFile)			require.NoError(t, os.WriteFile(testFile, tt.content, 0644))			testFile := filepath.Join(tempDir, "test")		t.Run(tt.name, func(t *testing.T) {	for _, tt := range tests {	}		},			wantFormat: "wav",			content:    append([]byte("RIFF"), make([]byte, 100)...),			name:       "WAV file",		{		},			wantFormat: "flac",			content:    append([]byte("fLaC"), make([]byte, 100)...),			name:       "FLAC file",		{		},			wantFormat: "mp3",			content:    append([]byte{0xFF, 0xFB}, make([]byte, 100)...),			name:       "MP3 file",		{	}{		wantFormat string		content    []byte		name       string	tests := []struct {	tempDir := t.TempDir()	detector := audio.NewFormatDetector()func TestFormatDetector_MagicNumberDetection(t *testing.T) {// TestFormatDetector_MagicNumberDetection tests content-based detection}	}		})			assert.Equal(t, tt.wantFormat, format)			require.NoError(t, err)			}				return				assert.Error(t, err)			if tt.wantErr {			format, err := detector.DetectFromExtension(tt.filename)		t.Run(tt.filename, func(t *testing.T) {	for _, tt := range tests {	}		{"no_extension", "", true},		{"song.unknown", "", true},		{"song.aac", "aac", false},		{"song.MP3", "mp3", false},		{"song.mp3", "mp3", false},	}{		wantErr    bool		wantFormat string		filename   string	tests := []struct {	detector := audio.NewFormatDetector()func TestFormatDetector_ExtensionDetection(t *testing.T) {// TestFormatDetector_ExtensionDetection tests format from extension}	}		})			assert.Equal(t, tt.wantSupported, supported)			supported := detector.IsSupported(tt.format)		t.Run(tt.format, func(t *testing.T) {	for _, tt := range tests {	}		{"mp4", false},		{"ape", false},		{"wma", false},		{"flac", true},		{"opus", true},		{"wav", true},		{"ogg", true},		{"m4a", true},		{"aac", true},		{"mp3", true},	}{		wantSupported bool