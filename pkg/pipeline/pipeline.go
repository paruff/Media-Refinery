package pipeline

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"

	"github.com/paruff/media-refinery/pkg/config"
	"github.com/paruff/media-refinery/pkg/integrations"
	"github.com/paruff/media-refinery/pkg/logger"
	"github.com/paruff/media-refinery/pkg/metadata"
	"github.com/paruff/media-refinery/pkg/processors"
	"github.com/paruff/media-refinery/pkg/storage"
	"github.com/paruff/media-refinery/pkg/validator"
)

// Pipeline orchestrates the media processing workflow
type Pipeline struct {
	config       *config.Config
	logger       *logger.Logger
	validator    *validator.Validator
	storage      *storage.Storage
	metadata     *metadata.MetadataExtractor
	processors   []processors.Processor
	integrations *integrations.Manager
}

// NewPipeline creates a new pipeline
func NewPipeline(cfg *config.Config, log *logger.Logger) (*Pipeline, error) {
	// Create validator
	val := validator.NewValidator(
		cfg.Audio.SupportedTypes,
		cfg.Video.SupportedTypes,
	)
	
	// Create storage manager
	stor := storage.NewStorage(cfg.WorkDir, cfg.DryRun)
	
	// Create metadata extractor
	meta := metadata.NewMetadataExtractor(cfg.Metadata.CleanupTags)
	
	// Create integration manager
	integ := integrations.NewManager(cfg, log)
	
	// Create processor context
	ctx := &processors.ProcessorContext{
		Logger:    log,
		Storage:   stor,
		Validator: val,
		Metadata:  meta,
		DryRun:    cfg.DryRun,
	}
	
	// Create processors
	var procs []processors.Processor
	
	if cfg.Audio.Enabled {
		audioProc := processors.NewAudioProcessor(
			ctx,
			cfg.Audio.OutputFormat,
			cfg.Audio.OutputQuality,
			cfg.Audio.Normalize,
			cfg.Audio.BitDepth,
			cfg.Audio.SampleRate,
		)
		procs = append(procs, audioProc)
	}
	
	if cfg.Video.Enabled {
		videoProc := processors.NewVideoProcessor(
			ctx,
			cfg.Video.OutputFormat,
			cfg.Video.VideoCodec,
			cfg.Video.AudioCodec,
			cfg.Video.Quality,
			cfg.Video.Resolution,
		)
		procs = append(procs, videoProc)
	}
	
	return &Pipeline{
		config:       cfg,
		logger:       log,
		validator:    val,
		storage:      stor,
		metadata:     meta,
		processors:   procs,
		integrations: integ,
	}, nil
}

// Run executes the pipeline
func (p *Pipeline) Run() error {
	p.logger.Info("Starting media refinery pipeline")
	p.logger.Info("Input directory: %s", p.config.InputDir)
	p.logger.Info("Output directory: %s", p.config.OutputDir)
	
	if p.config.DryRun {
		p.logger.Info("DRY-RUN mode enabled - no files will be modified")
	}
	
	// Health check integrations
	if p.integrations.HasAnyIntegration() {
		p.logger.Info("Performing integration health checks...")
		if err := p.integrations.HealthCheck(); err != nil {
			p.logger.Warn("Integration health check failed: %v", err)
			p.logger.Warn("Continuing without integrations...")
		}
	}
	
	// Ensure directories exist
	if err := p.ensureDirectories(); err != nil {
		return fmt.Errorf("failed to ensure directories: %w", err)
	}
	
	// Scan input directory
	p.logger.Info("Scanning input directory...")
	files, err := p.validator.ScanDirectory(p.config.InputDir)
	if err != nil {
		return fmt.Errorf("failed to scan directory: %w", err)
	}
	
	p.logger.Info("Found %d media files", len(files))
	
	if len(files) == 0 {
		p.logger.Info("No media files found to process")
		return nil
	}
	
	// Process files
	if err := p.processFiles(files); err != nil {
		return fmt.Errorf("processing failed: %w", err)
	}
	
	// Print statistics
	p.printStatistics()
	
	p.logger.Info("Pipeline completed successfully")
	
	return nil
}

// ensureDirectories ensures required directories exist
func (p *Pipeline) ensureDirectories() error {
	dirs := []string{
		p.config.OutputDir,
		p.config.WorkDir,
	}
	
	for _, dir := range dirs {
		if err := os.MkdirAll(dir, 0755); err != nil {
			return fmt.Errorf("failed to create directory %s: %w", dir, err)
		}
	}
	
	return nil
}

// processFiles processes a list of files
func (p *Pipeline) processFiles(files []*validator.FileInfo) error {
	// Create worker pool
	concurrency := p.config.Concurrency
	if concurrency < 1 {
		concurrency = 1
	}
	
	jobs := make(chan *validator.FileInfo, len(files))
	results := make(chan error, len(files))
	
	var wg sync.WaitGroup
	
	// Start workers
	for i := 0; i < concurrency; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for file := range jobs {
				err := p.processFile(file)
				results <- err
			}
		}()
	}
	
	// Send jobs
	for _, file := range files {
		jobs <- file
	}
	close(jobs)
	
	// Wait for completion
	wg.Wait()
	close(results)
	
	// Collect errors
	var errors []error
	for err := range results {
		if err != nil {
			errors = append(errors, err)
		}
	}
	
	if len(errors) > 0 {
		p.logger.Error("Processing completed with %d errors", len(errors))
		for i, err := range errors {
			if i < 10 { // Show first 10 errors
				p.logger.Error("  - %v", err)
			}
		}
		if len(errors) > 10 {
			p.logger.Error("  ... and %d more errors", len(errors)-10)
		}
	}
	
	return nil
}

