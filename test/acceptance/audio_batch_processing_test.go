package acceptance
package acceptance_test

import (
    "context"
    "fmt"
    "os"
    "path/filepath"
    "runtime"
    "sync"
    "sync/atomic"
    "testing"
    "time"

    "github.com/paruff/media-refinery/pkg/audio"
    "github.com/paruff/media-refinery/pkg/processor"
    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/require"
)

// TestStory2_BatchProcessing_ConcurrentWorkers tests concurrent processing
// ACCEPTANCE CRITERIA: Scenario 1
func TestStory2_BatchProcessing_ConcurrentWorkers(t *testing.T) {
    if testing.Short() {
        t.Skip("Skipping long-running batch test in short mode")
    }

    // ===== ARRANGE =====
    ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
    defer cancel()

    tempDir := t.TempDir()
    inputDir := filepath.Join(tempDir, "input")
    outputDir := filepath.Join(tempDir, "output")

    require.NoError(t, os.MkdirAll(inputDir, 0755))
    require.NoError(t, os.MkdirAll(outputDir, 0755))














































































































































































































































}    assert.Less(t, memoryMB, uint64(500), "Memory should be bounded")    memoryMB := m.Alloc / 1024 / 1024    runtime.ReadMemStats(&m)    var m runtime.MemStats    assert.Less(t, goroutineIncrease, 10, "Should not leak goroutines")    goroutineIncrease := finalGoroutines - initialGoroutines    finalGoroutines := runtime.NumGoroutine()    assert.LessOrEqual(t, maxProc, int32(4), "Should not exceed worker limit")    maxProc := atomic.LoadInt32(&maxActiveProcesses)    time.Sleep(1 * time.Second)    require.NoError(t, err)    _, err := batchProcessor.ProcessAll(ctx)    })        }            atomic.StoreInt32(&maxActiveProcesses, active)        if active > max {        max := atomic.LoadInt32(&maxActiveProcesses)        active := atomic.LoadInt32(&activeProcesses)    batchProcessor.SetProgressCallback(func(progress processor.Progress) {    initialGoroutines := runtime.NumGoroutine()    var maxActiveProcesses int32    var activeProcesses int32    })        AudioConfig: audio.Config{Format: "flac"},        Concurrency: 4,        OutputDir:   outputDir,        InputDir:    inputDir,    batchProcessor := processor.NewBatchProcessor(processor.Config{    }        require.NoError(t, copyTestFile("testdata/audio/sample.mp3", inputFile))        inputFile := filepath.Join(inputDir, filename)        filename := fmt.Sprintf("song%03d.mp3", i)    for i := 0; i < numFiles; i++ {    numFiles := 100    require.NoError(t, os.MkdirAll(outputDir, 0755))    require.NoError(t, os.MkdirAll(inputDir, 0755))    outputDir := filepath.Join(tempDir, "output")    inputDir := filepath.Join(tempDir, "input")    tempDir := t.TempDir()    defer cancel()    ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)    }        t.Skip("Skipping resource test in short mode")    if testing.Short() {func TestStory2_BatchProcessing_WorkerPoolLimits(t *testing.T) {// ACCEPTANCE CRITERIA: Scenario 4// TestStory2_BatchProcessing_WorkerPoolLimits tests resource limits}    assert.NoFileExists(t, filepath.Join(outputDir, "empty.flac"))    assert.NoFileExists(t, filepath.Join(outputDir, "corrupted.flac"))    assert.FileExists(t, filepath.Join(outputDir, "song3.flac"))    assert.FileExists(t, filepath.Join(outputDir, "song2.flac"))    assert.FileExists(t, filepath.Join(outputDir, "song1.flac"))    assert.Contains(t, result.Summary, "2 failed", "Summary should show failures")    assert.Contains(t, result.Summary, "3 of 5 successful", "Summary should show partial success")    assert.Contains(t, result.FailedFiles, "empty.mp3", "Should list empty file")    assert.Contains(t, result.FailedFiles, "corrupted.mp3", "Should list corrupted file")    assert.Len(t, result.FailedFiles, 2, "Should list failed files")    assert.Equal(t, 2, result.Failed, "Should fail for invalid files")    assert.Equal(t, 3, result.Successful, "Should succeed for valid files")    assert.Equal(t, 5, result.TotalFiles, "Should count all files")    require.NoError(t, err, "Should complete despite partial failures")    result, err := batchProcessor.ProcessAll(ctx)    })        AudioConfig: audio.Config{Format: "flac"},        Concurrency: 2,        OutputDir:   outputDir,        InputDir:    inputDir,    batchProcessor := processor.NewBatchProcessor(processor.Config{    }        }            require.NoError(t, os.WriteFile(inputFile, []byte("INVALID DATA"), 0644))        } else {            require.NoError(t, os.WriteFile(inputFile, []byte{}, 0644))        } else if filename == "empty.mp3" {            require.NoError(t, copyTestFile("testdata/audio/sample.mp3", inputFile))        if valid {        inputFile := filepath.Join(inputDir, filename)    for filename, valid := range files {    }        "song3.mp3":     true,        "empty.mp3":     false,        "song2.mp3":     true,        "corrupted.mp3": false,        "song1.mp3":     true,    files := map[string]bool{    require.NoError(t, os.MkdirAll(outputDir, 0755))    require.NoError(t, os.MkdirAll(inputDir, 0755))    outputDir := filepath.Join(tempDir, "output")    inputDir := filepath.Join(tempDir, "input")    tempDir := t.TempDir()    ctx := context.Background()func TestStory2_BatchProcessing_PartialFailures(t *testing.T) {// ACCEPTANCE CRITERIA: Scenario 3// TestStory2_BatchProcessing_PartialFailures tests failure handling}    }        assert.Greater(t, update.ETASeconds, float64(0), "Should calculate ETA")    for _, update := range progressUpdates[1:] {    }        }            assert.Contains(t, update.CurrentFile, ".mp3", "Should show current file")        if update.CurrentFile != "" {    for _, update := range progressUpdates {    }        )            "Progress should only increase",            progressUpdates[i-1].Processed,            progressUpdates[i].Processed,        assert.GreaterOrEqual(t,    for i := 1; i < len(progressUpdates); i++ {    assert.Equal(t, 100.0, lastUpdate.Percentage, "Last update should show 100%")    assert.Equal(t, numFiles, lastUpdate.Processed, "Last update should show all processed")    lastUpdate := progressUpdates[len(progressUpdates)-1]    assert.Equal(t, numFiles, firstUpdate.Total, "First update should show total")    assert.Equal(t, 0, firstUpdate.Processed, "First update should show 0 processed")    firstUpdate := progressUpdates[0]    assert.NotEmpty(t, progressUpdates, "Should receive progress updates")    defer mu.Unlock()    mu.Lock()    require.NoError(t, err)    _, err := batchProcessor.ProcessAll(ctx)    })        progressUpdates = append(progressUpdates, progress)        defer mu.Unlock()        mu.Lock()    batchProcessor.SetProgressCallback(func(progress processor.Progress) {    var mu sync.Mutex    var progressUpdates []processor.Progress    })        AudioConfig: audio.Config{Format: "flac"},        Concurrency: 4,        OutputDir:   outputDir,        InputDir:    inputDir,    batchProcessor := processor.NewBatchProcessor(processor.Config{    }        require.NoError(t, copyTestFile("testdata/audio/sample.mp3", inputFile))        inputFile := filepath.Join(inputDir, filename)        filename := fmt.Sprintf("song%02d.mp3", i)    for i := 0; i < numFiles; i++ {    numFiles := 50    require.NoError(t, os.MkdirAll(outputDir, 0755))    require.NoError(t, os.MkdirAll(inputDir, 0755))    outputDir := filepath.Join(tempDir, "output")    inputDir := filepath.Join(tempDir, "input")    tempDir := t.TempDir()    ctx := context.Background()func TestStory2_BatchProcessing_ProgressReporting(t *testing.T) {// ACCEPTANCE CRITERIA: Scenario 2// TestStory2_BatchProcessing_ProgressReporting tests progress updates}    assert.Less(t, memoryMB, uint64(500), "Memory should remain under 500 MB")    memoryMB := m.Alloc / 1024 / 1024    runtime.ReadMemStats(&m)    var m runtime.MemStats    assert.Less(t, duration, 300*time.Second, "Batch should be faster than sequential")    assert.Contains(t, result.Summary, "100 of 100 successful", "Summary should show results")    assert.NotEmpty(t, result.Summary, "Summary should be generated")    assert.Greater(t, maxWorkers, int32(0), "Should have used concurrent workers")    assert.LessOrEqual(t, maxWorkers, int32(4), "Should not exceed 4 concurrent workers")    maxWorkers := atomic.LoadInt32(&maxConcurrent)    assert.Len(t, outputFiles, numFiles, "All output files should exist")    require.NoError(t, err)    outputFiles, err := filepath.Glob(filepath.Join(outputDir, "*.flac"))    assert.Equal(t, 0, result.Failed, "No files should fail")    assert.Equal(t, numFiles, result.Successful, "All files should succeed")    assert.Equal(t, numFiles, result.TotalFiles, "Should process all files")    require.NotNil(t, result, "Result should not be nil")    require.NoError(t, err, "Batch processing should succeed")    // ===== ASSERT =====    duration := time.Since(startTime)    result, err := batchProcessor.ProcessAll(ctx)    startTime := time.Now()    // ===== ACT =====    })        }            atomic.StoreInt32(&maxConcurrent, current)        if current > max {        max := atomic.LoadInt32(&maxConcurrent)        current := atomic.LoadInt32(&currentConcurrent)    batchProcessor.SetProgressCallback(func(progress processor.Progress) {    var currentConcurrent int32    var maxConcurrent int32    })        },            PreserveMetadata: true,            Format:           "flac",        AudioConfig: audio.Config{        Concurrency: 4,        OutputDir:   outputDir,        InputDir:    inputDir,    batchProcessor := processor.NewBatchProcessor(processor.Config{    }        require.NoError(t, copyTestFile("testdata/audio/sample.mp3", inputFile))        inputFile := filepath.Join(inputDir, filename)        filename := fmt.Sprintf("song%03d.mp3", i)    for i := 0; i < numFiles; i++ {    numFiles := 100