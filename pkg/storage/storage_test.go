package storage

import (
	"io/ioutil"
	"os"
	"path/filepath"
	"testing"
)

func TestCreateDirAndCopy(t *testing.T) {
	tmp := t.TempDir()

	stor := NewStorage(tmp, false)

	// Create dir
	dirPath := filepath.Join(tmp, "a", "b", "c")
	if err := stor.CreateDir(dirPath); err != nil {
		t.Fatalf("CreateDir failed: %v", err)
	}
	if _, err := os.Stat(dirPath); err != nil {
		t.Fatalf("expected dir to exist: %v", err)
	}

	// Create source file
	src := filepath.Join(tmp, "src.txt")
	content := []byte("hello world")
	if err := ioutil.WriteFile(src, content, 0644); err != nil {
		t.Fatalf("failed to write src: %v", err)
	}

	dest := filepath.Join(tmp, "a", "b", "copied.txt")
	if err := stor.Copy(src, dest); err != nil {
		t.Fatalf("Copy failed: %v", err)
	}

	data, err := ioutil.ReadFile(dest)
	if err != nil {
		t.Fatalf("failed to read dest: %v", err)
	}
	if string(data) != string(content) {
		t.Fatalf("copied content mismatch: got %q want %q", string(data), string(content))
	}
}

func TestDryRunRecordsOperations(t *testing.T) {
	tmp := t.TempDir()
	stor := NewStorage(tmp, true)

	// Dry-run create dir
	dirPath := filepath.Join(tmp, "dr")
	if err := stor.CreateDir(dirPath); err != nil {
		t.Fatalf("CreateDir (dry) failed: %v", err)
	}

	// Dry-run copy
	src := filepath.Join(tmp, "src2.txt")
	if err := ioutil.WriteFile(src, []byte("x"), 0644); err != nil {
		t.Fatalf("write src2 failed: %v", err)
	}
	dest := filepath.Join(tmp, "dest2.txt")
	if err := stor.Copy(src, dest); err != nil {
		t.Fatalf("Copy (dry) failed: %v", err)
	}

	ops := stor.GetOperations()
	if len(ops) != 2 {
		t.Fatalf("expected 2 operations recorded, got %d", len(ops))
	}
}
