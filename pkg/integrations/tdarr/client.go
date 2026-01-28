package tdarr

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// Client represents a Tdarr API client
type Client struct {
	baseURL    string
	httpClient *http.Client
	apiKey     string
}

// TranscodeRequest represents a transcode job request
type TranscodeRequest struct {
	FilePath string            `json:"file_path"`
	Options  map[string]string `json:"options"`
}

// TranscodeJob represents a transcode job
type TranscodeJob struct {
	ID       string  `json:"_id"`
	FilePath string  `json:"file"`
	Status   string  `json:"status"`
	Progress float64 `json:"progress"`
	Error    string  `json:"error,omitempty"`
}

// LibraryStats represents library statistics
type LibraryStats struct {
	TotalFiles      int     `json:"totalFiles"`
	ProcessedFiles  int     `json:"processedFiles"`
	TotalSize       int64   `json:"totalSize"`
	HealthCheckSize int64   `json:"healthCheckSize"`
	SavingsSize     int64   `json:"savingsSize"`
}

// NewClient creates a new Tdarr API client
func NewClient(baseURL, apiKey string) *Client {
	return &Client{
		baseURL: baseURL,
		httpClient: &http.Client{
			Timeout: 60 * time.Second,
		},
		apiKey: apiKey,
	}
}

// SubmitJob submits a file for transcoding
func (c *Client) SubmitJob(filePath string, options map[string]string) (*TranscodeJob, error) {
	url := fmt.Sprintf("%s/api/v2/cruddb", c.baseURL)
	
	request := map[string]interface{}{
		"data": map[string]interface{}{
			"collection": "TranscodeDecisionMakerQueueDB",
			"mode":       "insert",
			"obj": map[string]interface{}{
				"file":    filePath,
				"status":  "queued",
				"options": options,
			},
		},
	}
	
	jsonData, err := json.Marshal(request)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}
	
	req, err := http.NewRequest("POST", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	
	req.Header.Set("Content-Type", "application/json")
	if c.apiKey != "" {
		req.Header.Set("x-api-key", c.apiKey)
	}
	
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}
	defer func() {
		if err := resp.Body.Close(); err != nil {
			fmt.Printf("failed to close response body: %v", err)
		}
	}()
	
	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("API returned status %d: %s", resp.StatusCode, string(body))
	}
	
	var result struct {
		ID string `json:"_id"`
	}
	
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}
	
	return &TranscodeJob{
		ID:       result.ID,
		FilePath: filePath,
		Status:   "queued",
	}, nil
}

// GetJobStatus retrieves the status of a transcode job
func (c *Client) GetJobStatus(jobID string) (*TranscodeJob, error) {
	url := fmt.Sprintf("%s/api/v2/cruddb", c.baseURL)
	
	request := map[string]interface{}{
		"data": map[string]interface{}{
			"collection": "TranscodeDecisionMakerQueueDB",
			"mode":       "getById",
			"docID":      jobID,
		},
	}
	
	jsonData, err := json.Marshal(request)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}
	
	req, err := http.NewRequest("POST", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	
	req.Header.Set("Content-Type", "application/json")
	if c.apiKey != "" {
		req.Header.Set("x-api-key", c.apiKey)
	}
	
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}
	defer func() {
		if err := resp.Body.Close(); err != nil {
			fmt.Printf("failed to close response body: %v", err)
		}
	}()
	
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("API returned status %d", resp.StatusCode)
	}
	
	var job TranscodeJob
	if err := json.NewDecoder(resp.Body).Decode(&job); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}
	
	return &job, nil
}

// WaitForJob waits for a transcode job to complete
func (c *Client) WaitForJob(jobID string, timeout time.Duration) (*TranscodeJob, error) {
	deadline := time.Now().Add(timeout)
	
	for time.Now().Before(deadline) {
		job, err := c.GetJobStatus(jobID)
		if err != nil {
			return nil, err
		}
		
		if job.Status == "completed" || job.Status == "success" {
			return job, nil
		}
		
		if job.Status == "error" || job.Status == "failed" {
			return job, fmt.Errorf("job failed: %s", job.Error)
		}
		
		time.Sleep(5 * time.Second)
	}
	
	return nil, fmt.Errorf("job timeout after %v", timeout)
}

// GetLibraryStats retrieves library statistics
func (c *Client) GetLibraryStats(libraryID string) (*LibraryStats, error) {
	url := fmt.Sprintf("%s/api/v2/get-library-stats", c.baseURL)
	
	request := map[string]interface{}{
		"data": map[string]interface{}{
			"libraryId": libraryID,
		},
	}
	
	jsonData, err := json.Marshal(request)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}
	
	req, err := http.NewRequest("POST", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	
	req.Header.Set("Content-Type", "application/json")
	if c.apiKey != "" {
		req.Header.Set("x-api-key", c.apiKey)
	}
	
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}
	defer func() {
		if err := resp.Body.Close(); err != nil {
			fmt.Printf("failed to close response body: %v", err)
		}
	}()
	
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("API returned status %d", resp.StatusCode)
	}
	
	var stats LibraryStats
	if err := json.NewDecoder(resp.Body).Decode(&stats); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}
	
	return &stats, nil
}

// HealthCheck checks if the Tdarr server is accessible
func (c *Client) HealthCheck() error {
	url := fmt.Sprintf("%s/api/v2/status", c.baseURL)
	
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}
	
	if c.apiKey != "" {
		req.Header.Set("x-api-key", c.apiKey)
	}
	
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("health check failed: %w", err)
	}
	defer func() {
		if err := resp.Body.Close(); err != nil {
			fmt.Printf("failed to close response body: %v", err)
		}
	}()
	
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("health check returned status %d", resp.StatusCode)
	}
	
	return nil
}
