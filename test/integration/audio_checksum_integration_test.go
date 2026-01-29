package integration
package integration_test

import (
    "os"
    "path/filepath"
    "testing"

    "github.com/paruff/media-refinery/pkg/state"
    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/require"
)

// TestChecksumIntegration_CalculateAndStore tests checksum workflow
func TestChecksumIntegration_CalculateAndStore(t *testing.T) {
    if testing.Short() {
        t.Skip("Skipping integration test")
    }
    tempDir := t.TempDir()
    stateDir := filepath.Join(tempDir, "state")
    testFile := filepath.Join(tempDir, "test.flac")
    require.NoError(t, os.MkdirAll(stateDir, 0755))
    require.NoError(t, os.WriteFile(testFile, []byte("test data"), 0644))
    stateManager := state.NewManager(stateDir)
    checksum, err := stateManager.CalculateChecksum(testFile)
    require.NoError(t, err)
    assert.NotEmpty(t, checksum)
    assert.Len(t, checksum, 64)
    err = stateManager.StoreChecksum(testFile, checksum)
    require.NoError(t, err)
    retrieved, err := stateManager.GetChecksum(testFile)
    require.NoError(t, err)
    assert.Equal(t, checksum, retrieved)
}

// TestChecksumIntegration_DetectMismatch tests mismatch detection
func TestChecksumIntegration_DetectMismatch(t *testing.T) {

















}    assert.False(t, matches, "Should detect mismatch")    require.NoError(t, err)    matches, err := stateManager.VerifyChecksum(testFile)    require.NoError(t, os.WriteFile(testFile, []byte("modified"), 0644))    require.NoError(t, stateManager.StoreChecksum(testFile, checksum1))    require.NoError(t, err)    checksum1, err := stateManager.CalculateChecksum(testFile)    stateManager := state.NewManager(stateDir)    require.NoError(t, os.WriteFile(testFile, []byte("original"), 0644))    require.NoError(t, os.MkdirAll(stateDir, 0755))    testFile := filepath.Join(tempDir, "test.flac")    stateDir := filepath.Join(tempDir, "state")    tempDir := t.TempDir()    }        t.Skip("Skipping integration test")    if testing.Short() {