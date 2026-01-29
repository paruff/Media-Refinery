package audio
package audio_test

import (
    "context"
    "os"
    "path/filepath"
    "testing"

    "github.com/paruff/media-refinery/pkg/audio"
    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/require"
)

// TestConverter_BuildFFmpegCommand tests command building logic
func TestConverter_BuildFFmpegCommand(t *testing.T) {
    tests := []struct {
        name     string
        input    string
        output   string
        format   string
        wantArgs []string
        wantErr  bool
    }{
        {
            name:   "MP3 to FLAC with metadata",
            input:  "/input/song.mp3",
            output: "/output/song.flac",
            format: "flac",
            wantArgs: []string{
                "-i", "/input/song.mp3",































































































}    }        })            }                assert.NoError(t, err)            } else {                assert.Error(t, err)            if tt.wantErr {            err := converter.ValidateInputFile(filePath)            converter := audio.NewConverter(audio.Config{})            filePath := tt.setup(t)        t.Run(tt.name, func(t *testing.T) {    for _, tt := range tests {    }        },            wantErr: true,            },                return file                require.NoError(t, os.WriteFile(file, []byte{}, 0644))                file := filepath.Join(tempDir, "empty.mp3")                tempDir := t.TempDir()            setup: func(t *testing.T) string {            name: "File is empty",        {        },            wantErr: true,            },                return "/nonexistent/file.mp3"            setup: func(t *testing.T) string {            name: "File does not exist",        {        },            wantErr: false,            },                return file                require.NoError(t, os.WriteFile(file, []byte("ID3..."), 0644))                // Create valid file                file := filepath.Join(tempDir, "valid.mp3")                tempDir := t.TempDir()            setup: func(t *testing.T) string {            name: "Valid MP3 file",        {    }{        wantErr bool        setup   func(t *testing.T) string // Returns file path        name    string    tests := []struct {func TestConverter_ValidateInputFile(t *testing.T) {// TestConverter_ValidateInputFile tests input validation}    }        })            assert.Equal(t, tt.wantArgs, args)            require.NoError(t, err)            }                return                assert.Error(t, err)            if tt.wantErr {            args, err := converter.BuildFFmpegCommand(tt.input, tt.output)            })                PreserveMetadata: true,                Format: tt.format,            converter := audio.NewConverter(audio.Config{        t.Run(tt.name, func(t *testing.T) {    for _, tt := range tests {    }        },            wantErr: true,            format:  "flac",            output:  "",            input:   "/input/song.mp3",            name:    "Empty output path",        {        },            wantErr: true,            format:  "flac",            output:  "/output/song.flac",            input:   "",            name:    "Empty input path",        {        },            wantErr: false,            },                "/output/song.flac",                "-map_metadata", "0",                "-compression_level", "5",                "-c:a", "flac",