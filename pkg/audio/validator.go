package audio

import (
	"fmt"
	"os"
)

type FormatValidator struct{}

func NewFormatValidator() *FormatValidator { return &FormatValidator{} }

// ValidateFile performs lightweight validation of audio file headers.
func (v *FormatValidator) ValidateFile(path string) error {
	fi, err := os.Stat(path)
	if err != nil {
		return fmt.Errorf("stat file: %w", err)
	}
	f, err := os.Open(path)
	if err != nil {
		return fmt.Errorf("open file: %w", err)
	}
	defer func() { _ = f.Close() }()
	buf := make([]byte, 12)
	n, err := f.Read(buf)
	if err != nil {
		return fmt.Errorf("read header: %w", err)
	}
	if n == 0 {
		return fmt.Errorf("invalid: empty file")
	}
	s := string(buf[:n])
	// FLAC
	if len(s) >= 4 && s[:4] == "fLaC" {
		return nil
	}
	// WAV
	if len(s) >= 4 && s[:4] == "RIFF" {
		if fi.Size() < 44 {
			return fmt.Errorf("incomplete wav header")
		}
		return nil
	}
	// OGG
	if len(s) >= 4 && s[:4] == "OggS" {
		return nil
	}
	// MP3 (ID3 or frame sync)
	if len(s) >= 3 && s[:3] == "ID3" {
		return nil
	}
	if n >= 2 && buf[0] == 0xFF && buf[1] == 0xFB {
		return nil
	}
	return fmt.Errorf("invalid audio file")
}
