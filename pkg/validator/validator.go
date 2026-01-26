package validator

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
)

// MediaType represents the type of media file
type MediaType int

const (
	UnknownType MediaType = iota
	AudioType
	VideoType
)

// FileInfo contains information about a media file
type FileInfo struct {
	Path     string
	Size     int64
	Checksum string
	Type     MediaType
	Format   string
}

// Validator provides file validation capabilities
type Validator struct {
	audioExts []string
	videoExts []string
}

// NewValidator creates a new validator
func NewValidator(audioExts, videoExts []string) *Validator {
	return &Validator{
		audioExts: audioExts,
		videoExts: videoExts,
	}
}

// ValidateFile validates a media file
func (v *Validator) ValidateFile(path string) (*FileInfo, error) {
	stat, err := os.Stat(path)
	if err != nil {
		return nil, fmt.Errorf("failed to stat file: %w", err)
	}
	
	if stat.IsDir() {
		return nil, fmt.Errorf("path is a directory")
	}
	
	info := &FileInfo{
		Path:   path,
		Size:   stat.Size(),
		Type:   v.GetMediaType(path),
		Format: v.GetFormat(path),
	}
	
	return info, nil
}

// GetMediaType determines the media type from file extension
func (v *Validator) GetMediaType(path string) MediaType {
	ext := strings.ToLower(filepath.Ext(path))
	ext = strings.TrimPrefix(ext, ".")
	
	for _, audioExt := range v.audioExts {
		if ext == audioExt {
			return AudioType
		}
	}
	
	for _, videoExt := range v.videoExts {
		if ext == videoExt {
			return VideoType
		}
	}
	
	return UnknownType
}

// GetFormat returns the file format (extension)
func (v *Validator) GetFormat(path string) string {
	ext := strings.ToLower(filepath.Ext(path))
	return strings.TrimPrefix(ext, ".")
}

// ComputeChecksum computes SHA-256 checksum of a file
func (v *Validator) ComputeChecksum(path string) (string, error) {
	file, err := os.Open(path)
	if err != nil {
		return "", fmt.Errorf("failed to open file: %w", err)
	}
	defer file.Close()
	
	hash := sha256.New()
	if _, err := io.Copy(hash, file); err != nil {
		return "", fmt.Errorf("failed to compute checksum: %w", err)
	}
	
	return hex.EncodeToString(hash.Sum(nil)), nil
}

// VerifyChecksum verifies a file's checksum
func (v *Validator) VerifyChecksum(path, expectedChecksum string) (bool, error) {
	actualChecksum, err := v.ComputeChecksum(path)
	if err != nil {
		return false, err
	}
	
	return actualChecksum == expectedChecksum, nil
}

// IsAudioFile checks if a file is an audio file
func (v *Validator) IsAudioFile(path string) bool {
	return v.GetMediaType(path) == AudioType
}

// IsVideoFile checks if a file is a video file
func (v *Validator) IsVideoFile(path string) bool {
	return v.GetMediaType(path) == VideoType
}

// ScanDirectory scans a directory for media files
func (v *Validator) ScanDirectory(dir string) ([]*FileInfo, error) {
	var files []*FileInfo
	
	err := filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		
		if info.IsDir() {
			return nil
		}
		
		mediaType := v.GetMediaType(path)
		if mediaType == UnknownType {
			return nil
		}
		
		fileInfo := &FileInfo{
			Path:   path,
			Size:   info.Size(),
			Type:   mediaType,
			Format: v.GetFormat(path),
		}
		
		files = append(files, fileInfo)
		return nil
	})
	
	if err != nil {
		return nil, fmt.Errorf("failed to scan directory: %w", err)
	}
	
	return files, nil
}

// ValidateOutputPath ensures output path doesn't exist or can be overwritten
func (v *Validator) ValidateOutputPath(path string, allowOverwrite bool) error {
	_, err := os.Stat(path)
	if err == nil {
		if !allowOverwrite {
			return fmt.Errorf("output file already exists: %s", path)
		}
	} else if !os.IsNotExist(err) {
		return fmt.Errorf("failed to check output path: %w", err)
	}
	
	return nil
}
