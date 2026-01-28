package validator

import (
	"os"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestValidateFile(t *testing.T) {
	tests := []struct {
		name        string
		path        string
		setup       func() string
		expectError bool
		expectType  MediaType
	}{
		{
			name: "Valid audio file",
			setup: func() string {
				       file, _ := os.CreateTemp("", "test")
				       defer func() {
					       if err := file.Close(); err != nil {
						       t.Errorf("failed to close file: %v", err)
					       }
				       }()
				mp3Data, _ := os.ReadFile("../../sample.mp3")
				if _, err := file.Write(mp3Data); err != nil {
					t.Fatalf("failed to write mp3 data: %v", err)
				}
				newPath := file.Name() + ".mp3"
				if err := os.Rename(file.Name(), newPath); err != nil {
					t.Fatalf("failed to rename file: %v", err)
				}
				return newPath
			},
			expectError: false,
			expectType:  AudioType,
		},
		{
			name:        "Non-existent file",
			path:        "nonexistent.mp3",
			expectError: true,
		},
		{
			name: "Directory instead of file",
			setup: func() string {
				dir, _ := os.MkdirTemp("", "testdir")
				return dir
			},
			expectError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			path := tt.path
			if tt.setup != nil {
				       path = tt.setup()
				       defer func() {
					       if err := os.RemoveAll(path); err != nil {
						       t.Errorf("failed to remove test file or dir: %v", err)
					       }
				       }()
			}

			validator := NewValidator([]string{"mp3"}, []string{"mp4"})
			fileInfo, err := validator.ValidateFile(path)

			if tt.expectError {
				require.Error(t, err)
				return
			}

			require.NoError(t, err)
			assert.Equal(t, tt.expectType, fileInfo.Type)
		})
	}
}

func TestComputeChecksum(t *testing.T) {
	tests := []struct {
		name        string
		content     string
		expectError bool
	}{
		{
			name:    "Valid file checksum",
			content: "test content",
		},
		{
			name:        "Non-existent file",
			expectError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var path string
			if tt.content != "" {
				       file, _ := os.CreateTemp("", "testfile")
				       defer func() {
					       if err := file.Close(); err != nil {
						       t.Errorf("failed to close file: %v", err)
					       }
				       }()
				if _, err := file.WriteString(tt.content); err != nil {
					t.Fatalf("failed to write string: %v", err)
				}
				path = file.Name()
			} else {
				path = "nonexistent.file"
			}

			validator := NewValidator(nil, nil)
			checksum, err := validator.ComputeChecksum(path)

			if tt.expectError {
				require.Error(t, err)
				return
			}

			require.NoError(t, err)
			assert.NotEmpty(t, checksum)
		})
	}
}

func TestProbeMediaFile(t *testing.T) {
	tests := []struct {
		name        string
		setup       func() string
		expectError bool
	}{
		{
			name: "Valid media file",
			setup: func() string {
				return "/Users/philruff/projects/github/paruff/Media-Refinery/input/sample2.mp3"
			},
		},
		{
			name:        "Non-existent file",
			expectError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var path string
			if tt.setup != nil {
				path = tt.setup()
				// Only run if file exists
				if _, err := os.Stat(path); os.IsNotExist(err) {
					t.Skipf("test file %s does not exist, skipping", path)
				}
			} else {
				path = "nonexistent.file"
			}

			validator := NewValidator([]string{"mp3"}, []string{"mp4"})
			err := validator.ProbeMediaFile(path)

			if tt.expectError {
				require.Error(t, err)
				return
			}

			require.NoError(t, err)
		})
	}
}
