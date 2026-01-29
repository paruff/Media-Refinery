package acceptance_test

import (
    "context"
    "fmt"
    "os"
    "path/filepath"
    "testing"
    "time"

    "github.com/paruff/Media-Refinery/pkg/audio"
    "github.com/paruff/Media-Refinery/pkg/processor"
    "github.com/paruff/Media-Refinery/pkg/state"
    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/require"
)

// TestStory3_Idempotency_SkipAlreadyConverted tests duplicate detection
// ACCEPTANCE CRITERIA: Scenario 1
func TestStory3_Idempotency_SkipAlreadyConverted(t *testing.T) {
    ctx := context.Background()
    tempDir := t.TempDir()
    inputDir := filepath.Join(tempDir, "input")
    outputDir := filepath.Join(tempDir, "output")
    stateDir := filepath.Join(tempDir, "state")
    require.NoError(t, os.MkdirAll(inputDir, 0755))
    require.NoError(t, os.MkdirAll(outputDir, 0755))
    require.NoError(t, os.MkdirAll(stateDir, 0755))
    inputFile := filepath.Join(inputDir, "song.mp3")
    require.NoError(t, copyTestFile("testdata/audio/sample.mp3", inputFile))
    stateManager := state.NewManager(stateDir)
    converter := audio.NewConverter(audio.Config{
        InputDir:    inputDir,
        OutputDir:   outputDir,
        Format:      "flac",
        StateManager: stateManager,
    })
    result1, err := converter.ConvertFile(ctx, inputFile)
    require.NoError(t, err)







































































































































































































































}    return string(header) == "fLaC"    }        return false    if _, err := file.Read(header); err != nil {    header := make([]byte, 4)    defer file.Close()    }        return false    if err != nil {    file, err := os.Open(path)    t.Helper()func isValidFLAC(t *testing.T, path string) bool {}    assert.FileExists(t, outputFile)    assert.True(t, result.Success)    require.NoError(t, err)    result, err := converter.ConvertFile(ctx2, inputFile)    ctx2 := context.Background()    assert.Empty(t, tempFiles, "No temporary files should remain")    tempFiles, _ := filepath.Glob(filepath.Join(outputDir, "*.tmp"))    assert.NoFileExists(t, outputFile, "Final output should not exist")    outputFile := filepath.Join(outputDir, "song.flac")    assert.Contains(t, err.Error(), "context canceled")    assert.Error(t, err, "Should return cancellation error")    err := <-errChan    cancel()    time.Sleep(100 * time.Millisecond)    }()        errChan <- err        _, err := converter.ConvertFile(ctx, inputFile)    go func() {    errChan := make(chan error, 1)    })        Format:    "flac",        OutputDir: outputDir,        InputDir:  inputDir,    converter := audio.NewConverter(audio.Config{    require.NoError(t, copyTestFile("testdata/audio/sample.mp3", inputFile))    inputFile := filepath.Join(inputDir, "song.mp3")    require.NoError(t, os.MkdirAll(outputDir, 0755))    require.NoError(t, os.MkdirAll(inputDir, 0755))    outputDir := filepath.Join(tempDir, "output")    inputDir := filepath.Join(tempDir, "input")    tempDir := t.TempDir()    ctx, cancel := context.WithCancel(context.Background())func TestStory3_Idempotency_AtomicFileOperations(t *testing.T) {// ACCEPTANCE CRITERIA: Scenario 5// TestStory3_Idempotency_AtomicFileOperations tests atomic writes}    }        assert.True(t, isValidFLAC(t, outputFile), "Output %d should be valid", i)        outputFile := filepath.Join(outputDir, filename)        filename := fmt.Sprintf("song%02d.flac", i)    for i := 0; i < numFiles; i++ {    assert.Equal(t, 2, result.NewlyProcessed)    assert.Equal(t, 3, result.Reprocessed)    assert.Equal(t, 5, result.Skipped)    assert.Equal(t, numFiles, result.Successful)    assert.Equal(t, numFiles, result.TotalFiles)    require.NoError(t, err)    result, err := batchProcessor.ProcessAll(ctx)    })        },            StateManager: stateManager,            Format:       "flac",        AudioConfig: audio.Config{        Concurrency: 2,        OutputDir:   outputDir,        InputDir:    inputDir,    batchProcessor := processor.NewBatchProcessor(processor.Config{    }        require.NoError(t, os.WriteFile(outputFile, []byte("CORRUPT"), 0644))        outputFile := filepath.Join(outputDir, filename)        filename := fmt.Sprintf("song%02d.flac", i)    for i := 5; i < 8; i++ {    }        require.NoError(t, err)        _, err := converter.ConvertFile(ctx, inputFile)        inputFile := filepath.Join(inputDir, filename)        filename := fmt.Sprintf("song%02d.mp3", i)    for i := 0; i < 5; i++ {    })        StateManager: stateManager,        Format:       "flac",        OutputDir:    outputDir,        InputDir:     inputDir,    converter := audio.NewConverter(audio.Config{    stateManager := state.NewManager(stateDir)    }        require.NoError(t, copyTestFile("testdata/audio/sample.mp3", inputFile))        inputFile := filepath.Join(inputDir, filename)        filename := fmt.Sprintf("song%02d.mp3", i)    for i := 0; i < numFiles; i++ {    numFiles := 10    require.NoError(t, os.MkdirAll(stateDir, 0755))    require.NoError(t, os.MkdirAll(outputDir, 0755))    require.NoError(t, os.MkdirAll(inputDir, 0755))    stateDir := filepath.Join(tempDir, "state")    outputDir := filepath.Join(tempDir, "output")    inputDir := filepath.Join(tempDir, "input")    tempDir := t.TempDir()    ctx := context.Background()func TestStory3_Idempotency_CorruptOutputRecovery(t *testing.T) {// ACCEPTANCE CRITERIA: Scenario 4// TestStory3_Idempotency_CorruptOutputRecovery tests corrupt file handling}    }        assert.Greater(t, firstUpdate.Processed, 0, "Should start with skipped count")        firstUpdate := progressUpdates[0]    if len(progressUpdates) > 0 {    assert.Len(t, finalOutputFiles, numFiles)    finalOutputFiles, _ := filepath.Glob(filepath.Join(outputDir, "*.flac"))    assert.Equal(t, numFiles-processedCount, result.NewlyProcessed)    assert.Equal(t, processedCount, result.Skipped)    assert.Equal(t, numFiles, result.Successful)    assert.Equal(t, numFiles, result.TotalFiles)    assert.Contains(t, result.Summary, "Resuming", "Should indicate resumption")    require.NoError(t, err)    result, err := batchProcessor.ProcessAll(ctx)    })        progressUpdates = append(progressUpdates, p)    batchProcessor.SetProgressCallback(func(p processor.Progress) {    var progressUpdates []processor.Progress    })        },            StateManager: stateManager,            Format:       "flac",        AudioConfig: audio.Config{        Concurrency: 4,        OutputDir:   outputDir,        InputDir:    inputDir,    batchProcessor := processor.NewBatchProcessor(processor.Config{    require.Len(t, outputFiles, processedCount)    outputFiles, _ := filepath.Glob(filepath.Join(outputDir, "*.flac"))    }        require.NoError(t, err)        _, err := converter.ConvertFile(ctx, inputFile)        inputFile := filepath.Join(inputDir, filename)        filename := fmt.Sprintf("song%03d.mp3", i)    for i := 0; i < processedCount; i++ {    })        StateManager: stateManager,        Format:       "flac",        OutputDir:    outputDir,        InputDir:     inputDir,    converter := audio.NewConverter(audio.Config{    processedCount := 42    stateManager := state.NewManager(stateDir)    }        require.NoError(t, copyTestFile("testdata/audio/sample.mp3", inputFile))        inputFile := filepath.Join(inputDir, filename)        filename := fmt.Sprintf("song%03d.mp3", i)    for i := 0; i < numFiles; i++ {    numFiles := 100    require.NoError(t, os.MkdirAll(stateDir, 0755))    require.NoError(t, os.MkdirAll(outputDir, 0755))    require.NoError(t, os.MkdirAll(inputDir, 0755))    stateDir := filepath.Join(tempDir, "state")    outputDir := filepath.Join(tempDir, "output")    inputDir := filepath.Join(tempDir, "input")    tempDir := t.TempDir()    ctx := context.Background()    }        t.Skip("Skipping long recovery test in short mode")    if testing.Short() {func TestStory3_Idempotency_PartialBatchRecovery(t *testing.T) {// ACCEPTANCE CRITERIA: Scenario 3// TestStory3_Idempotency_PartialBatchRecovery tests batch recovery}    assert.Equal(t, newChecksum, storedChecksum)    require.NoError(t, err)    storedChecksum, err := stateManager.GetChecksum(outputFile)    assert.NotEqual(t, checksum1, newChecksum, "New checksum should be different")    newChecksum := result2.Checksum    assert.FileExists(t, outputFile)    assert.FileExists(t, backupFile, "Should create backup")    backupFile := filepath.Join(outputDir, "song.flac.bak")    assert.True(t, result2.Reprocessed, "Should indicate reprocessing")    assert.False(t, result2.Skipped, "Should not skip")    require.NoError(t, err)    result2, err := converter.ConvertFile(ctx, inputFile)    require.NoError(t, os.WriteFile(outputFile, []byte("MODIFIED"), 0644))    outputFile := filepath.Join(outputDir, "song.flac")    checksum1 := result1.Checksum    require.NoError(t, err)    result1, err := converter.ConvertFile(ctx, inputFile)    })        StateManager: stateManager,        Format:       "flac",        OutputDir:    outputDir,        InputDir:     inputDir,    converter := audio.NewConverter(audio.Config{    stateManager := state.NewManager(stateDir)    require.NoError(t, copyTestFile("testdata/audio/sample.mp3", inputFile))    inputFile := filepath.Join(inputDir, "song.mp3")    require.NoError(t, os.MkdirAll(stateDir, 0755))    require.NoError(t, os.MkdirAll(outputDir, 0755))    require.NoError(t, os.MkdirAll(inputDir, 0755))    stateDir := filepath.Join(tempDir, "state")    outputDir := filepath.Join(tempDir, "output")    inputDir := filepath.Join(tempDir, "input")    tempDir := t.TempDir()    ctx := context.Background()func TestStory3_Idempotency_ReprocessOnChecksumMismatch(t *testing.T) {// ACCEPTANCE CRITERIA: Scenario 2// TestStory3_Idempotency_ReprocessOnChecksumMismatch tests mismatch handling}    assert.Equal(t, info1.ModTime(), info2.ModTime(), "File should not be modified")    info2, _ := os.Stat(outputFile)    time.Sleep(100 * time.Millisecond)    info1, _ := os.Stat(outputFile)    assert.FileExists(t, outputFile)    assert.Equal(t, checksum1, result2.Checksum, "Checksum should match")    assert.Less(t, duration, 1*time.Second, "Should skip quickly")    assert.Equal(t, "already_converted", result2.SkipReason)    assert.True(t, result2.Skipped, "Should indicate file was skipped")    require.NoError(t, err, "Second conversion should succeed")    duration := time.Since(startTime)    result2, err := converter.ConvertFile(ctx, inputFile)    startTime := time.Now()    assert.NotEmpty(t, checksum1)    checksum1 := result1.Checksum    assert.FileExists(t, outputFile)    outputFile := filepath.Join(outputDir, "song.flac")    require.True(t, result1.Success)