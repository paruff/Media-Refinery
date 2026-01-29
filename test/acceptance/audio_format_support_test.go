package acceptance_test

import (
	"context"
	"os"
	"path/filepath"
	"testing"

    "github.com/paruff/Media-Refinery/pkg/audio"
    "github.com/paruff/Media-Refinery/pkg/processor"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestStory4_FormatSupport_AllFormatsConvert tests multi-format conversion
// ACCEPTANCE CRITERIA: Scenario 1
func TestStory4_FormatSupport_AllFormatsConvert(t *testing.T) {
    if testing.Short() {
        t.Skip("Skipping format support test in short mode")
    }

    // ===== ARRANGE =====
    ctx := context.Background()

    tempDir := t.TempDir()
    inputDir := filepath.Join(tempDir, "input")
    outputDir := filepath.Join(tempDir, "output")

    require.NoError(t, os.MkdirAll(inputDir, 0755))
    require.NoError(t, os.MkdirAll(outputDir, 0755))

    // Define test files for each format
    testFiles := []struct {
        filename     string
        sourceFormat string
        testdataFile string
        isLossless   bool
    }{
        {"song1.mp3", "mp3", "testdata/audio/sample.mp3", false},
        {"song2.aac", "aac", "testdata/audio/sample.aac", false},
        {"song3.m4a", "m4a", "testdata/audio/sample-alac.m4a", true},
        {"song4.ogg", "ogg", "testdata/audio/sample.ogg", false},
        {"song5.wav", "wav", "testdata/audio/sample.wav", true},
        {"song6.opus", "opus", "testdata/audio/sample.opus", false},
    }

    // Copy test files
    for _, tf := range testFiles {
        inputFile := filepath.Join(inputDir, tf.filename)
        require.NoError(t, copyTestFile(tf.testdataFile, inputFile),
            "Failed to copy %s", tf.filename)
    }

    // Create batch processor
    batchProcessor := processor.NewBatchProcessor(processor.Config{
        InputDir:  inputDir,
        OutputDir: outputDir,
        AudioConfig: audio.Config{
            Format:           "flac",
            PreserveMetadata: true,
            AutoDetectFormat: true,
        },
    })

    // ===== ACT =====
    result, err := batchProcessor.ProcessAll(ctx)

    // ===== ASSERT =====

    // 1. All conversions succeeded
    require.NoError(t, err, "Batch processing should succeed")
    assert.Equal(t, len(testFiles), result.TotalFiles, "Should find all files")
    assert.Equal(t, len(testFiles), result.Successful, "All should convert")
    assert.Equal(t, 0, result.Failed, "None should fail")

    // 2. All output files exist and are valid FLAC
    for _, tf := range testFiles {
        outputFile := filepath.Join(outputDir, 
            changeExtension(tf.filename, "flac"))

        assert.FileExists(t, outputFile, 
            "Output for %s should exist", tf.filename)

        isValid := validateFLACFile(t, outputFile)
        assert.True(t, isValid, 
            "Output for %s should be valid FLAC", tf.filename)
    }

    // 3. Quality preservation appropriate for source
    for _, tf := range testFiles {
        outputFile := filepath.Join(outputDir, 
            changeExtension(tf.filename, "flac"))

        codec := getAudioCodec(t, outputFile)
        assert.Equal(t, "flac", codec, 
            "Output codec should be FLAC for %s", tf.filename)

        // Verify lossless sources maintain higher quality
        if tf.isLossless {
            compressionLevel := getFLACCompressionLevel(t, outputFile)
            assert.GreaterOrEqual(t, compressionLevel, 7,
                "Lossless source should use high compression for %s", tf.filename)
        }
    }

    // 4. Metadata preserved
    for _, tf := range testFiles {
        outputFile := filepath.Join(outputDir, 
            changeExtension(tf.filename, "flac"))

        metadata := extractMetadata(t, outputFile)
        assert.NotEmpty(t, metadata, 
            "Metadata should exist for %s", tf.filename)
    }

    // 5. Summary report correct
    assert.Contains(t, result.Summary, "6 of 6 successful")
}

// TestStory4_FormatSupport_AutoDetection tests format detection
// ACCEPTANCE CRITERIA: Scenario 2
func TestStory4_FormatSupport_AutoDetection(t *testing.T) {
    ctx := context.Background()

    tempDir := t.TempDir()
    inputDir := filepath.Join(tempDir, "input")
    outputDir := filepath.Join(tempDir, "output")

    require.NoError(t, os.MkdirAll(inputDir, 0755))
    require.NoError(t, os.MkdirAll(outputDir, 0755))

    disguisedMP3 := filepath.Join(inputDir, "disguised.txt")
    require.NoError(t, copyTestFile("testdata/audio/sample.mp3", disguisedMP3))

    noExtension := filepath.Join(inputDir, "no_extension")
    require.NoError(t, copyTestFile("testdata/audio/sample.wav", noExtension))

    detector := audio.NewFormatDetector()

    format1, err := detector.DetectFormat(disguisedMP3)
    require.NoError(t, err)
    format2, err := detector.DetectFormat(noExtension)
    require.NoError(t, err)

    assert.Equal(t, "mp3", format1, "Should detect MP3 despite .txt extension")
    assert.Equal(t, "wav", format2, "Should detect WAV despite no extension")

    converter := audio.NewConverter(audio.Config{
        InputDir:         inputDir,
        OutputDir:        outputDir,
        Format:           "flac",
        AutoDetectFormat: true,
    })

    result1, err := converter.ConvertFile(ctx, disguisedMP3)
    require.NoError(t, err)
    assert.True(t, result1.Success)

    result2, err := converter.ConvertFile(ctx, noExtension)
    require.NoError(t, err)
    assert.True(t, result2.Success)

    output1 := filepath.Join(outputDir, "disguised.flac")
    output2 := filepath.Join(outputDir, "no_extension.flac")

    assert.FileExists(t, output1)
    assert.FileExists(t, output2)
    assert.True(t, validateFLACFile(t, output1))
    assert.True(t, validateFLACFile(t, output2))
}

// TestStory4_FormatSupport_UnsupportedFormats tests error handling
// ACCEPTANCE CRITERIA: Scenario 3
func TestStory4_FormatSupport_UnsupportedFormats(t *testing.T) {
    ctx := context.Background()

    tempDir := t.TempDir()
    inputDir := filepath.Join(tempDir, "input")
    outputDir := filepath.Join(tempDir, "output")

    require.NoError(t, os.MkdirAll(inputDir, 0755))
    require.NoError(t, os.MkdirAll(outputDir, 0755))

    files := map[string]string{
        "song.mp3":   "testdata/audio/sample.mp3",
        "video.mp4":  "testdata/video/sample.mp4",
        "audio.wma":  "testdata/audio/sample.wma",
        "song.flac":  "testdata/audio/sample.flac",
        "audio.ape":  "testdata/audio/sample.ape",
    }

    for filename, source := range files {
        dest := filepath.Join(inputDir, filename)
        if fileExists(source) {
            require.NoError(t, copyTestFile(source, dest))
        } else {
            require.NoError(t, os.WriteFile(dest, []byte("dummy"), 0644))
        }
    }

    batchProcessor := processor.NewBatchProcessor(processor.Config{
        InputDir:  inputDir,
        OutputDir: outputDir,
        AudioConfig: audio.Config{
            Format:           "flac",
            AutoDetectFormat: true,
        },
    })

    result, err := batchProcessor.ProcessAll(ctx)

    require.NoError(t, err, "Should complete with partial failures")
    assert.Equal(t, 5, result.TotalFiles)
    assert.Equal(t, 1, result.Successful)
    assert.Equal(t, 3, result.Failed)
    assert.Equal(t, 1, result.Skipped)

    errorMap := result.ErrorsByFile

    assert.Contains(t, errorMap["video.mp4"], "Unsupported format",
        "MP4 should have unsupported format error")
    assert.Contains(t, errorMap["audio.wma"], "Unsupported format",
        "WMA should have unsupported format error")
    assert.Contains(t, errorMap["audio.ape"], "Unsupported format",
        "APE should have unsupported format error")

    assert.Contains(t, result.Summary, "1 successful")
    assert.Contains(t, result.Summary, "3 failed")
    assert.Contains(t, result.Summary, "1 skipped")
}

// TestStory4_FormatSupport_FormatSpecificParameters tests encoding params
// ACCEPTANCE CRITERIA: Scenario 4
func TestStory4_FormatSupport_FormatSpecificParameters(t *testing.T) {
    if testing.Short() {
        t.Skip("Skipping format-specific test in short mode")
    }

    ctx := context.Background()

    tempDir := t.TempDir()
    inputDir := filepath.Join(tempDir, "input")
    outputDir := filepath.Join(tempDir, "output")

    require.NoError(t, os.MkdirAll(inputDir, 0755))
    require.NoError(t, os.MkdirAll(outputDir, 0755))

    testCases := []struct {
        filename   string
        sourceFile string
        sampleRate int
        isLossless bool
    }{
        {"opus_48k.opus", "testdata/audio/sample-48k.opus", 48000, false},
        {"wav_96k.wav", "testdata/audio/sample-96k.wav", 96000, true},
        {"mp3_44k.mp3", "testdata/audio/sample.mp3", 44100, false},
    }

    for _, tc := range testCases {
        inputFile := filepath.Join(inputDir, tc.filename)
        require.NoError(t, copyTestFile(tc.sourceFile, inputFile))
    }

    converter := audio.NewConverter(audio.Config{
        InputDir:  inputDir,
        OutputDir: outputDir,
        Format:    "flac",
        AdaptiveCompression: true,
    })

    for _, tc := range testCases {
        inputFile := filepath.Join(inputDir, tc.filename)
        result, err := converter.ConvertFile(ctx, inputFile)
        require.NoError(t, err, "Conversion should succeed for %s", tc.filename)
        outputFile := result.OutputPath
        actualSampleRate := getSampleRate(t, outputFile)
        assert.Equal(t, tc.sampleRate, actualSampleRate,
            "Sample rate should be preserved for %s", tc.filename)
        compressionLevel := getFLACCompressionLevel(t, outputFile)
        if tc.isLossless {
            assert.GreaterOrEqual(t, compressionLevel, 7,
                "Lossless source should use high compression for %s", tc.filename)
        } else {
            assert.LessOrEqual(t, compressionLevel, 6,
                "Lossy source should use balanced compression for %s", tc.filename)
        }
    }
}

// TestStory4_FormatSupport_FormatValidation tests pre-conversion validation
// ACCEPTANCE CRITERIA: Scenario 5
func TestStory4_FormatSupport_FormatValidation(t *testing.T) {
    tempDir := t.TempDir()

    brokenMP3 := filepath.Join(tempDir, "broken.mp3")
    require.NoError(t, os.WriteFile(brokenMP3, []byte("NOT MP3 DATA"), 0644))

    truncatedWAV := filepath.Join(tempDir, "truncated.wav")
    wavHeader := []byte{
        0x52, 0x49, 0x46, 0x46,
        0x00, 0x00, 0x00, 0x00,
    }
    require.NoError(t, os.WriteFile(truncatedWAV, wavHeader, 0644))

    validOGG := filepath.Join(tempDir, "valid.ogg")
    require.NoError(t, copyTestFile("testdata/audio/sample.ogg", validOGG))

    validator := audio.NewFormatValidator()

    err := validator.ValidateFile(brokenMP3)
    assert.Error(t, err, "Broken MP3 should fail validation")
    assert.Contains(t, err.Error(), "invalid", "Error should mention invalidity")

    err = validator.ValidateFile(truncatedWAV)
    assert.Error(t, err, "Truncated WAV should fail validation")
    assert.Contains(t, err.Error(), "incomplete", "Error should mention incompleteness")

    err = validator.ValidateFile(validOGG)
    assert.NoError(t, err, "Valid OGG should pass validation")
}

// ... Additional tests for other scenarios would follow here ...

// ===== HELPER FUNCTIONS =====

func changeExtension(filename, newExt string) string {
    base := filepath.Base(filename)
    ext := filepath.Ext(base)
    nameWithoutExt := base[:len(base)-len(ext)]
    return nameWithoutExt + "." + newExt
}

func validateFLACFile(t *testing.T, path string) bool {
    t.Helper()
    // Check FLAC magic number "fLaC"
    file, err := os.Open(path)
    if err != nil {
        return false
    }
    defer file.Close()

    magic := make([]byte, 4)
    if _, err := file.Read(magic); err != nil {
        return false
    }

    return string(magic) == "fLaC"
}

func getAudioCodec(t *testing.T, path string) string {
    t.Helper()
    // PLACEHOLDER - implement with exec.Command or ffprobe
    return "flac" // TODO: Real implementation
}

func getFLACCompressionLevel(t *testing.T, path string) int {
    t.Helper()
    // PLACEHOLDER - implement with FLAC library or ffprobe
    return 5 // TODO: Real implementation
}

func extractMetadata(t *testing.T, path string) map[string]string {
    t.Helper()
    // PLACEHOLDER - implement with ffprobe
    return map[string]string{"ARTIST": "Test"} // TODO: Real implementation
}

func copyTestFile(src, dst string) error {
    data, err := os.ReadFile(src)
    if err != nil {
        return err
    }
    return os.WriteFile(dst, data, 0644)
}
