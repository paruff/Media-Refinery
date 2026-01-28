//go:build integration
// +build integration

package integration

import (
	"os"
	"testing"

	"github.com/paruff/Media-Refinery/pkg/integrations/beets"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestBeetsIntegration(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode.")
	}

	baseURL := os.Getenv("BEETS_BASE_URL")
	token := os.Getenv("BEETS_TOKEN")
	require.NotEmpty(t, baseURL, "BEETS_BASE_URL must be set")
	require.NotEmpty(t, token, "BEETS_TOKEN must be set")

	client := beets.NewClient(baseURL, token)

	t.Run("HealthCheck", func(t *testing.T) {
		err := client.HealthCheck()
		assert.NoError(t, err)
	})

	t.Run("Query", func(t *testing.T) {
		items, err := client.Query("test")
		assert.NoError(t, err)
		assert.NotEmpty(t, items)
	})
}
