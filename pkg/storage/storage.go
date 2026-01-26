package storage

import (
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sync"
)

// Storage provides safe file operations with transaction-like behavior
type Storage struct {
	workDir     string
	dryRun      bool
	operations  []Operation
	mu          sync.Mutex
}

// Operation represents a file operation
type Operation struct {
	Type      OperationType
	Source    string
	Dest      string
	Completed bool
	BackupPath string
}

// OperationType represents the type of operation
type OperationType int

const (
	CopyOp OperationType = iota
	MoveOp
	DeleteOp
	CreateDirOp
)

// NewStorage creates a new storage manager
func NewStorage(workDir string, dryRun bool) *Storage {
	return &Storage{
		workDir:    workDir,
		dryRun:     dryRun,
		operations: make([]Operation, 0),
	}
}

// Copy copies a file
func (s *Storage) Copy(src, dest string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	
	op := Operation{
		Type:   CopyOp,
		Source: src,
		Dest:   dest,
	}
	
	if s.dryRun {
		s.operations = append(s.operations, op)
		return nil
	}
	
	// Ensure destination directory exists
	destDir := filepath.Dir(dest)
	if err := os.MkdirAll(destDir, 0755); err != nil {
		return fmt.Errorf("failed to create destination directory: %w", err)
	}
	
	// Check if destination exists and back it up
	if _, err := os.Stat(dest); err == nil {
		backupPath := dest + ".backup"
		if err := s.backup(dest, backupPath); err != nil {
			return fmt.Errorf("failed to backup existing file: %w", err)
		}
		op.BackupPath = backupPath
	}
	
	// Copy file
	if err := copyFile(src, dest); err != nil {
		// Restore backup if copy failed
		if op.BackupPath != "" {
			_ = s.restore(op.BackupPath, dest)
		}
		return fmt.Errorf("failed to copy file: %w", err)
	}
	
	op.Completed = true
	s.operations = append(s.operations, op)
	
	return nil
}

// Move moves a file
func (s *Storage) Move(src, dest string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	
	op := Operation{
		Type:   MoveOp,
		Source: src,
		Dest:   dest,
	}
	
	if s.dryRun {
		s.operations = append(s.operations, op)
		return nil
	}
	
	// Ensure destination directory exists
	destDir := filepath.Dir(dest)
	if err := os.MkdirAll(destDir, 0755); err != nil {
		return fmt.Errorf("failed to create destination directory: %w", err)
	}
	
	// Try rename first (faster if on same filesystem)
	if err := os.Rename(src, dest); err != nil {
		// If rename fails, try copy and delete
		if err := copyFile(src, dest); err != nil {
			return fmt.Errorf("failed to copy file: %w", err)
		}
		if err := os.Remove(src); err != nil {
			// Try to clean up destination on failure
			_ = os.Remove(dest)
			return fmt.Errorf("failed to remove source file: %w", err)
		}
	}
	
	op.Completed = true
	s.operations = append(s.operations, op)
	
	return nil
}

// CreateDir creates a directory
func (s *Storage) CreateDir(path string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	
	op := Operation{
		Type: CreateDirOp,
		Dest: path,
	}
	
	if s.dryRun {
		s.operations = append(s.operations, op)
		return nil
	}
	
	if err := os.MkdirAll(path, 0755); err != nil {
		return fmt.Errorf("failed to create directory: %w", err)
	}
	
	op.Completed = true
	s.operations = append(s.operations, op)
	
	return nil
}

// GetOperations returns all recorded operations
func (s *Storage) GetOperations() []Operation {
	s.mu.Lock()
	defer s.mu.Unlock()
	
	result := make([]Operation, len(s.operations))
	copy(result, s.operations)
	return result
}

// Rollback attempts to rollback completed operations
func (s *Storage) Rollback() error {
	s.mu.Lock()
	defer s.mu.Unlock()
	
	var errors []error
	
	// Rollback in reverse order
	for i := len(s.operations) - 1; i >= 0; i-- {
		op := s.operations[i]
		if !op.Completed {
			continue
		}
		
		switch op.Type {
		case CopyOp:
			if err := os.Remove(op.Dest); err != nil && !os.IsNotExist(err) {
				errors = append(errors, fmt.Errorf("failed to remove %s: %w", op.Dest, err))
			}
			if op.BackupPath != "" {
				if err := s.restore(op.BackupPath, op.Dest); err != nil {
					errors = append(errors, fmt.Errorf("failed to restore backup: %w", err))
				}
			}
		case MoveOp:
			// Try to move back
			if err := os.Rename(op.Dest, op.Source); err != nil {
				errors = append(errors, fmt.Errorf("failed to move back %s: %w", op.Dest, err))
			}
		}
	}
	
	if len(errors) > 0 {
		return fmt.Errorf("rollback completed with %d errors", len(errors))
	}
	
	return nil
}

// backup creates a backup of a file
func (s *Storage) backup(src, dest string) error {
	return copyFile(src, dest)
}

// restore restores a file from backup
func (s *Storage) restore(backup, dest string) error {
	if err := copyFile(backup, dest); err != nil {
		return err
	}
	return os.Remove(backup)
}

// copyFile copies a file from src to dest
func copyFile(src, dest string) error {
	srcFile, err := os.Open(src)
	if err != nil {
		return err
	}
	defer srcFile.Close()
	
	destFile, err := os.Create(dest)
	if err != nil {
		return err
	}
	defer destFile.Close()
	
	if _, err := io.Copy(destFile, srcFile); err != nil {
		return err
	}
	
	// Sync to ensure data is written
	if err := destFile.Sync(); err != nil {
		return err
	}
	
	// Copy permissions
	srcInfo, err := os.Stat(src)
	if err != nil {
		return err
	}
	
	return os.Chmod(dest, srcInfo.Mode())
}

// IsDryRun returns whether storage is in dry-run mode
func (s *Storage) IsDryRun() bool {
	return s.dryRun
}
