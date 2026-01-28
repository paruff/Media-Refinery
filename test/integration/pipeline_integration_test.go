package integration

import (
	"context"
	"os"
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
	t.Run("processes files end-to-end", func(t *testing.T) {
		inputDir := t.TempDir()
		outputDir := t.TempDir()
		workDir := t.TempDir()

		// Copy a real MP3 file from input/sample.mp3
		src := filepath.Join("input", "sample.mp3")
		dst := filepath.Join(inputDir, "sample.mp3")
		srcData, err := os.ReadFile(src)
		require.NoError(t, err, "failed to read input/sample.mp3 for integration test")
		require.NoError(t, os.WriteFile(dst, srcData, 0644), "failed to copy sample.mp3 to temp input dir")

		// Verify file copying
		copiedFile := filepath.Join(inputDir, "sample.mp3")
		require.FileExists(t, copiedFile, "sample.mp3 should exist in the temporary input directory")

		cfg := config.DefaultConfig()
		cfg.InputDir = inputDir
		cfg.OutputDir = outputDir
		cfg.WorkDir = workDir
		cfg.Audio.Enabled = true
		cfg.Video.Enabled = false

		log := logger.NewLogger("info", "text", os.Stdout)
		tel, err := telemetry.Initialize(context.Background(), "Media-Refinery", "1.0.0")
		require.NoError(t, err)

		pipe, err := pipeline.NewPipeline(cfg, log, tel)
		require.NoError(t, err)

		ctx := context.Background()
		err = pipe.Run(ctx)
		assert.NoError(t, err)

		// Verify output
		outputFiles, err := os.ReadDir(outputDir)
		require.NoError(t, err)
		assert.Greater(t, len(outputFiles), 0)
	})

	t.Run("skips processing in dry-run mode", func(t *testing.T) {
		inputDir := t.TempDir()
		outputDir := t.TempDir()
		workDir := t.TempDir()

		// Create sample input file
		inputFile := filepath.Join(inputDir, "sample.mp3")
		require.NoError(t, os.WriteFile(inputFile, []byte("dummy audio data"), 0644))

		cfg := config.DefaultConfig()
		cfg.InputDir = inputDir
		cfg.OutputDir = outputDir
		cfg.WorkDir = workDir
		cfg.DryRun = true
		cfg.Audio.Enabled = true
		cfg.Video.Enabled = false

		log := logger.NewLogger("info", "text", os.Stdout)
		tel, err := telemetry.Initialize(context.Background(), "Media-Refinery", "1.0.0")
		require.NoError(t, err)

		pipe, err := pipeline.NewPipeline(cfg, log, tel)
		require.NoError(t, err)

		ctx := context.Background()
		err = pipe.Run(ctx)
		assert.NoError(t, err)

		// Verify no output
		outputFiles, err := os.ReadDir(outputDir)
		require.NoError(t, err)
		assert.Equal(t, 0, len(outputFiles))
	})
}