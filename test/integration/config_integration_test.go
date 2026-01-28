package integration

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/paruff/Media-Refinery/pkg/config"
)

func TestConfigIntegration_LoadAndSave(t *testing.T) {
	t.Run("save and load config successfully", func(t *testing.T) {
		tempDir := t.TempDir()
		configPath := filepath.Join(tempDir, "config.yaml")

		// Create and save a config
		cfg := config.DefaultConfig()
		cfg.InputDir = "/integration/input"
		cfg.OutputDir = "/integration/output"
		require.NoError(t, cfg.SaveConfig(configPath))

		// Load the saved config
		loadedCfg, err := config.LoadConfig(configPath)
		require.NoError(t, err)
		assert.Equal(t, cfg.InputDir, loadedCfg.InputDir)
		assert.Equal(t, cfg.OutputDir, loadedCfg.OutputDir)
	})

	t.Run("load non-existent config returns default", func(t *testing.T) {
		loadedCfg, err := config.LoadConfig("/nonexistent/config.yaml")
		require.NoError(t, err)
		assert.Equal(t, config.DefaultConfig(), loadedCfg)
	})
}

func TestConfigIntegration_Validate(t *testing.T) {
	t.Run("validate integration config", func(t *testing.T) {
		cfg := config.DefaultConfig()
		cfg.InputDir = "/integration/input"
		cfg.OutputDir = "/integration/output"
		assert.NoError(t, cfg.Validate())
	})

	t.Run("validate fails for missing input_dir", func(t *testing.T) {
		cfg := config.DefaultConfig()
		cfg.InputDir = ""
		assert.Error(t, cfg.Validate())
	})
}