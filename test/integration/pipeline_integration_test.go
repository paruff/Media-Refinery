package integration

import (
	"context"
	"encoding/binary"
	"os"
	"os/exec"
	"path/filepath"
	"testing"

	"github.com/paruff/Media-Refinery/pkg/config"
	"github.com/paruff/Media-Refinery/pkg/logger"
	"github.com/paruff/Media-Refinery/pkg/pipeline"
	"github.com/paruff/Media-Refinery/pkg/telemetry"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestPipelineIntegration_Run(t *testing.T) {

	// Table-driven tests for dry-run vs real conversion
	cases := []struct {
		name          string
		dryRun        bool
		expectOutput  bool
		requireFFMpeg bool
	}{
		{name: "dry-run", dryRun: true, expectOutput: false, requireFFMpeg: false},
		{name: "real-conversion", dryRun: false, expectOutput: true, requireFFMpeg: true},
	}

	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()

			// If real conversion is required but ffmpeg/ffprobe is not present, skip
			if tc.requireFFMpeg {
				if _, err := exec.LookPath("ffprobe"); err != nil {
					t.Skip("ffprobe not available in PATH; skipping real-conversion test")
				}
			}

			inputDir := t.TempDir()
			outputDir := t.TempDir()
			samplePath, _ := filepath.Abs("testdata/sample.mp3")
			// If MP3 sample is missing, fall back to a WAV sample (generated if needed).
			if _, err := os.Stat(samplePath); os.IsNotExist(err) {
				wavPath := filepath.Join("testdata", "sample.wav")
				if _, err := os.Stat(wavPath); os.IsNotExist(err) {
					// generate a tiny WAV file (1s silence)
					if err := os.MkdirAll(filepath.Dir(wavPath), 0755); err != nil {
						t.Fatalf("failed to create testdata dir: %v", err)
					}
					f, err := os.Create(wavPath)
					if err != nil {
						t.Fatalf("create wav sample: %v", err)
					}
					// write minimal WAV header + 1s silence (8kHz, 16-bit mono)
					sampleRate := uint32(8000)
					bitsPerSample := uint16(16)
					channels := uint16(1)
					byteRate := sampleRate * uint32(channels) * uint32(bitsPerSample/8)
					blockAlign := channels * (bitsPerSample / 8)
					durationSeconds := uint32(1)
					numSamples := sampleRate * durationSeconds
					dataSize := uint32(numSamples) * uint32(blockAlign)
					// RIFF
					f.Write([]byte("RIFF"))
					binary.Write(f, binary.LittleEndian, uint32(36+dataSize))
					f.Write([]byte("WAVE"))
					// fmt
					f.Write([]byte("fmt "))
					binary.Write(f, binary.LittleEndian, uint32(16))
					binary.Write(f, binary.LittleEndian, uint16(1))
					binary.Write(f, binary.LittleEndian, channels)
					binary.Write(f, binary.LittleEndian, sampleRate)
					binary.Write(f, binary.LittleEndian, byteRate)
					binary.Write(f, binary.LittleEndian, blockAlign)
					binary.Write(f, binary.LittleEndian, bitsPerSample)
					// data
					f.Write([]byte("data"))
					binary.Write(f, binary.LittleEndian, dataSize)
					silence := make([]byte, dataSize)
					f.Write(silence)
					f.Close()
				}
				samplePath = wavPath
			}
			dst := filepath.Join(inputDir, filepath.Base(samplePath))
			srcData, err := os.ReadFile(samplePath)
			require.NoError(t, err, "failed to read sample for integration test")
			require.NoError(t, os.WriteFile(dst, srcData, 0644), "failed to copy sample to temp input dir")

			log := logger.NewLogger("info", "text", os.Stdout)
			tel, err := telemetry.Initialize(context.Background(), "Media-Refinery", "1.0.0")
			require.NoError(t, err)

			cfg := config.Config{
				InputDir:  inputDir,
				OutputDir: outputDir,
				WorkDir:   t.TempDir(),
				DryRun:    tc.dryRun,
				Audio: config.AudioConfig{
					Enabled:        true,
					OutputFormat:   "flac",
					SupportedTypes: []string{"mp3", "flac", "aac", "m4a", "ogg", "wav"},
				},
				Video: config.VideoConfig{
					Enabled:        false,
					SupportedTypes: []string{"avi", "mp4", "mkv", "mov", "wmv", "flv"},
				},
			}

			pipe, err := pipeline.NewPipeline(&cfg, log, tel)
			require.NoError(t, err)
			ctx := context.Background()
			err = pipe.Run(ctx)
			require.NoError(t, err)

			outputFiles, err := os.ReadDir(outputDir)
			require.NoError(t, err)

			if tc.expectOutput {
				// Expect at least one .flac output file anywhere under outputDir
				foundFlac := false
				err = filepath.WalkDir(outputDir, func(path string, d os.DirEntry, err error) error {
					if err != nil {
						return err
					}
					if !d.IsDir() && filepath.Ext(d.Name()) == ".flac" {
						foundFlac = true
					}
					return nil
				})
				require.NoError(t, err)
				assert.True(t, foundFlac, "expected at least one .flac output file")
			} else {
				assert.Equal(t, 0, len(outputFiles))
			}
		})
	}
}
