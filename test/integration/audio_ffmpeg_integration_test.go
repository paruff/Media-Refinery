package integration_test

import (
	"os"
	"os/exec"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestFFmpegIntegration_Available verifies FFmpeg is installed
func TestFFmpegIntegration_Available(t *testing.T) {
	// Check if ffmpeg is available
	_, err := exec.LookPath("ffmpeg")
	require.NoError(t, err, "FFmpeg must be installed for integration tests")

	// Check if ffprobe is available
	_, err = exec.LookPath("ffprobe")
	require.NoError(t, err, "ffprobe must be installed for integration tests")
}

// TestFFmpegIntegration_ConvertMP3toFLAC tests real FFmpeg conversion
func TestFFmpegIntegration_ConvertMP3toFLAC(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	// Setup
	tempDir := t.TempDir()
	inputFile := filepath.Join(tempDir, "input.mp3")
	outputFile := filepath.Join(tempDir, "output.flac")

	// Copy test file
	require.NoError(t, copyTestFile("testdata/audio/sample.mp3", inputFile))

	// Convert with metadata preservation
	cmd := exec.Command("ffmpeg", "-y", "-i", inputFile, "-map_metadata", "0", "-c:a", "flac", outputFile)
	out, err := cmd.CombinedOutput()
	require.NoErrorf(t, err, "FFmpeg conversion failed: %s", string(out))

	// Verify output exists and is non-empty
	info, err := os.Stat(outputFile)
	require.NoError(t, err)
	assert.Greater(t, info.Size(), int64(0), "Output file should not be empty")
}

// copyTestFile copies a file from testdata to a destination
func copyTestFile(src, dst string) error {
	data, err := os.ReadFile(src)
	if err != nil {
		return err
	}
	return os.WriteFile(dst, data, 0644)
}
