package beets

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestBeetsClient_HTTP(t *testing.T) {
	// Setup fake server
	mux := http.NewServeMux()

	mux.HandleFunc("/item/", func(w http.ResponseWriter, r *http.Request) {
		// simulate query endpoint
		q := r.URL.Query().Get("query")
		if q != "path:/some/path" && q != "" {
			// return empty
			w.WriteHeader(http.StatusOK)
			json.NewEncoder(w).Encode(map[string]interface{}{"results": []interface{}{}})
			return
		}
		resp := map[string]interface{}{"results": []map[string]interface{}{{
			"id":          1,
			"title":       "S",
			"artist":      "A",
			"album":       "AL",
			"albumartist": "AA",
			"track":       1,
			"year":        2020,
			"genre":       "Rock",
			"path":        "/some/path",
			"length":      3.5,
			"bitrate":     320,
			"format":      "mp3",
		}}}
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(resp)
	})

	mux.HandleFunc("/item/1", func(w http.ResponseWriter, r *http.Request) {
		item := map[string]interface{}{
			"id":          1,
			"title":       "S",
			"artist":      "A",
			"album":       "AL",
			"albumartist": "AA",
			"track":       1,
			"year":        2020,
			"genre":       "Rock",
			"path":        "/some/path",
			"length":      3.5,
			"bitrate":     320,
			"format":      "mp3",
		}
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(item)
	})

	mux.HandleFunc("/import", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" {
			w.WriteHeader(http.StatusMethodNotAllowed)
			return
		}
		w.WriteHeader(http.StatusCreated)
	})

	mux.HandleFunc("/stats", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("{}"))
	})

	server := httptest.NewServer(mux)
	defer server.Close()

	client := NewClient(server.URL, "")

	// Query
	items, err := client.Query("path:/some/path")
	if err != nil {
		t.Fatalf("Query failed: %v", err)
	}
	if len(items) != 1 {
		t.Fatalf("expected 1 item, got %d", len(items))
	}

	// GetItem
	item, err := client.GetItem(1)
	if err != nil {
		t.Fatalf("GetItem failed: %v", err)
	}
	if item.ID != 1 {
		t.Fatalf("unexpected item id: %v", item.ID)
	}

	// Import
	if err := client.Import([]string{"/foo"}, true, false, false); err != nil {
		t.Fatalf("Import failed: %v", err)
	}

	// HealthCheck
	if err := client.HealthCheck(); err != nil {
		t.Fatalf("HealthCheck failed: %v", err)
	}

	// GetMetadataForFile
	meta, err := client.GetMetadataForFile("/some/path")
	if err != nil {
		t.Fatalf("GetMetadataForFile failed: %v", err)
	}
	if meta.FilePath != "/some/path" {
		t.Fatalf("unexpected metadata path: %s", meta.FilePath)
	}
}
