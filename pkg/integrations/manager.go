package integrations

import (
	"fmt"

	"github.com/paruff/Media-Refinery/pkg/config"
	"github.com/paruff/Media-Refinery/pkg/integrations/beets"
	"github.com/paruff/Media-Refinery/pkg/integrations/radarr"
	"github.com/paruff/Media-Refinery/pkg/integrations/sonarr"
	"github.com/paruff/Media-Refinery/pkg/integrations/tdarr"
	"github.com/paruff/Media-Refinery/pkg/logger"
	"github.com/paruff/Media-Refinery/pkg/metadata"
	"github.com/paruff/Media-Refinery/pkg/validator"
)

// Manager coordinates all third-party integrations
type Manager struct {
	beets  *beets.Client
	tdarr  *tdarr.Client
	radarr *radarr.Client
	sonarr *sonarr.Client
	logger *logger.Logger
	config *config.Config
}

// NewManager creates a new integration manager
func NewManager(cfg *config.Config, log *logger.Logger) *Manager {
	m := &Manager{
		config: cfg,
		logger: log,
	}

	// Initialize enabled integrations
	if cfg.Integrations.Beets.Enabled {
		m.beets = beets.NewClient(cfg.Integrations.Beets.URL, cfg.Integrations.Beets.Token)
		log.Info("Beets integration enabled: %s", cfg.Integrations.Beets.URL)
	}

	if cfg.Integrations.Tdarr.Enabled {
		m.tdarr = tdarr.NewClient(cfg.Integrations.Tdarr.URL, cfg.Integrations.Tdarr.APIKey)
		log.Info("Tdarr integration enabled: %s", cfg.Integrations.Tdarr.URL)
	}

	if cfg.Integrations.Radarr.Enabled {
		m.radarr = radarr.NewClient(cfg.Integrations.Radarr.URL, cfg.Integrations.Radarr.APIKey)
		log.Info("Radarr integration enabled: %s", cfg.Integrations.Radarr.URL)
	}

	if cfg.Integrations.Sonarr.Enabled {
		m.sonarr = sonarr.NewClient(cfg.Integrations.Sonarr.URL, cfg.Integrations.Sonarr.APIKey)
		log.Info("Sonarr integration enabled: %s", cfg.Integrations.Sonarr.URL)
	}

	return m
}

// HealthCheck checks all enabled integrations
func (m *Manager) HealthCheck() error {
	if m.beets != nil {
		if err := m.beets.HealthCheck(); err != nil {
			return fmt.Errorf("beets health check failed: %w", err)
		}
		m.logger.Info("Beets health check passed")
	}

	if m.tdarr != nil {
		if err := m.tdarr.HealthCheck(); err != nil {
			return fmt.Errorf("tdarr health check failed: %w", err)
		}
		m.logger.Info("Tdarr health check passed")
	}

	if m.radarr != nil {
		if err := m.radarr.HealthCheck(); err != nil {
			return fmt.Errorf("radarr health check failed: %w", err)
		}
		m.logger.Info("Radarr health check passed")
	}

	if m.sonarr != nil {
		if err := m.sonarr.HealthCheck(); err != nil {
			return fmt.Errorf("sonarr health check failed: %w", err)
		}
		m.logger.Info("Sonarr health check passed")
	}

	return nil
}

// GetMetadata retrieves metadata for a file from appropriate integration
func (m *Manager) GetMetadata(path string, mediaType validator.MediaType) (*metadata.Metadata, error) {
	switch mediaType {
	case validator.AudioType:
		if m.beets != nil {
			m.logger.Debug("Fetching audio metadata from beets: %s", path)
			meta, err := m.beets.GetMetadataForFile(path)
			if err != nil {
				m.logger.Warn("Failed to get metadata from beets: %v", err)
				return nil, err
			}
			return meta, nil
		}

	case validator.VideoType:
		// Try to determine if it's a movie or TV show
		// For now, try radarr first, then sonarr
		if m.radarr != nil {
			// Extract title from path for lookup
			// This is a simplified approach
			m.logger.Debug("Attempting movie metadata lookup via Radarr")
			// In a real implementation, we'd parse the filename better
		}

		if m.sonarr != nil {
			m.logger.Debug("Attempting TV show metadata lookup via Sonarr")
			// In a real implementation, we'd parse the filename better
		}
	}

	return nil, fmt.Errorf("no integration available for media type")
}

// SubmitForTranscoding submits a file to Tdarr for transcoding
func (m *Manager) SubmitForTranscoding(path string, options map[string]string) error {
	if m.tdarr == nil {
		return fmt.Errorf("tdarr integration not enabled")
	}

	m.logger.Info("Submitting file to Tdarr: %s", path)

	job, err := m.tdarr.SubmitJob(path, options)
	if err != nil {
		return fmt.Errorf("failed to submit to tdarr: %w", err)
	}

	m.logger.Info("Tdarr job created: %s", job.ID)

	return nil
}

// ImportToBeets imports audio files to beets
func (m *Manager) ImportToBeets(paths []string, copy, move bool) error {
	if m.beets == nil {
		return fmt.Errorf("beets integration not enabled")
	}

	m.logger.Info("Importing %d files to beets", len(paths))

	if err := m.beets.Import(paths, copy, move, true); err != nil {
		return fmt.Errorf("failed to import to beets: %w", err)
	}

	m.logger.Info("Successfully imported files to beets")

	return nil
}

// GetRadarrRenamePreview gets rename preview for a movie
func (m *Manager) GetRadarrRenamePreview(movieID int) (string, string, error) {
	if m.radarr == nil {
		return "", "", fmt.Errorf("radarr integration not enabled")
	}

	previews, err := m.radarr.GetRenamePreview(movieID)
	if err != nil {
		return "", "", fmt.Errorf("failed to get rename preview: %w", err)
	}

	if len(previews) == 0 {
		return "", "", fmt.Errorf("no rename preview available")
	}

	return previews[0].ExistingPath, previews[0].NewPath, nil
}

// GetSonarrRenamePreview gets rename preview for a series
func (m *Manager) GetSonarrRenamePreview(seriesID int) ([]string, []string, error) {
	if m.sonarr == nil {
		return nil, nil, fmt.Errorf("sonarr integration not enabled")
	}

	previews, err := m.sonarr.GetRenamePreview(seriesID)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to get rename preview: %w", err)
	}

	var existing, newPaths []string
	for _, preview := range previews {
		existing = append(existing, preview.ExistingPath)
		newPaths = append(newPaths, preview.NewPath)
	}

	return existing, newPaths, nil
}

// HasBeetsIntegration returns true if beets is enabled
func (m *Manager) HasBeetsIntegration() bool {
	return m.beets != nil
}

// HasTdarrIntegration returns true if tdarr is enabled
func (m *Manager) HasTdarrIntegration() bool {
	return m.tdarr != nil
}

// HasRadarrIntegration returns true if radarr is enabled
func (m *Manager) HasRadarrIntegration() bool {
	return m.radarr != nil
}

// HasSonarrIntegration returns true if sonarr is enabled
func (m *Manager) HasSonarrIntegration() bool {
	return m.sonarr != nil
}

// HasAnyIntegration returns true if any integration is enabled
func (m *Manager) HasAnyIntegration() bool {
	return m.beets != nil || m.tdarr != nil || m.radarr != nil || m.sonarr != nil
}
