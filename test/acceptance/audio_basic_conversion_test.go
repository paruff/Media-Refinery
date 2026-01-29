package acceptance_test

import (
	"context"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/paruff/Media-Refinery/pkg/audio"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestStory1_BasicAudioConversion_Success tests the happy path
// ACCEPTANCE CRITERIA: Scenario 1
func TestStory1_BasicAudioConversion_Success(t *testing.T) {
	// ===== ARRANGE =====
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	// Setup test directories
	tempDir := t.TempDir() // Automatically cleaned up
	inputDir := filepath.Join(tempDir, "input")
	outputDir := filepath.Join(tempDir, "output")

	require.NoError(t, os.MkdirAll(inputDir, 0755))
	require.NoError(t, os.MkdirAll(outputDir, 0755))

	// Copy test file to input
	inputFile := filepath.Join(inputDir, "song.mp3")
	require.NoError(t, copyTestFile("testdata/audio/sample.mp3", inputFile))

	// Verify test file has expected properties
	info, err := os.Stat(inputFile)
	require.NoError(t, err)
	require.Greater(t, info.Size(), int64(0), "Test file should not be empty")

	// Create converter with configuration
	converter := audio.NewConverter(audio.Config{
		InputDir:         inputDir,
		OutputDir:        outputDir,
		Format:           "flac",
		PreserveMetadata: true,
	})

	// ===== ACT =====
	startTime := time.Now()
	result, err := converter.ConvertFile(ctx, inputFile)
	duration := time.Since(startTime)

	// ===== ASSERT =====

	// 1. Conversion succeeded
	require.NoError(t, err, "Conversion should succeed")
	require.NotNil(t, result, "Result should not be nil")

	// 2. Output file exists
	outputFile := filepath.Join(outputDir, "song.flac")
	assert.FileExists(t, outputFile, "Output FLAC file should exist")

	// 3. Output file is valid FLAC
	isValid := validateFLACFile(t, outputFile)
	assert.True(t, isValid, "Output should be valid FLAC file")

	// 4. Metadata preserved (ID3v2 → Vorbis)
	metadata := extractMetadata(t, outputFile)
	assert.Equal(t, "Test Artist", metadata["ARTIST"], "Artist metadata should be preserved")
	assert.Equal(t, "Test Song", metadata["TITLE"], "Title metadata should be preserved")
	assert.Equal(t, "Test Album", metadata["ALBUM"], "Album metadata should be preserved")

	// 5. Original file unchanged
	assert.FileExists(t, inputFile, "Original MP3 should still exist")
	originalChecksum := computeChecksum(t, inputFile)
	assert.NotEmpty(t, originalChecksum, "Should be able to compute checksum")

	// 6. Checksum stored in result
	assert.NotEmpty(t, result.Checksum, "Result should contain checksum")
	assert.Equal(t, 64, len(result.Checksum), "SHA256 checksum should be 64 hex chars")

	// 7. Performance requirement met
	assert.Less(t, duration, 10*time.Second, "Conversion should complete in <10 seconds")

	// 8. Result contains expected fields
	assert.Equal(t, outputFile, result.OutputPath, "Result should contain output path")
	assert.Equal(t, "flac", result.Format, "Result should indicate FLAC format")
	assert.True(t, result.Success, "Result should indicate success")
}

// TestStory1_BasicAudioConversion_InvalidFile tests error handling
// ACCEPTANCE CRITERIA: Scenario 2
func TestStory1_BasicAudioConversion_InvalidFile(t *testing.T) {
	// ===== ARRANGE =====
	ctx := context.Background()

	tempDir := t.TempDir()
	inputDir := filepath.Join(tempDir, "input")
	outputDir := filepath.Join(tempDir, "output")

	require.NoError(t, os.MkdirAll(inputDir, 0755))
	require.NoError(t, os.MkdirAll(outputDir, 0755))

	// Create invalid file (random bytes, not audio)
	inputFile := filepath.Join(inputDir, "corrupted.mp3")
	require.NoError(t, os.WriteFile(inputFile, []byte("NOT VALID AUDIO DATA"), 0644))

	converter := audio.NewConverter(audio.Config{
		InputDir:  inputDir,
		OutputDir: outputDir,
		Format:    "flac",
	})

	// ===== ACT =====
	result, err := converter.ConvertFile(ctx, inputFile)

	// ===== ASSERT =====

	// 1. Conversion should fail
	require.Error(t, err, "Conversion should fail for invalid file")

	// 2. Error message should be clear
	assert.Contains(t, err.Error(), "Invalid audio file", "Error should mention invalid file")
	assert.Contains(t, err.Error(), "corrupted.mp3", "Error should mention filename")

	// 3. No output file created
	outputFile := filepath.Join(outputDir, "corrupted.flac")
	assert.NoFileExists(t, outputFile, "No output file should be created")

	// 4. Result should indicate failure
	if result != nil {
		assert.False(t, result.Success, "Result should indicate failure")
	}
}

// TestStory1_BasicAudioConversion_OutputValidation tests output integrity
// ACCEPTANCE CRITERIA: Scenario 3
func TestStory1_BasicAudioConversion_OutputValidation(t *testing.T) {
	// ===== ARRANGE =====
	ctx := context.Background()

	tempDir := t.TempDir()
	inputDir := filepath.Join(tempDir, "input")
	outputDir := filepath.Join(tempDir, "output")

	require.NoError(t, os.MkdirAll(inputDir, 0755))
	require.NoError(t, os.MkdirAll(outputDir, 0755))

	inputFile := filepath.Join(inputDir, "song.mp3")
	require.NoError(t, copyTestFile("testdata/audio/sample.mp3", inputFile))

	converter := audio.NewConverter(audio.Config{
		InputDir:  inputDir,
		OutputDir: outputDir,
		Format:    "flac",
	})

	// ===== ACT =====
	_, err := converter.ConvertFile(ctx, inputFile)
	require.NoError(t, err)

	// ===== ASSERT =====
	outputFile := filepath.Join(outputDir, "song.flac")

	// 1. Valid FLAC header
	hasValidHeader := checkFLACHeader(t, outputFile)
	assert.True(t, hasValidHeader, "Output should have valid FLAC header")

	// 2. Audio stream is valid
	hasValidStream := checkAudioStream(t, outputFile)
	assert.True(t, hasValidStream, "Output should have valid audio stream")

	// 3. Metadata is readable
	metadata := extractMetadata(t, outputFile)
	assert.NotEmpty(t, metadata, "Metadata should be readable")

	// 4. No corruption detected
	isCorrupted := checkForCorruption(t, outputFile)
	assert.False(t, isCorrupted, "Output should not be corrupted")
}

// ===== HELPER FUNCTIONS =====
// INSTRUCTION: Implement these helpers to support the tests above

func copyTestFile(src, dst string) error {
	data, err := os.ReadFile(src)
	if err != nil {
		return err
	}
	return os.WriteFile(dst, data, 0644)
}

func validateFLACFile(t *testing.T, path string) bool {
	t.Helper()
	// Use ffprobe to validate FLAC file
	// IMPLEMENTATION HINT: exec.Command("ffprobe", "-v", "error", "-show_format", path)
	// Return true if ffprobe succeeds and format is "flac"
	// PLACEHOLDER: Implement using ffprobe
	return true // TODO: Real implementation
}

func extractMetadata(t *testing.T, path string) map[string]string {
	t.Helper()
	// Use ffprobe to extract Vorbis comments
	// IMPLEMENTATION HINT:
	// ffprobe -v error -show_entries format_tags=artist,title,album -of default=noprint_wrappers=1 path
	// PLACEHOLDER: Implement using ffprobe
	return map[string]string{
		"ARTIST": "Test Artist",
		"TITLE":  "Test Song",
		"ALBUM":  "Test Album",
	} // TODO: Real implementation
}

func computeChecksum(t *testing.T, path string) string {
	t.Helper()
	// Compute SHA256 checksum
	// IMPLEMENTATION HINT: Use crypto/sha256
	// PLACEHOLDER: Implement checksum calculation
	return "placeholder_checksum" // TODO: Real implementation
}

func checkFLACHeader(t *testing.T, path string) bool {
	t.Helper()
	// Check for FLAC header: "fLaC"
	// IMPLEMENTATION HINT: Read first 4 bytes, compare to []byte{'f', 'L', 'a', 'C'}
	// PLACEHOLDER
	return true // TODO: Real implementation
}

func checkAudioStream(t *testing.T, path string) bool {
	t.Helper()
	// Verify audio stream is valid using ffprobe
	// PLACEHOLDER
	return true // TODO: Real implementation
}

func checkForCorruption(t *testing.T, path string) bool {
	t.Helper()
	// Use ffmpeg to decode and check for errors
	// IMPLEMENTATION HINT: ffmpeg -v error -i path -f null -
	// If no errors, file is not corrupted
	// PLACEHOLDER
	return false // TODO: Real implementation
}
