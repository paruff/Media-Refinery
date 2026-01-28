package integration

import (
	"context"
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/paruff/media-refinery/pkg/config"
	"github.com/paruff/media-refinery/pkg/logger"
	"github.com/paruff/media-refinery/pkg/pipeline"
	"github.com/paruff/media-refinery/pkg/telemetry"
)

func TestPipelineIntegration_Run(t *testing.T) {
	t.Run("processes files end-to-end", func(t *testing.T) {
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
		cfg.Audio.Enabled = true
		cfg.Video.Enabled = false

		log := logger.NewLogger("info", "text", "")
		tel := telemetry.NewProvider()

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

		log := logger.NewLogger("info", "text", "")
		tel := telemetry.NewProvider()

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