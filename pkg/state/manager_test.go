package state_test

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/paruff/Media-Refinery/pkg/state"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestStateManager_CalculateChecksum(t *testing.T) {
	tests := []struct {
		name    string
		content []byte
		wantLen int
		wantErr bool
	}{
		{"Valid file", []byte("test data"), 64, false},
		{"Empty file", []byte{}, 64, false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			tempDir := t.TempDir()
			testFile := filepath.Join(tempDir, "test.txt")
			require.NoError(t, os.WriteFile(testFile, tt.content, 0644))
			manager := state.NewManager(tempDir)
			checksum, err := manager.CalculateChecksum(testFile)
			if tt.wantErr {
				assert.Error(t, err)
				return
			}
			require.NoError(t, err)
			assert.Len(t, checksum, tt.wantLen)
		})
	}

}

func TestStateManager_StoreAndRetrieve(t *testing.T) {
	tempDir := t.TempDir()
	manager := state.NewManager(tempDir)
	testFile := filepath.Join(tempDir, "test.flac")
	testChecksum := "abc123def456"
	err := manager.StoreChecksum(testFile, testChecksum)
	require.NoError(t, err)
	retrieved, err := manager.GetChecksum(testFile)
	require.NoError(t, err)
	assert.Equal(t, testChecksum, retrieved)
}

func TestStateManager_VerifyChecksum(t *testing.T) {
	tempDir := t.TempDir()
	manager := state.NewManager(tempDir)
	testFile := filepath.Join(tempDir, "test.flac")
	require.NoError(t, os.WriteFile(testFile, []byte("data1"), 0644))
	checksum, err := manager.CalculateChecksum(testFile)
	require.NoError(t, err)
	require.NoError(t, manager.StoreChecksum(testFile, checksum))
	matches, err := manager.VerifyChecksum(testFile)
	require.NoError(t, err)
	assert.True(t, matches, "Should match after storing")
	require.NoError(t, os.WriteFile(testFile, []byte("data2"), 0644))
	matches, err = manager.VerifyChecksum(testFile)
	require.NoError(t, err)
	assert.False(t, matches, "Should not match after modification")
}
