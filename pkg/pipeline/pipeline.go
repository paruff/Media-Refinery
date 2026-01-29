package pipeline

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/paruff/Media-Refinery/pkg/config"
	"github.com/paruff/Media-Refinery/pkg/integrations"
	"github.com/paruff/Media-Refinery/pkg/logger"
	"github.com/paruff/Media-Refinery/pkg/metadata"
	"github.com/paruff/Media-Refinery/pkg/processors"
	"github.com/paruff/Media-Refinery/pkg/storage"
	"github.com/paruff/Media-Refinery/pkg/telemetry"
	"github.com/paruff/Media-Refinery/pkg/validator"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/trace"
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
	telemetry    *telemetry.Provider
}

// NewPipeline creates a new pipeline
func NewPipeline(cfg *config.Config, log *logger.Logger, tel *telemetry.Provider) (*Pipeline, error) {
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
		Telemetry: tel,
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
		telemetry:    tel,
	}, nil
}

// Run executes the pipeline
func (p *Pipeline) Run(ctx context.Context) error {
	// Start overall pipeline span
	if p.telemetry != nil {
		var span trace.Span
		ctx, span = p.telemetry.StartSpan(ctx, "pipeline.run")
		defer span.End()
	}

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

	// Log current working directory
	if cwd, err := os.Getwd(); err == nil {
		p.logger.Info("Current working directory: %s", cwd)
	} else {
		p.logger.Warn("Failed to get current working directory: %v", err)
	}

	// List files in input directory
	entries, err := os.ReadDir(p.config.InputDir)
	if err != nil {
		p.logger.Warn("Failed to list input directory: %v", err)
	} else {
		var names []string
		for _, entry := range entries {
			names = append(names, entry.Name())
		}
		p.logger.Info("Input directory contents: %v", names)
	}

	// Scan input directory
	p.logger.Debug("Scanning directory for media files: directory=%s", p.config.InputDir)
	files, err := p.validator.ScanDirectory(p.config.InputDir)
	if err != nil {
		return fmt.Errorf("failed to scan directory: %w", err)
	}
	p.logger.Debug("Files found during scan: count=%d, files=%v", len(files), files)

	p.logger.Info("Found %d media files", len(files))

	if len(files) == 0 {
		p.logger.Info("No media files found to process")
		return nil
	}

	// Process files
	if err := p.processFiles(ctx, files); err != nil {
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
func (p *Pipeline) processFiles(ctx context.Context, files []*validator.FileInfo) error {
	// Start span for batch processing
	if p.telemetry != nil {
		var span trace.Span
		ctx, span = p.telemetry.StartSpan(ctx, "pipeline.process_files",
			attribute.Int("file.count", len(files)))
		defer span.End()
	}

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
				err := p.processFile(ctx, file)
				results <- err
			}
		}()
	}

	// Send jobs
	for _, file := range files {
		select {
		case <-ctx.Done():
			close(jobs)
			wg.Wait()
			return ctx.Err()
		case jobs <- file:
		}
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
func (p *Pipeline) processFile(ctx context.Context, file *validator.FileInfo) error {
	// Start processing span
	startTime := time.Now()
	var span trace.Span
	if p.telemetry != nil {
		ctx, span = p.telemetry.StartSpan(ctx, "pipeline.process_file",
			attribute.String("file.path", file.Path),
			attribute.String("file.type", strconv.Itoa(int(file.Type))),
			attribute.Int64("file.size", file.Size))
		defer func() {
			duration := time.Since(startTime)
			if p.telemetry != nil {
				p.telemetry.RecordProcessingDuration(ctx, duration, strconv.Itoa(int(file.Type)), span.SpanContext().IsValid())
			}
			span.End()
		}()
	}

	p.logger.Debug("Processing file: file=%s", file.Path)
	p.logger.Debug("File size: size=%d", file.Size)
	p.logger.Debug("File type: type=%d", file.Type)

	// Perform comprehensive integrity check before processing
	p.logger.Info("Validating file integrity: %s", file.Path)
	validationStart := time.Now()
	validatedFile, err := p.validator.ValidateMediaIntegrity(file.Path)
	if err != nil {
		p.logger.Error("File validation failed for %s: %v", file.Path, err)
		if p.telemetry != nil {
			p.telemetry.RecordFileFailed(ctx, strconv.Itoa(int(file.Type)), "validation_failed")
			span.SetStatus(codes.Error, err.Error())
		}
		return fmt.Errorf("validation failed: %w", err)
	}
	file = validatedFile
	if p.telemetry != nil {
		span.AddEvent("file_validated", trace.WithAttributes(
			attribute.Float64("validation.duration_ms", time.Since(validationStart).Seconds()*1000)))
	}

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
		if p.telemetry != nil {
			span.AddEvent("no_processor_found")
		}
		return nil
	}

	// Extract metadata for path formatting (with ffprobe already done during validation)
	p.logger.Debug("Extracting metadata from: %s", file.Path)
	metadataStart := time.Now()
	meta, err := p.metadata.ExtractMetadata(file.Path)
	if err != nil {
		p.logger.Warn("Failed to extract metadata from %s: %v", file.Path, err)
		meta = &metadata.Metadata{Title: "Unknown"}
	}
	if p.telemetry != nil {
		span.AddEvent("metadata_extracted", trace.WithAttributes(
			attribute.Float64("metadata.duration_ms", time.Since(metadataStart).Seconds()*1000),
			attribute.String("metadata.title", meta.Title),
			attribute.String("metadata.artist", meta.Artist)))
	}

	// Try to enrich metadata from integrations
	if p.integrations.HasAnyIntegration() {
		integratedMeta, err := p.integrations.GetMetadata(file.Path, file.Type)
		if err == nil && integratedMeta != nil {
			p.logger.Debug("Enriched metadata from integrations for: %s", file.Path)
			meta = p.metadata.MergeMetadata(meta, integratedMeta)
		} else if err != nil {
			p.logger.Debug("Could not get metadata from integrations: %v", err)
		}
	}

	// Determine output path
	outputPath := p.determineOutputPath(file, meta, proc)

	// Verify checksum if enabled
	if p.config.VerifyChecksums && !p.config.DryRun {
		p.logger.Debug("Computing checksum for: %s", file.Path)
		checksum, err := p.validator.ComputeChecksum(file.Path)
		if err != nil {
			p.logger.Warn("Failed to compute checksum for %s: %v", file.Path, err)
		} else {
			p.logger.Debug("Checksum for %s: %s", file.Path, checksum)
		}
	}

	// Process file
	// Add 30-minute timeout per file
	processCtx, processCancel := context.WithTimeout(ctx, 30*time.Minute)
	defer processCancel()

	processStart := time.Now()
	if err := proc.Process(processCtx, file.Path, outputPath); err != nil {
		p.logger.Error("Failed to process %s: %v", file.Path, err)
		if p.telemetry != nil {
			p.telemetry.RecordFileFailed(ctx, strconv.Itoa(int(file.Type)), "processing_failed")
			span.SetStatus(codes.Error, err.Error())
		}
		return err
	}

	// Record success metrics
	if p.telemetry != nil {
		processDuration := time.Since(processStart)
		format := filepath.Ext(outputPath)
		p.telemetry.RecordFileProcessed(ctx, strconv.Itoa(int(file.Type)), format, file.Size)
		span.AddEvent("file_processed", trace.WithAttributes(
			attribute.Float64("processing.duration_s", processDuration.Seconds())))
		span.SetStatus(codes.Ok, "File processed successfully")
	}

	p.logger.Info("Successfully processed: %s -> %s", file.Path, outputPath)

	return nil
}

// determineOutputPath determines the output path for a file
func (p *Pipeline) determineOutputPath(file *validator.FileInfo, meta *metadata.Metadata, proc processors.Processor) string {
	// Get appropriate pattern
	pattern := ""
	mediaType := ""
	switch file.Type {
	case validator.AudioType:
		pattern = p.config.Organization.MusicPattern
		mediaType = "audio"
	case validator.VideoType:
		if meta.Season != "" || meta.Episode != "" || meta.Show != "" {
			pattern = p.config.Organization.VideoPattern
		} else {
			if meta.Year != "" && meta.Year != "Unknown" {
				pattern = "{title} ({year})/{title}"
			} else {
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
		switch file.Type {
		case validator.AudioType:
			relativePath = filepath.Join("music", relPath)
		case validator.VideoType:
			relativePath = filepath.Join("movies", relPath)
		default:
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
