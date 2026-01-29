package audio_test

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/paruff/Media-Refinery/pkg/audio"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestConverter_ValidateInputFile(t *testing.T) {
	tempDir := t.TempDir()
	tests := []struct {
		name    string
		setup   func(t *testing.T) string // returns file path
		wantErr bool
	}{
		{
			name: "File does not exist",
			setup: func(t *testing.T) string {
				return "/nonexistent/file.mp3"
			},
			wantErr: true,
		},
		{
			name: "File is empty",
			setup: func(t *testing.T) string {
				file := filepath.Join(tempDir, "empty.mp3")
				require.NoError(t, os.WriteFile(file, []byte{}, 0644))
				return file
			},
			wantErr: true,
		},
		{
			name: "Valid MP3 file",
			setup: func(t *testing.T) string {
				file := filepath.Join(tempDir, "valid.mp3")
				require.NoError(t, os.WriteFile(file, []byte("ID3..."), 0644))
				return file
			},
			wantErr: false,
		},
	}
	converter := audio.NewConverter(audio.Config{})
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			filePath := tt.setup(t)
			err := converter.ValidateInputFile(filePath)
			if tt.wantErr {
				assert.Error(t, err)
			} else {
				assert.NoError(t, err)
			}
		})
	}
}
