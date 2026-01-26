package radarr

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/paruff/media-refinery/pkg/metadata"
)

// Client represents a Radarr API client
type Client struct {
	baseURL    string
	httpClient *http.Client
	apiKey     string
}

// Movie represents a movie in Radarr
type Movie struct {
	ID            int      `json:"id"`
	Title         string   `json:"title"`
	OriginalTitle string   `json:"originalTitle"`
	Year          int      `json:"year"`
	Path          string   `json:"path"`
	Genres        []string `json:"genres"`
	IMDbID        string   `json:"imdbId"`
	TMDbID        int      `json:"tmdbId"`
	Overview      string   `json:"overview"`
	Studio        string   `json:"studio"`
	Monitored     bool     `json:"monitored"`
	HasFile       bool     `json:"hasFile"`
}

// MovieFile represents a movie file in Radarr
type MovieFile struct {
	ID           int     `json:"id"`
	MovieID      int     `json:"movieId"`
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
	MovieID      int    `json:"movieId"`
	MovieFileID  int    `json:"movieFileId"`
	ExistingPath string `json:"existingPath"`
	NewPath      string `json:"newPath"`
}

// NewClient creates a new Radarr API client
func NewClient(baseURL, apiKey string) *Client {
	return &Client{
		baseURL: baseURL,
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
		apiKey: apiKey,
	}
}

// GetMovie retrieves a specific movie by ID
func (c *Client) GetMovie(id int) (*Movie, error) {
	url := fmt.Sprintf("%s/api/v3/movie/%d", c.baseURL, id)
	
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
	
	var movie Movie
	if err := json.NewDecoder(resp.Body).Decode(&movie); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}
	
	return &movie, nil
}

// LookupMovie searches for movies by title
func (c *Client) LookupMovie(title string) ([]Movie, error) {
	url := fmt.Sprintf("%s/api/v3/movie/lookup?term=%s", c.baseURL, title)
	
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
	
	var movies []Movie
	if err := json.NewDecoder(resp.Body).Decode(&movies); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}
	
	return movies, nil
}

// GetRenamePreview gets a preview of how files would be renamed
func (c *Client) GetRenamePreview(movieID int) ([]RenamePreview, error) {
	url := fmt.Sprintf("%s/api/v3/rename?movieId=%d", c.baseURL, movieID)
	
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

// RenameFiles triggers a rename operation for a movie
func (c *Client) RenameFiles(movieIDs []int) error {
	url := fmt.Sprintf("%s/api/v3/command", c.baseURL)
	
	command := map[string]interface{}{
		"name":     "RenameMovie",
		"movieIds": movieIDs,
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

// ToMetadata converts a Radarr movie to our metadata format
func (m *Movie) ToMetadata() *metadata.Metadata {
	genre := ""
	if len(m.Genres) > 0 {
		genre = m.Genres[0]
	}
	
	return &metadata.Metadata{
		Title:    m.Title,
		Year:     fmt.Sprintf("%d", m.Year),
		Genre:    genre,
		Comment:  m.Overview,
		FilePath: m.Path,
	}
}

// GetMetadataByTitle retrieves metadata for a movie by title
func (c *Client) GetMetadataByTitle(title string) (*metadata.Metadata, error) {
	movies, err := c.LookupMovie(title)
	if err != nil {
		return nil, err
	}
	
	if len(movies) == 0 {
		return nil, fmt.Errorf("no movie found with title: %s", title)
	}
	
	return movies[0].ToMetadata(), nil
}

// HealthCheck checks if the Radarr server is accessible
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
