
package state

import (
    "crypto/sha256"
    "encoding/hex"
    "encoding/json"
    "fmt"
    "io"
    "os"
    "path/filepath"
    "sync"
    "time"
)

// FileState represents the state of a processed file
type FileState struct {
    ProcessedAt int64  `json:"processed_at"`
    Checksum    string `json:"checksum"`
    OutputPath  string `json:"output_path"`
    InputPath   string `json:"input_path,omitempty"`
}

// NewManager creates a new state manager
func NewManager(stateDir string) *Manager {
    return &Manager{
        stateDir: stateDir,
        cache:    make(map[string]*FileState),
    }
}

// CalculateChecksum computes SHA256 checksum of a file
func (m *Manager) CalculateChecksum(path string) (string, error) {
    file, err := os.Open(path)
    if err != nil {
        return "", fmt.Errorf("open file: %w", err)
    }
    defer file.Close()

    hash := sha256.New()
    if _, err := io.Copy(hash, file); err != nil {
        return "", fmt.Errorf("compute hash: %w", err)
    }
    return hex.EncodeToString(hash.Sum(nil)), nil
}

// StoreChecksum stores a file's checksum
func (m *Manager) StoreChecksum(outputPath, checksum string) error {
    m.mu.Lock()
    defer m.mu.Unlock()

    state := &FileState{
        OutputPath:  outputPath,
        Checksum:    checksum,
        ProcessedAt: time.Now().Unix(),
    }
    m.cache[outputPath] = state

    stateFile := m.getStateFile(outputPath)
    if err := os.MkdirAll(filepath.Dir(stateFile), 0755); err != nil {
        return fmt.Errorf("create state dir: %w", err)
    }
    data, err := json.Marshal(state)
    if err != nil {
        return fmt.Errorf("marshal state: %w", err)
    }
    if err := os.WriteFile(stateFile, data, 0644); err != nil {
        return fmt.Errorf("write state file: %w", err)
    }
    return nil
}

// GetChecksum retrieves a stored checksum
func (m *Manager) GetChecksum(outputPath string) (string, error) {
    m.mu.RLock()
    if state, ok := m.cache[outputPath]; ok {
        m.mu.RUnlock()
        return state.Checksum, nil
    }
    m.mu.RUnlock()

    state, err := m.loadState(outputPath)
    if err != nil {
        return "", err
    }
    m.mu.Lock()
    m.cache[outputPath] = state
    m.mu.Unlock()
    return state.Checksum, nil
}

// VerifyChecksum verifies a file's checksum matches stored value
func (m *Manager) VerifyChecksum(outputPath string) (bool, error) {
    storedChecksum, err := m.GetChecksum(outputPath)
    if err != nil {
        return false, err
    }
    currentChecksum, err := m.CalculateChecksum(outputPath)
    if err != nil {
        return false, err
    }
    return storedChecksum == currentChecksum, nil
}

// IsProcessed checks if a file has been processed
func (m *Manager) IsProcessed(outputPath string) bool {
    _, err := m.GetChecksum(outputPath)
    return err == nil
}

// getStateFile returns the state file path for an output file
func (m *Manager) getStateFile(outputPath string) string {
    hash := sha256.Sum256([]byte(outputPath))
    filename := hex.EncodeToString(hash[:]) + ".json"
    return filepath.Join(m.stateDir, filename)
}

// loadState loads state from disk
func (m *Manager) loadState(outputPath string) (*FileState, error) {
    stateFile := m.getStateFile(outputPath)
    data, err := os.ReadFile(stateFile)
    if err != nil {
        return nil, fmt.Errorf("read state file: %w", err)
    }
    var state FileState
    if err := json.Unmarshal(data, &state); err != nil {
        return nil, fmt.Errorf("unmarshal state: %w", err)
    }
    return &state, nil
}

// Manager manages processing state and checksums
type Manager struct {
    stateDir string
    mu       sync.RWMutex
    cache    map[string]*FileState
}

























































































































}    return &state, nil    }        return nil, fmt.Errorf("unmarshal state: %w", err)    if err := json.Unmarshal(data, &state); err != nil {    var state FileState    }        return nil, fmt.Errorf("read state file: %w", err)    if err != nil {    data, err := os.ReadFile(stateFile)    stateFile := m.getStateFile(outputPath)func (m *Manager) loadState(outputPath string) (*FileState, error) {// loadState loads state from disk}    return filepath.Join(m.stateDir, filename)    filename := hex.EncodeToString(hash[:]) + ".json"    hash := sha256.Sum256([]byte(outputPath))func (m *Manager) getStateFile(outputPath string) string {// getStateFile returns the state file path for an output file}    return err == nil    _, err := m.GetChecksum(outputPath)func (m *Manager) IsProcessed(outputPath string) bool {// IsProcessed checks if a file has been processed}    return storedChecksum == currentChecksum, nil    }        return false, err    if err != nil {    currentChecksum, err := m.CalculateChecksum(outputPath)    }        return false, err    if err != nil {    storedChecksum, err := m.GetChecksum(outputPath)func (m *Manager) VerifyChecksum(outputPath string) (bool, error) {// VerifyChecksum verifies a file's checksum matches stored value}    return state.Checksum, nil    m.mu.Unlock()    m.cache[outputPath] = state    m.mu.Lock()    }        return "", err    if err != nil {    state, err := m.loadState(outputPath)    m.mu.RUnlock()    }        return state.Checksum, nil        m.mu.RUnlock()    if state, ok := m.cache[outputPath]; ok {    m.mu.RLock()func (m *Manager) GetChecksum(outputPath string) (string, error) {// GetChecksum retrieves a stored checksum}    return nil    }        return fmt.Errorf("write state file: %w", err)    if err := os.WriteFile(stateFile, data, 0644); err != nil {    }        return fmt.Errorf("marshal state: %w", err)    if err != nil {    data, err := json.Marshal(state)    }        return fmt.Errorf("create state dir: %w", err)    if err := os.MkdirAll(filepath.Dir(stateFile), 0755); err != nil {    stateFile := m.getStateFile(outputPath)    m.cache[outputPath] = state    }        ProcessedAt: time.Now().Unix(),        Checksum:    checksum,        OutputPath:  outputPath,    state := &FileState{    defer m.mu.Unlock()    m.mu.Lock()func (m *Manager) StoreChecksum(outputPath, checksum string) error {// StoreChecksum stores a file's checksum}    return hex.EncodeToString(hash.Sum(nil)), nil    }        return "", fmt.Errorf("compute hash: %w", err)    if _, err := io.Copy(hash, file); err != nil {    hash := sha256.New()    defer file.Close()    }        return "", fmt.Errorf("open file: %w", err)    if err != nil {    file, err := os.Open(path)func (m *Manager) CalculateChecksum(path string) (string, error) {// CalculateChecksum computes SHA256 checksum of a file}    }        cache:    make(map[string]*FileState),        stateDir: stateDir,    return &Manager{func NewManager(stateDir string) *Manager {// NewManager creates a new state manager}    cache    map[string]*FileState    mu       sync.RWMutex    stateDir stringtype Manager struct {//// Manager manages processing state and checksums}    ProcessedAt int64  `json:"processed_at"`    Checksum    string `json:"checksum"`    OutputPath  string `json:"output_path"`    InputPath   string `json:"input_path,omitempty"`type FileState struct {//// FileState represents the state of a processed file