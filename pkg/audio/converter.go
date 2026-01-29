package audio

import (
	"context"
	"crypto/sha256"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/paruff/Media-Refinery/pkg/state"
	"go.uber.org/zap"
)

// Config holds converter configuration
// See .github/copilot-instructions.md for project standards
// All operations must be idempotent, support dry-run, and wrap errors with context
// Context must be passed to all operations
// Logging must use structured zap logger
//
type Config struct {
	InputDir         string
	OutputDir        string
	Format           string // "flac", "mp3", etc.
	PreserveMetadata bool
	CompressionLevel int // FLAC: 0-8, higher = better compression
	DryRun           bool
	StateDir         string // Directory for state files
}

// Result holds conversion result
// ...existing code...

type Converter struct {
	logger   *zap.Logger
	config   Config
	stateMgr *state.Manager
}

// NewConverter creates a new audio converter
func NewConverter(config Config) *Converter {
	mgr := state.NewManager(config.StateDir)
	return &Converter{
		logger:   zap.L(),
		config:   config,
		stateMgr: mgr,
	}
}