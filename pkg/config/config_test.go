package config

import (
	"os"
	"path/filepath"
	"testing"
)

func TestDefaultConfig(t *testing.T) {
	cfg := DefaultConfig()

	if cfg == nil {
		t.Fatal("DefaultConfig returned nil")
	}

	if cfg.InputDir == "" {
		t.Error("InputDir should have a default value")
	}

	if cfg.OutputDir == "" {
		t.Error("OutputDir should have a default value")
	}

	if cfg.Concurrency < 1 {
		t.Error("Concurrency should be at least 1")
	}

	if cfg.Audio.OutputFormat != "flac" {
		t.Errorf("Expected default audio format to be 'flac', got %s", cfg.Audio.OutputFormat)
	}

	if cfg.Video.OutputFormat != "mkv" {
		t.Errorf("Expected default video format to be 'mkv', got %s", cfg.Video.OutputFormat)
	}
}

func TestConfigValidation(t *testing.T) {
	tests := []struct {
		name    string
		cfg     *Config
		wantErr bool
	}{
		{
			name:    "valid config",
			cfg:     DefaultConfig(),
			wantErr: false,
		},
		{
			name: "missing input dir",
			cfg: &Config{
				InputDir:    "",
				OutputDir:   "./output",
				Concurrency: 4,
			},
			wantErr: true,
		},
		{
			name: "missing output dir",
			cfg: &Config{
				InputDir:    "./input",
				OutputDir:   "",
				Concurrency: 4,
			},
			wantErr: true,
		},
		{
			name: "invalid concurrency",
			cfg: &Config{
				InputDir:    "./input",
				OutputDir:   "./output",
				Concurrency: 0,
			},
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.cfg.Validate()
			if (err != nil) != tt.wantErr {
				t.Errorf("Validate() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestLoadConfig(t *testing.T) {
	// Create a temporary config file
	tmpDir := t.TempDir()
	configPath := filepath.Join(tmpDir, "config.yaml")

	cfg := DefaultConfig()
	cfg.InputDir = "/custom/input"
	cfg.OutputDir = "/custom/output"

	if err := cfg.SaveConfig(configPath); err != nil {
		t.Fatalf("Failed to save config: %v", err)
	}

	// Load it back
	loaded, err := LoadConfig(configPath)
	if err != nil {
		t.Fatalf("Failed to load config: %v", err)
	}

	if loaded.InputDir != cfg.InputDir {
		t.Errorf("Expected InputDir %s, got %s", cfg.InputDir, loaded.InputDir)
	}

	if loaded.OutputDir != cfg.OutputDir {
		t.Errorf("Expected OutputDir %s, got %s", cfg.OutputDir, loaded.OutputDir)
	}
}

func TestLoadConfigNonExistent(t *testing.T) {
	// Loading a non-existent config should return default config
	cfg, err := LoadConfig("nonexistent.yaml")
	if err != nil {
		t.Fatalf("LoadConfig should not error on non-existent file: %v", err)
	}

	if cfg == nil {
		t.Fatal("LoadConfig should return default config for non-existent file")
	}

	// Should be default values
	if cfg.Audio.OutputFormat != "flac" {
		t.Errorf("Expected default audio format")
	}
}

func TestSaveConfig(t *testing.T) {
	tmpDir := t.TempDir()
	configPath := filepath.Join(tmpDir, "subdir", "config.yaml")

	cfg := DefaultConfig()
	if err := cfg.SaveConfig(configPath); err != nil {
		t.Fatalf("SaveConfig failed: %v", err)
	}

	// Verify file exists
	if _, err := os.Stat(configPath); os.IsNotExist(err) {
		t.Error("Config file was not created")
	}

	// Verify directory was created
	if _, err := os.Stat(filepath.Dir(configPath)); os.IsNotExist(err) {
		t.Error("Config directory was not created")
	}
}
