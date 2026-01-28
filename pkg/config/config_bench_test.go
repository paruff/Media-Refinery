package config

import (
	"path/filepath"
	"testing"
)

func BenchmarkLoadConfig(b *testing.B) {
	// Create a temporary config file
	tempDir := b.TempDir()
	configPath := filepath.Join(tempDir, "config.yaml")

	cfg := DefaultConfig()
	cfg.InputDir = "/benchmark/input"
	cfg.OutputDir = "/benchmark/output"
	if err := cfg.SaveConfig(configPath); err != nil {
		b.Fatalf("Failed to save config: %v", err)
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, err := LoadConfig(configPath)
		if err != nil {
			b.Fatalf("Failed to load config: %v", err)
		}
	}
}

func BenchmarkValidate(b *testing.B) {
	cfg := DefaultConfig()
	cfg.InputDir = "/benchmark/input"
	cfg.OutputDir = "/benchmark/output"

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		if err := cfg.Validate(); err != nil {
			b.Fatalf("Validation failed: %v", err)
		}
	}
}