package validator

import (
    "io/ioutil"
    "testing"
)

func TestComputeChecksum_Success(t *testing.T) {
    tmp := t.TempDir()
    file := tmp + "/f.txt"
    data := []byte("checksum-test")
    if err := ioutil.WriteFile(file, data, 0644); err != nil {
        t.Fatalf("write failed: %v", err)
    }

    v := NewValidator([]string{"mp3"}, []string{"mp4"})
    ch, err := v.ComputeChecksum(file)
    if err != nil {
        t.Fatalf("ComputeChecksum failed: %v", err)
    }
    if ch == "" {
        t.Fatalf("empty checksum")
    }
}

func TestComputeChecksum_NonExistent(t *testing.T) {
    v := NewValidator([]string{"mp3"}, []string{"mp4"})
    _, err := v.ComputeChecksum("/path/does/not/exist")
    if err == nil {
        t.Fatalf("expected error for missing file")
    }
}

func TestProbeMediaFile_NonExistent(t *testing.T) {
    v := NewValidator([]string{"mp3"}, []string{"mp4"})
    err := v.ProbeMediaFile("nonexistent.file")
    if err == nil {
        t.Fatalf("expected ffprobe error for nonexistent file")
    }
}
