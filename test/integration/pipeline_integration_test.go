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
		       samplePath, _ := filepath.Abs("testdata/sample.mp3")
		       if _, err := os.Stat(samplePath); err != nil {
			       t.Fatalf("sample.mp3 not found at %s: %v", samplePath, err)
		       }
		       dst := filepath.Join(inputDir, "sample.mp3")
		       srcData, err := os.ReadFile(samplePath)
		       require.NoError(t, err, "failed to read sample.mp3 for integration test")
		       require.NoError(t, os.WriteFile(dst, srcData, 0644), "failed to copy sample.mp3 to temp input dir")
		       log := logger.NewLogger("info", "text", os.Stdout)
		       tel, err := telemetry.Initialize(context.Background(), "Media-Refinery", "1.0.0")
		       require.NoError(t, err)
			       cfg := config.Config{
				       InputDir:  inputDir,
				       OutputDir: outputDir,
				       WorkDir:   t.TempDir(),
				       DryRun:    false,
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
		       // Verify output
		       outputFiles, err := os.ReadDir(outputDir)
		       require.NoError(t, err)
		       assert.Greater(t, len(outputFiles), 0)
	       })

	       t.Run("skips processing in dry-run mode", func(t *testing.T) {
		       inputDir := t.TempDir()
		       outputDir := t.TempDir()
		       samplePath, _ := filepath.Abs("testdata/sample.mp3")
		       if _, err := os.Stat(samplePath); err != nil {
			       t.Fatalf("sample.mp3 not found at %s: %v", samplePath, err)
		       }
		       dst := filepath.Join(inputDir, "sample.mp3")
		       srcData, err := os.ReadFile(samplePath)
		       require.NoError(t, err, "failed to read sample.mp3 for integration test (dry-run)")
		       require.NoError(t, os.WriteFile(dst, srcData, 0644), "failed to copy sample.mp3 to temp input dir (dry-run)")
		       log := logger.NewLogger("info", "text", os.Stdout)
		       tel, err := telemetry.Initialize(context.Background(), "Media-Refinery", "1.0.0")
		       require.NoError(t, err)
			       cfg := config.Config{
				       InputDir:  inputDir,
				       OutputDir: outputDir,
				       WorkDir:   t.TempDir(),
				       DryRun:    true,
				       Audio: config.AudioConfig{
					       Enabled:        true,
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
		       // Optionally: verify output is empty or unchanged in dry-run mode
		       outputFiles, err := os.ReadDir(outputDir)
		       require.NoError(t, err)
		       assert.Equal(t, 0, len(outputFiles))
	       })
}
