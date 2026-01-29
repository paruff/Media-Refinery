package audio

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

type FormatDetector struct{}

// NewFormatDetector constructs a new FormatDetector
func NewFormatDetector() *FormatDetector { return &FormatDetector{} }

// IsSupported reports whether a format is supported
func (d *FormatDetector) IsSupported(format string) bool {
	switch strings.ToLower(format) {
	case "mp3", "aac", "m4a", "ogg", "wav", "flac", "opus":
		return true
	default:
		return false
	}
}

// DetectFromExtension attempts to detect format from filename extension
func (d *FormatDetector) DetectFromExtension(filename string) (string, error) {
	ext := strings.ToLower(filepath.Ext(filename))
	if ext == "" {
		return "", fmt.Errorf("no extension")
	}
	ext = strings.TrimPrefix(ext, ".")
	if d.IsSupported(ext) {
		return ext, nil
	}
	return "", fmt.Errorf("unsupported extension: %s", ext)
}

// DetectFromContent reads the beginning of the file to detect format by magic numbers
func (d *FormatDetector) DetectFromContent(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer func() { _ = f.Close() }()
	buf := make([]byte, 8)
	n, err := f.Read(buf)
	if err != nil {
		return "", err
	}
	s := string(buf[:n])
	if strings.HasPrefix(s, "fLaC") {
		return "flac", nil
	}
	if strings.HasPrefix(s, "RIFF") {
		return "wav", nil
	}
	if strings.HasPrefix(s, "OggS") {
		return "ogg", nil
	}
	if len(buf) >= 2 && buf[0] == 0xFF && buf[1] == 0xFB {
		return "mp3", nil
	}
	if strings.HasPrefix(s, "ID3") {
		return "mp3", nil
	}
	// Fallback to extension-based detection
	return d.DetectFromExtension(path)
}

// DetectFormat convenience wrapper used by some tests
func (d *FormatDetector) DetectFormat(path string) (string, error) {
	if format, err := d.DetectFromContent(path); err == nil {
		return format, nil
	}
	return d.DetectFromExtension(path)
}
