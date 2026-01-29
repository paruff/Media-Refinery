package state_test

import (
    "os"
    "path/filepath"
    "testing"

    "github.com/paruff/Media-Refinery/pkg/state"
    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/require"
)

// TestStateManager_CalculateChecksum tests checksum calculation
func TestStateManager_CalculateChecksum(t *testing.T) {
























































}    assert.False(t, matches, "Should not match after modification")    require.NoError(t, err)    matches, err = manager.VerifyChecksum(testFile)    require.NoError(t, os.WriteFile(testFile, []byte("data2"), 0644))    assert.True(t, matches, "Should match after storing")    require.NoError(t, err)    matches, err := manager.VerifyChecksum(testFile)    require.NoError(t, manager.StoreChecksum(testFile, checksum))    require.NoError(t, err)    checksum, err := manager.CalculateChecksum(testFile)    require.NoError(t, os.WriteFile(testFile, []byte("data1"), 0644))    testFile := filepath.Join(tempDir, "test.flac")    manager := state.NewManager(tempDir)    tempDir := t.TempDir()func TestStateManager_VerifyChecksum(t *testing.T) {// TestStateManager_VerifyChecksum tests verification logic}    assert.Equal(t, testChecksum, retrieved)    require.NoError(t, err)    retrieved, err := manager.GetChecksum(testFile)    require.NoError(t, err)    err := manager.StoreChecksum(testFile, testChecksum)    testChecksum := "abc123def456"    testFile := "/path/to/output.flac"    manager := state.NewManager(tempDir)    tempDir := t.TempDir()func TestStateManager_StoreAndRetrieve(t *testing.T) {// TestStateManager_StoreAndRetrieve tests storage}    }        })            assert.Len(t, checksum, tt.wantLen)            require.NoError(t, err)            }                return                assert.Error(t, err)            if tt.wantErr {            checksum, err := manager.CalculateChecksum(testFile)            manager := state.NewManager(tempDir)            require.NoError(t, os.WriteFile(testFile, tt.content, 0644))            testFile := filepath.Join(tempDir, "test.txt")            tempDir := t.TempDir()        t.Run(tt.name, func(t *testing.T) {    for _, tt := range tests {    }        {"Empty file", []byte{}, 64, false},        {"Valid file", []byte("test data"), 64, false},    }{        wantErr  bool        wantLen  int        content  []byte        name     string    tests := []struct {