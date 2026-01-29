package audio
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
}

// Result holds conversion result
//







		logger   *zap.Logger
		config   Config
		stateMgr *state.Manager



		mgr := state.NewManager(config.StateDir)
		return &Converter{
			logger: zap.L(),
			config: config,
			stateMgr: mgr,
		}




























































































































































































}	return filepath.Join(c.config.OutputDir, outputName)	outputName := fmt.Sprintf("%s.%s", nameWithoutExt, c.config.Format)	nameWithoutExt := strings.TrimSuffix(base, ext)	ext := filepath.Ext(base)	base := filepath.Base(inputPath)func (c *Converter) determineOutputPath(inputPath string) string {// determineOutputPath determines output file path}	return fmt.Sprintf("%x", hash.Sum(nil)), nil	}		return "", fmt.Errorf("compute hash: %w", err)	if _, err := io.Copy(hash, file); err != nil {	hash := sha256.New()	defer file.Close()	}		return "", fmt.Errorf("open file: %w", err)	if err != nil {	file, err := os.Open(path)func (c *Converter) calculateChecksum(path string) (string, error) {// calculateChecksum computes SHA256 checksum}	return nil	// TODO: Add format validation using ffprobe	}		return fmt.Errorf("output file is empty")	if info.Size() == 0 {	}		return fmt.Errorf("output file not found: %w", err)	if err != nil {	info, err := os.Stat(path)func (c *Converter) validateOutput(path string) error {// validateOutput validates the output file}	return nil	}		return fmt.Errorf("ffmpeg failed: %w, output: %s", err, string(output))	if err != nil {	output, err := cmd.CombinedOutput()	cmd := exec.CommandContext(ctx, "ffmpeg", args...)func (c *Converter) executeFFmpeg(ctx context.Context, args []string) error {// executeFFmpeg runs the FFmpeg command}	return args, nil	args = append(args, output)	}		args = append(args, "-map_metadata", "0")	if c.config.PreserveMetadata {	}		args = append(args, "-compression_level", fmt.Sprintf("%d", c.config.CompressionLevel))	if c.config.Format == "flac" {	args := []string{"-i", input, "-c:a", c.config.Format}	}		return nil, fmt.Errorf("output path is empty")	if output == "" {	}		return nil, fmt.Errorf("input path is empty")	if input == "" {func (c *Converter) BuildFFmpegCommand(input, output string) ([]string, error) {// BuildFFmpegCommand builds the FFmpeg command arguments}	return nil	// TODO: Add format validation using ffprobe	defer file.Close()	}		return fmt.Errorf("file not readable: %w", err)	if err != nil {	file, err := os.Open(path)	}		return fmt.Errorf("file is empty: %s", path)	if info.Size() == 0 {	}		return fmt.Errorf("stat file: %w", err)		}			return fmt.Errorf("file not found: %s", path)		if os.IsNotExist(err) {	if err != nil {	info, err := os.Stat(path)func (c *Converter) ValidateInputFile(path string) error {// ValidateInputFile checks if input file is valid and readable}	}, nil		Duration:   dur,		Success:    true,		Checksum:   checksum,		Format:     c.config.Format,		OutputPath: outputPath,		InputPath:  inputPath,	return &Result{	)		zap.Duration("duration", dur),		zap.String("output", outputPath),	c.logger.Info("conversion complete",	dur := time.Since(start)	}		}, fmt.Errorf("checksum failed: %w", err)			Duration:   time.Since(start),			Success:    false,			Format:     c.config.Format,			OutputPath: outputPath,			InputPath:  inputPath,		return &Result{		c.logger.Error("checksum failed", zap.Error(err), zap.String("output", outputPath))	if err != nil {	checksum, err := c.calculateChecksum(outputPath)	// 7. Calculate checksum	}		}, fmt.Errorf("output validation failed: %w", err)			Duration:   time.Since(start),			Success:    false,			Format:     c.config.Format,			OutputPath: outputPath,			InputPath:  inputPath,		return &Result{		c.logger.Error("output validation failed", zap.Error(err), zap.String("output", outputPath))	if err := c.validateOutput(outputPath); err != nil {	// 6. Validate output file	}		}, fmt.Errorf("conversion failed: %w", err)			Duration:   time.Since(start),			Success:    false,			Format:     c.config.Format,			OutputPath: outputPath,			InputPath:  inputPath,		return &Result{		c.logger.Error("ffmpeg failed", zap.Error(err), zap.Strings("args", args))	if err := c.executeFFmpeg(ctx, args); err != nil {	// 5. Execute FFmpeg	}		}, nil			Duration:   time.Since(start),			Success:    true,			Format:     c.config.Format,			OutputPath: outputPath,			InputPath:  inputPath,		return &Result{		c.logger.Info("dry-run: would execute ffmpeg", zap.Strings("args", args))	if c.config.DryRun {	// 4. Dry-run support	}		return nil, fmt.Errorf("build command: %w", err)	if err != nil {	args, err := c.BuildFFmpegCommand(inputPath, outputPath)	// 3. Build FFmpeg command	outputPath := c.determineOutputPath(inputPath)	// 2. Determine output path	}		return nil, fmt.Errorf("Invalid audio file '%s': %w", filepath.Base(inputPath), err)	if err := c.ValidateInputFile(inputPath); err != nil {	// 1. Validate input file	start := time.Now()	)		zap.String("format", c.config.Format),		zap.String("input", inputPath),	c.logger.Info("starting conversion",func (c *Converter) ConvertFile(ctx context.Context, inputPath string) (*Result, error) {// ConvertFile converts a single audio file to the configured format}	}		logger: zap.L(), // Use global logger or inject		config: config,	return &Converter{	}		config.Format = "flac"	if config.Format == "" {	}		config.CompressionLevel = 5	if config.CompressionLevel == 0 {func NewConverter(config Config) *Converter {// NewConverter creates a new audio converter}	logger *zap.Logger	config Configtype Converter struct {//// Converter handles audio file conversion}	Duration   time.Duration	Success    bool	Checksum   string	Format     string	OutputPath string	InputPath  stringtype Result struct {