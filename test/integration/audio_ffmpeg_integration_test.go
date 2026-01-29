package integration
package integration_test

import (
    "context"
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

    // Run FFmpeg command
    cmd := exec.Command("ffmpeg",
        "-i", inputFile,





























































}    return os.WriteFile(dst, data, 0644)    }        return err    if err != nil {    data, err := os.ReadFile(src)func copyTestFile(src, dst string) error {// Helper for copying test files (should match acceptance test helper)}    assert.Contains(t, string(output), "Test Artist")    require.NoError(t, err)    output, err := cmd.Output()    )        outputFile,        "-of", "default=noprint_wrappers=1:nokey=1",        "-show_entries", "format_tags=artist,title,album",        "-v", "error",    cmd = exec.Command("ffprobe",    // Verify metadata in output    require.NoError(t, cmd.Run())    )        outputFile,        "-map_metadata", "0", // Preserve metadata        "-c:a", "flac",        "-i", inputFile,    cmd := exec.Command("ffmpeg",    // Convert with metadata preservation    require.NoError(t, copyTestFile("testdata/audio/sample-with-metadata.mp3", inputFile))    // Copy test file with metadata    outputFile := filepath.Join(tempDir, "output.flac")    inputFile := filepath.Join(tempDir, "input.mp3")    tempDir := t.TempDir()    }        t.Skip("Skipping integration test in short mode")    if testing.Short() {func TestFFmpegIntegration_PreserveMetadata(t *testing.T) {// TestFFmpegIntegration_PreserveMetadata tests metadata preservation}    assert.Greater(t, info.Size(), int64(0), "Output file should not be empty")    require.NoError(t, err)    info, err := os.Stat(outputFile)    // Verify output is FLAC    assert.FileExists(t, outputFile)    // Verify output exists    require.NoError(t, err, "FFmpeg conversion should succeed: %s", string(output))    output, err := cmd.CombinedOutput()    )        outputFile,        "-compression_level", "5",        "-c:a", "flac",