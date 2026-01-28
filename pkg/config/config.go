package config

import (
	"fmt"
	"os"
	"path/filepath"

	"gopkg.in/yaml.v3"
)

// Config represents the main configuration for the media refinery
type Config struct {
	// General settings
	InputDir        string `yaml:"input_dir"`
	OutputDir       string `yaml:"output_dir"`
	WorkDir         string `yaml:"work_dir"`
	DryRun          bool   `yaml:"dry_run"`
	VerifyChecksums bool   `yaml:"verify_checksums"`

	// Processing settings
	Concurrency int `yaml:"concurrency"`
	ChunkSize   int `yaml:"chunk_size"`

	// Audio settings
	Audio AudioConfig `yaml:"audio"`

	// Video settings
	Video VideoConfig `yaml:"video"`

	// Metadata settings
	Metadata MetadataConfig `yaml:"metadata"`

	// Organization settings
	Organization OrganizationConfig `yaml:"organization"`

	// Logging settings
	Logging LoggingConfig `yaml:"logging"`

	// Integration settings
	Integrations IntegrationConfig `yaml:"integrations"`
}

// AudioConfig contains audio processing settings
type AudioConfig struct {
	Enabled        bool     `yaml:"enabled"`
	OutputFormat   string   `yaml:"output_format"`  // flac, mp3, aac
	OutputQuality  string   `yaml:"output_quality"` // lossless, high, medium
	SupportedTypes []string `yaml:"supported_types"`
	Normalize      bool     `yaml:"normalize"`
	BitDepth       int      `yaml:"bit_depth"`
	SampleRate     int      `yaml:"sample_rate"`
}

// VideoConfig contains video processing settings
type VideoConfig struct {
	Enabled        bool     `yaml:"enabled"`
	OutputFormat   string   `yaml:"output_format"` // mkv, mp4
	VideoCodec     string   `yaml:"video_codec"`   // h264, h265
	AudioCodec     string   `yaml:"audio_codec"`   // aac, ac3
	SupportedTypes []string `yaml:"supported_types"`
	Quality        string   `yaml:"quality"`    // high, medium, low
	Resolution     string   `yaml:"resolution"` // keep, 1080p, 720p
}

// MetadataConfig contains metadata processing settings
type MetadataConfig struct {
	FetchOnline  bool     `yaml:"fetch_online"`
	Sources      []string `yaml:"sources"` // musicbrainz, tmdb, etc.
	EmbedArtwork bool     `yaml:"embed_artwork"`
	CleanupTags  bool     `yaml:"cleanup_tags"`
}

// OrganizationConfig contains file organization settings
type OrganizationConfig struct {
	MusicPattern string `yaml:"music_pattern"`
	VideoPattern string `yaml:"video_pattern"`
	UseSymlinks  bool   `yaml:"use_symlinks"`
}

// LoggingConfig contains logging settings
type LoggingConfig struct {
	Level      string `yaml:"level"`  // debug, info, warn, error
	Format     string `yaml:"format"` // json, text
	OutputFile string `yaml:"output_file"`
}

// IntegrationConfig contains third-party integration settings
type IntegrationConfig struct {
	Beets  BeetsConfig  `yaml:"beets"`
	Tdarr  TdarrConfig  `yaml:"tdarr"`
	Radarr RadarrConfig `yaml:"radarr"`
	Sonarr SonarrConfig `yaml:"sonarr"`
}

// BeetsConfig contains beets integration settings
type BeetsConfig struct {
	Enabled bool   `yaml:"enabled"`
	URL     string `yaml:"url"`
	Token   string `yaml:"token"`
}

// TdarrConfig contains Tdarr integration settings
type TdarrConfig struct {
	Enabled   bool   `yaml:"enabled"`
	URL       string `yaml:"url"`
	APIKey    string `yaml:"api_key"`
	LibraryID string `yaml:"library_id"`
}

// RadarrConfig contains Radarr integration settings
type RadarrConfig struct {
	Enabled bool   `yaml:"enabled"`
	URL     string `yaml:"url"`
	APIKey  string `yaml:"api_key"`
}

// SonarrConfig contains Sonarr integration settings
type SonarrConfig struct {
	Enabled bool   `yaml:"enabled"`
	URL     string `yaml:"url"`
	APIKey  string `yaml:"api_key"`
}

// DefaultConfig returns a default configuration
func DefaultConfig() *Config {
	return &Config{
		InputDir:        "./input",
		OutputDir:       "./output",
		WorkDir:         "./work",
		DryRun:          false,
		VerifyChecksums: true,
		Concurrency:     4,
		ChunkSize:       100,
		Audio: AudioConfig{
			Enabled:        true,
			OutputFormat:   "flac",
			OutputQuality:  "lossless",
			SupportedTypes: []string{"mp3", "flac", "aac", "m4a", "ogg", "wav"},
			Normalize:      true,
			BitDepth:       16,
			SampleRate:     44100,
		},
		Video: VideoConfig{
			Enabled:        true,
			OutputFormat:   "mkv",
			VideoCodec:     "h264",
			AudioCodec:     "aac",
			SupportedTypes: []string{"avi", "mp4", "mkv", "mov", "wmv", "flv"},
			Quality:        "high",
			Resolution:     "keep",
		},
		Metadata: MetadataConfig{
			FetchOnline:  false,
			Sources:      []string{"local"},
			EmbedArtwork: true,
			CleanupTags:  true,
		},
		Organization: OrganizationConfig{
			MusicPattern: "{artist}/{album}/{track} - {title}",
			VideoPattern: "{type}/{title} ({year})/Season {season}/{title} - S{season}E{episode}",
			UseSymlinks:  false,
		},
		Logging: LoggingConfig{
			Level:      "info",
			Format:     "text",
			OutputFile: "",
		},
		Integrations: IntegrationConfig{
			Beets: BeetsConfig{
				Enabled: false,
				URL:     "http://localhost:8337",
				Token:   "",
			},
			Tdarr: TdarrConfig{
				Enabled:   false,
				URL:       "http://localhost:8265",
				APIKey:    "",
				LibraryID: "",
			},
			Radarr: RadarrConfig{
				Enabled: false,
				URL:     "http://localhost:7878",
				APIKey:  "",
			},
			Sonarr: SonarrConfig{
				Enabled: false,
				URL:     "http://localhost:8989",
				APIKey:  "",
			},
		},
	}
}

// LoadConfig loads configuration from a YAML file
func LoadConfig(path string) (*Config, error) {
	config := DefaultConfig()

	if path == "" {
		return config, nil
	}

	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return config, nil
		}
		return nil, fmt.Errorf("failed to read config file: %w", err)
	}

	if err := yaml.Unmarshal(data, config); err != nil {
		return nil, fmt.Errorf("failed to parse config file: %w", err)
	}

	return config, nil
}

// SaveConfig saves the configuration to a YAML file
func (c *Config) SaveConfig(path string) error {
	data, err := yaml.Marshal(c)
	if err != nil {
		return fmt.Errorf("failed to marshal config: %w", err)
	}

	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return fmt.Errorf("failed to create config directory: %w", err)
	}

	if err := os.WriteFile(path, data, 0644); err != nil {
		return fmt.Errorf("failed to write config file: %w", err)
	}

	return nil
}

// Validate validates the configuration
func (c *Config) Validate() error {
	if c.InputDir == "" {
		return fmt.Errorf("input_dir is required")
	}

	if c.OutputDir == "" {
		return fmt.Errorf("output_dir is required")
	}

	if c.Concurrency < 1 {
		return fmt.Errorf("concurrency must be at least 1")
	}

	return nil
}
