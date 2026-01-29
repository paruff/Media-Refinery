package processor

import (
	"context"
	"fmt"
	"path/filepath"
	"sync"
	"sync/atomic"
	"time"

	"github.com/paruff/media-refinery/pkg/audio"
	"go.uber.org/zap"
)

// Config holds batch processor configuration
type Config struct {
    InputDir    string
    OutputDir   string
    Concurrency int
    AudioConfig audio.Config
}

// Progress represents processing progress
type Progress struct {
    Processed   int
    Total       int
    Percentage  float64
    CurrentFile string
    ETASeconds  float64
}

// Result holds batch processing result
type Result struct {
    TotalFiles  int
    Successful  int
    Failed      int
    FailedFiles []string
    Summary     string
    Duration    time.Duration
}

// BatchProcessor handles batch file processing
// Now supports idempotency and state management via audio.Converter
type BatchProcessor struct {
    config           Config
    converter        *audio.Converter
    logger           *zap.Logger
    progressCallback func(Progress)
}

// NewBatchProcessor creates a new batch processor
func NewBatchProcessor(config Config) *BatchProcessor {
    if config.Concurrency == 0 {
        config.Concurrency = 4
    }
    return &BatchProcessor{
        config: config,
        converter: audio.NewConverter(audio.Config{
            InputDir:         config.InputDir,
            OutputDir:        config.OutputDir,
            Format:           config.AudioConfig.Format,
            PreserveMetadata: config.AudioConfig.PreserveMetadata,
        }),
        logger: zap.L(),
    }
}

// SetProgressCallback sets the progress callback
func (bp *BatchProcessor) SetProgressCallback(callback func(Progress)) {
    bp.progressCallback = callback
}

// ProcessAll processes all files in the input directory
func (bp *BatchProcessor) ProcessAll(ctx context.Context) (*Result, error) {
    bp.logger.Info("starting batch processing",
        zap.String("input_dir", bp.config.InputDir),
        zap.Int("concurrency", bp.config.Concurrency),
    )
    startTime := time.Now()
    files, err := bp.findAudioFiles()
    if err != nil {
        return nil, fmt.Errorf("find audio files: %w", err)
    }
    if len(files) == 0 {
        return &Result{Summary: "No audio files found"}, nil
    }
    pool, err := NewWorkerPool(bp.config.Concurrency)
    if err != nil {
        return nil, fmt.Errorf("worker pool: %w", err)
    }
    defer pool.Close()
    var processed, successful, failed int32
    var failedFiles []string
    var mu sync.Mutex
    totalFiles := len(files)
    for _, file := range files {
        filePath := file
        task := func() error {
            // Idempotency: audio.Converter.ConvertFile now skips already-processed files
            _, err := bp.converter.ConvertFile(ctx, filePath)
            atomic.AddInt32(&processed, 1)
            if err != nil {
                atomic.AddInt32(&failed, 1)
                mu.Lock()
                failedFiles = append(failedFiles, filepath.Base(filePath))
                mu.Unlock()
                bp.logger.Error("conversion failed", zap.String("file", filePath), zap.Error(err))
            } else {
                atomic.AddInt32(&successful, 1)
            }
            if bp.progressCallback != nil {
                p := atomic.LoadInt32(&processed)
                progress := Progress{
                    Processed:   int(p),
                    Total:       totalFiles,
                    Percentage:  float64(p) / float64(totalFiles) * 100,
                    CurrentFile: filepath.Base(filePath),
                    ETASeconds:  bp.estimateETA(int(p), totalFiles, time.Since(startTime)),
                }
                bp.progressCallback(progress)
            }
            return err
        }
        if err := pool.Submit(ctx, task); err != nil {
            return nil, fmt.Errorf("submit task: %w", err)
        }
    }
    pool.Wait()
    duration := time.Since(startTime)
    result := &Result{
        TotalFiles:  totalFiles,
        Successful:  int(atomic.LoadInt32(&successful)),
        Failed:      int(atomic.LoadInt32(&failed)),
        FailedFiles: failedFiles,
        Duration:    duration,
    }
    result.Summary = fmt.Sprintf("%d of %d successful", result.Successful, result.TotalFiles)
    if result.Failed > 0 {
        result.Summary += fmt.Sprintf(", %d failed", result.Failed)
    }
    bp.logger.Info("batch processing complete",
        zap.Int("total", result.TotalFiles),
        zap.Int("successful", result.Successful),
        zap.Int("failed", result.Failed),
        zap.Duration("duration", duration),
    )
    return result, nil
}

// findAudioFiles finds all audio files in input directory
func (bp *BatchProcessor) findAudioFiles() ([]string, error) {
    patterns := []string{
        filepath.Join(bp.config.InputDir, "*.mp3"),
        filepath.Join(bp.config.InputDir, "*.aac"),
        filepath.Join(bp.config.InputDir, "*.m4a"),
        filepath.Join(bp.config.InputDir, "*.ogg"),
        filepath.Join(bp.config.InputDir, "*.wav"),
        filepath.Join(bp.config.InputDir, "*.opus"),
    }
    var files []string
    for _, pattern := range patterns {
        matches, err := filepath.Glob(pattern)
        if err != nil {
            return nil, fmt.Errorf("glob pattern %s: %w", pattern, err)
        }
        files = append(files, matches...)
    }
    return files, nil
}

// estimateETA estimates time remaining
func (bp *BatchProcessor) estimateETA(processed, total int, elapsed time.Duration) float64 {
    if processed == 0 {
        return 0
    }
    avgTimePerFile := elapsed.Seconds() / float64(processed)
    remaining := total - processed
    return avgTimePerFile * float64(remaining)
}
