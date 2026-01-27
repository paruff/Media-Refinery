package beets

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"time"

	"github.com/paruff/media-refinery/pkg/metadata"
)

// Client represents a beets API client
type Client struct {
	baseURL    string
	httpClient *http.Client
	token      string
}

// BeetsItem represents a music item in beets
type BeetsItem struct {
	ID          int     `json:"id"`
	Title       string  `json:"title"`
	Artist      string  `json:"artist"`
	Album       string  `json:"album"`
	AlbumArtist string  `json:"albumartist"`
	Track       int     `json:"track"`
	Year        int     `json:"year"`
	Genre       string  `json:"genre"`
	Path        string  `json:"path"`
	Length      float64 `json:"length"`
	Bitrate     int     `json:"bitrate"`
	Format      string  `json:"format"`
}

// ImportRequest represents a beets import request
type ImportRequest struct {
	Paths []string `json:"paths"`
	Copy  bool     `json:"copy"`
	Move  bool     `json:"move"`
	Write bool     `json:"write"`
}

// NewClient creates a new beets API client
func NewClient(baseURL, token string) *Client {
	return &Client{
		baseURL: baseURL,
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
		token: token,
	}
}

// Query searches for items in the beets library
func (c *Client) Query(query string) ([]BeetsItem, error) {
	url := fmt.Sprintf("%s/item/?query=%s", c.baseURL, url.QueryEscape(query))
	
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	
	if c.token != "" {
		req.Header.Set("Authorization", "Bearer "+c.token)
	}
	
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("API returned status %d: %s", resp.StatusCode, string(body))
	}
	
	var result struct {
		Items []BeetsItem `json:"results"`
	}
	
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}
	
	return result.Items, nil
}

// GetItem retrieves a specific item by ID
func (c *Client) GetItem(id int) (*BeetsItem, error) {
	url := fmt.Sprintf("%s/item/%d", c.baseURL, id)
	
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	
	if c.token != "" {
		req.Header.Set("Authorization", "Bearer "+c.token)
	}
	
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("API returned status %d", resp.StatusCode)
	}
	
	var item BeetsItem
	if err := json.NewDecoder(resp.Body).Decode(&item); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}
	
	return &item, nil
}

// Import imports files into the beets library
func (c *Client) Import(paths []string, copy, move, write bool) error {
	url := fmt.Sprintf("%s/import", c.baseURL)
	
	importReq := ImportRequest{
		Paths: paths,
		Copy:  copy,
		Move:  move,
		Write: write,
	}
	
	jsonData, err := json.Marshal(importReq)
	if err != nil {
		return fmt.Errorf("failed to marshal request: %w", err)
	}
	
	req, err := http.NewRequest("POST", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}
	
	req.Header.Set("Content-Type", "application/json")
	if c.token != "" {
		req.Header.Set("Authorization", "Bearer "+c.token)
	}
	
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("API returned status %d: %s", resp.StatusCode, string(body))
	}
	
	return nil
}

// ToMetadata converts a beets item to our metadata format
func (i *BeetsItem) ToMetadata() *metadata.Metadata {
	return &metadata.Metadata{
		Title:       i.Title,
		Artist:      i.Artist,
		Album:       i.Album,
		AlbumArtist: i.AlbumArtist,
		Track:       fmt.Sprintf("%d", i.Track),
		Year:        fmt.Sprintf("%d", i.Year),
		Genre:       i.Genre,
		Duration:    i.Length,
		Bitrate:     i.Bitrate,
		Format:      i.Format,
		FilePath:    i.Path,
	}
}

// GetMetadataForFile retrieves metadata for a file path
func (c *Client) GetMetadataForFile(path string) (*metadata.Metadata, error) {
	items, err := c.Query(fmt.Sprintf("path:%s", path))
	if err != nil {
		return nil, err
	}
	
	if len(items) == 0 {
		return nil, fmt.Errorf("no metadata found for file: %s", path)
	}
	
	return items[0].ToMetadata(), nil
}

// HealthCheck checks if the beets server is accessible
func (c *Client) HealthCheck() error {
	url := fmt.Sprintf("%s/stats", c.baseURL)
	
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}
	
	if c.token != "" {
		req.Header.Set("Authorization", "Bearer "+c.token)
	}
	
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
