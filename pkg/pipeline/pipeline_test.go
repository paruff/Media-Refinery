// Corrected import paths to use the proper case for Media-Refinery
package pipeline_test

import (
	"os"
	"testing"

	"github.com/paruff/Media-Refinery/pkg/config"
	"github.com/paruff/Media-Refinery/pkg/logger"
	"github.com/paruff/Media-Refinery/pkg/pipeline"
	"github.com/stretchr/testify/assert"
)

func TestNewPipeline(t *testing.T) {
	t.Run("creates a new pipeline successfully", func(t *testing.T) {
		cfg := config.DefaultConfig()
		log := logger.NewLogger("info", "text", os.Stdout)
		pipe, err := pipeline.NewPipeline(cfg, log, nil)
		assert.NoError(t, err)
		assert.NotNil(t, pipe)
	})
}
