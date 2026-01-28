package pipeline

import (
	"context"
	"os"
	"path/filepath"
	"strconv"
	"testing"

	"github.com/paruff/Media-Refinery/pkg/config"
	"github.com/paruff/Media-Refinery/pkg/logger"
)

func BenchmarkPipeline_ProcessFiles(b *testing.B) {
	inputDir := b.TempDir()
	outputDir := b.TempDir()
	workDir := b.TempDir()

	// Create sample input files
	for i := 0; i < 100; i++ {
		inputFile := filepath.Join(inputDir, "sample"+strconv.Itoa(i)+".mp3")
		if err := os.WriteFile(inputFile, []byte("dummy audio data"), 0644); err != nil {
			b.Fatalf("Failed to create input file: %v", err)
		}
	}

	cfg := config.DefaultConfig()
	cfg.InputDir = inputDir
	cfg.OutputDir = outputDir
	cfg.WorkDir = workDir
	cfg.Audio.Enabled = true
	cfg.Video.Enabled = false

	log := logger.NewLogger("info", "text", os.Stdout)

	pipe, err := NewPipeline(cfg, log, nil)
	if err != nil {
		b.Fatalf("Failed to create pipeline: %v", err)
	}

	ctx := context.Background()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		if err := pipe.processFiles(ctx, nil); err != nil {
			b.Fatalf("Failed to process files: %v", err)
		}
	}
}
