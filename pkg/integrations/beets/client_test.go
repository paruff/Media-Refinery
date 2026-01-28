package beets

import (
	"bytes"
	"errors"
	"io/ioutil"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestNewClient(t *testing.T) {
	t.Run("valid inputs", func(t *testing.T) {
		client := NewClient("http://localhost:8337", "test-token")
		require.NotNil(t, client)
		assert.Equal(t, "http://localhost:8337", client.baseURL)
		assert.Equal(t, "test-token", client.token)
	})
}

func TestQuery(t *testing.T) {
	t.Run("successful query", func(t *testing.T) {
		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			assert.Equal(t, "/item/?query=test", r.URL.String())
			w.WriteHeader(http.StatusOK)
			w.Write([]byte(`{"results": [{"id": 1, "title": "Test Song"}]}`))
		}))
		defer server.Close()

		client := NewClient(server.URL, "")
		items, err := client.Query("test")
		require.NoError(t, err)
		assert.Len(t, items, 1)
		assert.Equal(t, "Test Song", items[0].Title)
	})

	t.Run("API error", func(t *testing.T) {
		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			w.WriteHeader(http.StatusInternalServerError)
			w.Write([]byte("Internal Server Error"))
		}))
		defer server.Close()

		client := NewClient(server.URL, "")
		items, err := client.Query("test")
		assert.Error(t, err)
		assert.Nil(t, items)
	})

	t.Run("decode error", func(t *testing.T) {
		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			w.WriteHeader(http.StatusOK)
			w.Write([]byte("invalid json"))
		}))
		defer server.Close()

		client := NewClient(server.URL, "")
		items, err := client.Query("test")
		assert.Error(t, err)
		assert.Nil(t, items)
	})
}

func TestHealthCheck(t *testing.T) {
	t.Run("healthy server", func(t *testing.T) {
		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			w.WriteHeader(http.StatusOK)
		}))
		defer server.Close()

		client := NewClient(server.URL, "")
		err := client.HealthCheck()
		assert.NoError(t, err)
	})

	t.Run("unhealthy server", func(t *testing.T) {
		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			w.WriteHeader(http.StatusInternalServerError)
		}))
		defer server.Close()

		client := NewClient(server.URL, "")
		err := client.HealthCheck()
		assert.Error(t, err)
	})
}