// processFile processes a single file
func (p *Pipeline) processFile(file *validator.FileInfo) error {
	p.logger.Debug("Processing: %s", file.Path)
	
	// Find appropriate processor
	var proc processors.Processor
	for _, processor := range p.processors {
		if processor.CanProcess(file.Path) {
			proc = processor
			break
		}
	}
	
	if proc == nil {
		p.logger.Warn("No processor found for: %s", file.Path)
		return nil
	}
	
	// Extract metadata for path formatting
	meta, err := p.metadata.ExtractMetadata(file.Path)
	if err != nil {
		p.logger.Warn("Failed to extract metadata from %s: %v", file.Path, err)
		meta = &metadata.Metadata{Title: "Unknown"}
	}
	
	// Try to enrich metadata from integrations
	if p.integrations.HasAnyIntegration() {
		integratedMeta, err := p.integrations.GetMetadata(file.Path, file.Type)
		if err == nil && integratedMeta != nil {
			p.logger.Info("Enriched metadata from integrations for: %s", file.Path)
			meta = p.metadata.MergeMetadata(meta, integratedMeta)
		}
	}
	
	// Determine output path
	outputPath := p.determineOutputPath(file, meta, proc)
	
	// Verify checksum if enabled
	if p.config.VerifyChecksums && !p.config.DryRun {
		checksum, err := p.validator.ComputeChecksum(file.Path)
		if err != nil {
			p.logger.Warn("Failed to compute checksum for %s: %v", file.Path, err)
		} else {
			p.logger.Debug("Checksum for %s: %s", file.Path, checksum)
		}
	}
	
	// Process file
	if err := proc.Process(file.Path, outputPath); err != nil {
		p.logger.Error("Failed to process %s: %v", file.Path, err)
		return err
	}
	
	p.logger.Info("Successfully processed: %s -> %s", file.Path, outputPath)
	
	return nil
}

// determineOutputPath determines the output path for a file
func (p *Pipeline) determineOutputPath(file *validator.FileInfo, meta *metadata.Metadata, proc processors.Processor) string {
	// Get appropriate pattern
	pattern := ""
	mediaType := ""
	if file.Type == validator.AudioType {
		pattern = p.config.Organization.MusicPattern
		mediaType = "audio"
	} else if file.Type == validator.VideoType {
		// Determine if it's a movie or series
		if meta.Season != "" || meta.Episode != "" || meta.Show != "" {
			// It's a TV series
			pattern = p.config.Organization.VideoPattern
		} else {
			// It's a movie - use pattern based on whether we have a year
			if meta.Year != "" && meta.Year != "Unknown" {
				pattern = "{title} ({year})/{title}"
			} else {
				// No year, just use title
				pattern = "{title}/{title}"
			}
		}
		mediaType = "video"
	}
	
	// Format path using metadata
	var relativePath string
	if pattern != "" && meta.Title != "" && meta.Title != "Unknown" {
		relativePath = p.metadata.FormatPath(meta, pattern, mediaType)
	} else {
		// Fallback to preserving directory structure with type prefix
		relPath, err := filepath.Rel(p.config.InputDir, file.Path)
		if err != nil {
			relPath = filepath.Base(file.Path)
		}
		// Add type prefix
		if file.Type == validator.AudioType {
			relativePath = filepath.Join("music", relPath)
		} else if file.Type == validator.VideoType {
			relativePath = filepath.Join("movies", relPath)
		} else {
			relativePath = relPath
		}
	}
	
	// Change extension if needed
	ext := proc.GetOutputExtension()
	if ext != "" {
		relativePath = strings.TrimSuffix(relativePath, filepath.Ext(relativePath)) + ext
	}
	
	return filepath.Join(p.config.OutputDir, relativePath)
}

// printStatistics prints processing statistics
func (p *Pipeline) printStatistics() {
	counters := p.logger.GetCounters()
	
	p.logger.Info("=== Processing Statistics ===")
	
	if audioCount, ok := counters["audio.processed"]; ok {
		p.logger.Info("Audio files processed: %d", audioCount)
	}
	
	if videoCount, ok := counters["video.processed"]; ok {
		p.logger.Info("Video files processed: %d", videoCount)
	}
	
	if p.storage.IsDryRun() {
		ops := p.storage.GetOperations()
		p.logger.Info("Operations that would be performed: %d", len(ops))
	}
}

// Rollback attempts to rollback the pipeline operations
func (p *Pipeline) Rollback() error {
	p.logger.Warn("Rolling back pipeline operations...")
	return p.storage.Rollback()
}
