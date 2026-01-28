package validator

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"os"
	"os/exec"
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
	logger    *log.Logger
}

// NewValidator creates a new validator
func NewValidator(audioExts, videoExts []string) *Validator {
	return &Validator{
		audioExts: audioExts,
		videoExts: videoExts,
		logger:    log.New(os.Stdout, "", 0),
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
	// Debug logging for path input
	fmt.Printf("Input path: '%s' (bytes: %v)\n", path, []byte(path))

	ext := strings.ToLower(strings.TrimSpace(filepath.Ext(path)))
	ext = strings.TrimPrefix(ext, ".")

	// Debug logging with byte representation
	fmt.Printf("Extracted extension: '%s' (bytes: %v)\n", ext, []byte(ext))
	for i, audioExt := range v.audioExts {
		fmt.Printf("Comparing with audioExt[%d]: '%s' (bytes: %v)\n", i, audioExt, []byte(audioExt))
		if ext == strings.TrimSpace(audioExt) {
			return AudioType
		}
	}

	for i, videoExt := range v.videoExts {
		fmt.Printf("Comparing with videoExt[%d]: '%s' (bytes: %v)\n", i, videoExt, []byte(videoExt))
		if ext == strings.TrimSpace(videoExt) {
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
	       var closeErr error
	       defer func() {
		       cerr := file.Close()
		       if cerr != nil {
			       closeErr = cerr
			       fmt.Printf("failed to close file: %v", cerr)
		       }
	       }()

	       hash := sha256.New()
	       if _, err := io.Copy(hash, file); err != nil {
		       return "", fmt.Errorf("failed to compute checksum: %w", err)
	       }
	       if closeErr != nil {
		       return "", fmt.Errorf("failed to close file: %w", closeErr)
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
		// Log configured audio and video extensions for debugging
		fmt.Printf("Configured audio extensions: %v\n", v.audioExts)
		fmt.Printf("Configured video extensions: %v\n", v.videoExts)
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

// ProbeMediaFile validates a media file using ffprobe to ensure it's not corrupted
func (v *Validator) ProbeMediaFile(path string) error {
	cmd := exec.Command("ffprobe",
		"-v", "error",
		"-show_entries", "format=duration,size,bit_rate:stream=codec_type,codec_name",
		"-of", "json",
		path,
	)

	// Debug logging for ffprobe command
	log.Printf("Running ffprobe command: %v", cmd.Args)

	output, err := cmd.CombinedOutput()
	if err != nil {
		log.Printf("ffprobe error: %v, output: %s", err, string(output))
		return fmt.Errorf("ffprobe failed - file may be corrupted: %w", err)
	}

	var result struct {
		Format struct {
			Duration string `json:"duration"`
			Size     string `json:"size"`
		} `json:"format"`
		Streams []struct {
			CodecType string `json:"codec_type"`
			CodecName string `json:"codec_name"`
		} `json:"streams"`
	}

	if err := json.Unmarshal(output, &result); err != nil {
		return fmt.Errorf("failed to parse ffprobe output: %w", err)
	}

	// Check if file has at least one valid stream
	if len(result.Streams) == 0 {
		return fmt.Errorf("no valid streams found in file")
	}

	// Check if we have valid codec info
	hasValidStream := false
	for _, stream := range result.Streams {
		if stream.CodecName != "" && stream.CodecType != "" {
			hasValidStream = true
			break
		}
	}

	if !hasValidStream {
		return fmt.Errorf("no valid codec information found - file may be corrupted")
	}

	// Check if duration is valid for video/audio
	if result.Format.Duration == "" || result.Format.Duration == "N/A" {
		return fmt.Errorf("invalid or missing duration - file may be corrupted")
	}

	return nil
}

// ValidateMediaIntegrity performs comprehensive validation including ffprobe check
func (v *Validator) ValidateMediaIntegrity(path string) (*FileInfo, error) {
	// Basic file validation
	fileInfo, err := v.ValidateFile(path)
	if err != nil {
		return nil, fmt.Errorf("basic validation failed: %w", err)
	}

	// Check file size
	if fileInfo.Size == 0 {
		return nil, fmt.Errorf("file is empty")
	}

	// Probe file with ffprobe to check integrity
	if err := v.ProbeMediaFile(path); err != nil {
		return nil, fmt.Errorf("integrity check failed: %w", err)
	}

	return fileInfo, nil
}
