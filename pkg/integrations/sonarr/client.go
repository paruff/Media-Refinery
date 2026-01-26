package sonarr

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/paruff/media-refinery/pkg/metadata"
)

// Client represents a Sonarr API client
type Client struct {
	baseURL    string
	httpClient *http.Client
	apiKey     string
}

// Series represents a TV series in Sonarr
type Series struct {
	ID           int      `json:"id"`
	Title        string   `json:"title"`
	Year         int      `json:"year"`
	Path         string   `json:"path"`
	Genres       []string `json:"genres"`
	TVDbID       int      `json:"tvdbId"`
	IMDbID       string   `json:"imdbId"`
	Overview     string   `json:"overview"`
	Network      string   `json:"network"`
	Monitored    bool     `json:"monitored"`
	SeasonCount  int      `json:"seasonCount"`
}

// Episode represents an episode in Sonarr
type Episode struct {
	ID                 int    `json:"id"`
	SeriesID           int    `json:"seriesId"`
	SeasonNumber       int    `json:"seasonNumber"`
	EpisodeNumber      int    `json:"episodeNumber"`
	Title              string `json:"title"`
	AirDate            string `json:"airDate"`
	Overview           string `json:"overview"`
	HasFile            bool   `json:"hasFile"`
	EpisodeFileID      int    `json:"episodeFileId,omitempty"`
}

// EpisodeFile represents an episode file in Sonarr
type EpisodeFile struct {
	ID           int     `json:"id"`
	SeriesID     int     `json:"seriesId"`
	SeasonNumber int     `json:"seasonNumber"`
	RelativePath string  `json:"relativePath"`
	Path         string  `json:"path"`
	Size         int64   `json:"size"`
	Quality      Quality `json:"quality"`
}

// Quality represents quality information
type Quality struct {
	Quality  QualityDefinition `json:"quality"`
	Revision Revision          `json:"revision"`
}

// QualityDefinition represents a quality level
type QualityDefinition struct {
	ID   int    `json:"id"`
	Name string `json:"name"`
}

// Revision represents quality revision
type Revision struct {
	Version  int  `json:"version"`
	Real     int  `json:"real"`
	IsRepack bool `json:"isRepack"`
}

// RenamePreview represents a rename preview
type RenamePreview struct {
	SeriesID        int    `json:"seriesId"`
	SeasonNumber    int    `json:"seasonNumber"`
	EpisodeNumbers  []int  `json:"episodeNumbers"`
	EpisodeFileID   int    `json:"episodeFileId"`
	ExistingPath    string `json:"existingPath"`
	NewPath         string `json:"newPath"`
}

// NewClient creates a new Sonarr API client
func NewClient(baseURL, apiKey string) *Client {
	return &Client{
		baseURL: baseURL,
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
		apiKey: apiKey,
	}
}

// GetSeries retrieves a specific series by ID
func (c *Client) GetSeries(id int) (*Series, error) {
	url := fmt.Sprintf("%s/api/v3/series/%d", c.baseURL, id)
	
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	
	req.Header.Set("X-Api-Key", c.apiKey)
	
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("API returned status %d: %s", resp.StatusCode, string(body))
	}
	
	var series Series
	if err := json.NewDecoder(resp.Body).Decode(&series); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}
	
	return &series, nil
}

// LookupSeries searches for series by title
func (c *Client) LookupSeries(title string) ([]Series, error) {
	url := fmt.Sprintf("%s/api/v3/series/lookup?term=%s", c.baseURL, title)
	
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	
	req.Header.Set("X-Api-Key", c.apiKey)
	
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("API returned status %d", resp.StatusCode)
	}
	
	var series []Series
	if err := json.NewDecoder(resp.Body).Decode(&series); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}
	
	return series, nil
}

// GetEpisode retrieves a specific episode by ID
func (c *Client) GetEpisode(id int) (*Episode, error) {
	url := fmt.Sprintf("%s/api/v3/episode/%d", c.baseURL, id)
	
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	
	req.Header.Set("X-Api-Key", c.apiKey)
	
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("API returned status %d", resp.StatusCode)
	}
	
	var episode Episode
	if err := json.NewDecoder(resp.Body).Decode(&episode); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}
	
	return &episode, nil
}

// GetRenamePreview gets a preview of how files would be renamed
func (c *Client) GetRenamePreview(seriesID int) ([]RenamePreview, error) {
	url := fmt.Sprintf("%s/api/v3/rename?seriesId=%d", c.baseURL, seriesID)
	
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	
	req.Header.Set("X-Api-Key", c.apiKey)
	
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("API returned status %d", resp.StatusCode)
	}
	
	var previews []RenamePreview
	if err := json.NewDecoder(resp.Body).Decode(&previews); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}
	
	return previews, nil
}

// RenameFiles triggers a rename operation for a series
func (c *Client) RenameFiles(seriesIDs []int) error {
	url := fmt.Sprintf("%s/api/v3/command", c.baseURL)
	
	command := map[string]interface{}{
		"name":      "RenameSeries",
		"seriesIds": seriesIDs,
	}
	
	jsonData, err := json.Marshal(command)
	if err != nil {
		return fmt.Errorf("failed to marshal request: %w", err)
	}
	
	req, err := http.NewRequest("POST", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}
	
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Api-Key", c.apiKey)
	
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusCreated {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("API returned status %d: %s", resp.StatusCode, string(body))
	}
	
	return nil
}

// ToMetadata converts a Sonarr series and episode to our metadata format
func (s *Series) ToMetadata(ep *Episode) *metadata.Metadata {
	genre := ""
	if len(s.Genres) > 0 {
		genre = s.Genres[0]
	}
	
	meta := &metadata.Metadata{
		Title:    s.Title,
		Year:     fmt.Sprintf("%d", s.Year),
		Genre:    genre,
		Comment:  s.Overview,
		Show:     s.Title,
		FilePath: s.Path,
	}
	
	if ep != nil {
		meta.Episode = fmt.Sprintf("%d", ep.EpisodeNumber)
		meta.Season = fmt.Sprintf("%d", ep.SeasonNumber)
		meta.Title = ep.Title
	}
	
	return meta
}

// GetMetadataByTitle retrieves metadata for a series by title
func (c *Client) GetMetadataByTitle(title string, season, episode int) (*metadata.Metadata, error) {
	series, err := c.LookupSeries(title)
	if err != nil {
		return nil, err
	}
	
	if len(series) == 0 {
		return nil, fmt.Errorf("no series found with title: %s", title)
	}
	
	return series[0].ToMetadata(nil), nil
}

// HealthCheck checks if the Sonarr server is accessible
func (c *Client) HealthCheck() error {
	url := fmt.Sprintf("%s/api/v3/system/status", c.baseURL)
	
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}
	
	req.Header.Set("X-Api-Key", c.apiKey)
	
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("health check failed: %w", err)
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("health check returned status %d", resp.StatusCode)
	}
	
	return nil
}
