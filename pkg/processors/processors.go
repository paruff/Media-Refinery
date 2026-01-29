package processors

import (
	"context"
	"fmt"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/paruff/Media-Refinery/pkg/logger"
	"github.com/paruff/Media-Refinery/pkg/metadata"
	"github.com/paruff/Media-Refinery/pkg/storage"
	"github.com/paruff/Media-Refinery/pkg/telemetry"
	"github.com/paruff/Media-Refinery/pkg/validator"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/trace"
)

// Processor is the interface for media processors
type Processor interface {
	// Process processes a single file
	Process(ctx context.Context, input string, output string) error

	// CanProcess checks if this processor can handle the file
	CanProcess(path string) bool

	// GetOutputExtension returns the output file extension
	GetOutputExtension() string
}

// ProcessorContext provides context for processing
type ProcessorContext struct {
	Logger    *logger.Logger
	Storage   *storage.Storage
	Validator *validator.Validator
	Metadata  *metadata.MetadataExtractor
	DryRun    bool
	Telemetry *telemetry.Provider
}

// BaseProcessor provides common functionality
type BaseProcessor struct {
	ctx *ProcessorContext
}

// NewBaseProcessor creates a new base processor
func NewBaseProcessor(ctx *ProcessorContext) *BaseProcessor {
	return &BaseProcessor{ctx: ctx}
}

// AudioProcessor processes audio files
type AudioProcessor struct {
	*BaseProcessor
	outputFormat  string
	outputQuality string
	normalize     bool
	bitDepth      int
	sampleRate    int
}

// NewAudioProcessor creates a new audio processor
func NewAudioProcessor(ctx *ProcessorContext, outputFormat, outputQuality string, normalize bool, bitDepth, sampleRate int) *AudioProcessor {
	return &AudioProcessor{
		BaseProcessor: NewBaseProcessor(ctx),
		outputFormat:  outputFormat,
		outputQuality: outputQuality,
		normalize:     normalize,
		bitDepth:      bitDepth,
		sampleRate:    sampleRate,
	}
}

// Process processes an audio file
func (p *AudioProcessor) Process(ctx context.Context, input, output string) error {
	// Start span for audio processing
	startTime := time.Now()
	var span trace.Span
	if p.ctx.Telemetry != nil {
		ctx, span = p.ctx.Telemetry.StartSpan(ctx, "processor.audio.process",
			attribute.String("input.path", input),
			attribute.String("output.path", output),
			attribute.String("output.format", p.outputFormat))
		defer span.End()
	}

	p.ctx.Logger.Info("Processing audio: %s -> %s", input, output)

	// Validate input
	fileInfo, err := p.ctx.Validator.ValidateFile(input)
	if err != nil {
		if p.ctx.Telemetry != nil {
			span.RecordError(err)
		}
		return fmt.Errorf("validation failed: %w", err)
	}

	if fileInfo.Type != validator.AudioType {
		err := fmt.Errorf("not an audio file")
		if p.ctx.Telemetry != nil {
			span.RecordError(err)
		}
		return err
	}

	// Extract metadata
	meta, err := p.ctx.Metadata.ExtractMetadata(input)
	if err != nil {
		p.ctx.Logger.Warn("Failed to extract metadata: %v", err)
		meta = &metadata.Metadata{}
	}

	// Check if conversion is needed
	inputFormat := strings.ToLower(filepath.Ext(input))
	inputFormat = strings.TrimPrefix(inputFormat, ".")

	if inputFormat == p.outputFormat {
		p.ctx.Logger.Info("File already in target format, copying: %s", input)
		if !p.ctx.DryRun {
			if err := p.ctx.Storage.Copy(input, output); err != nil {
				if p.ctx.Telemetry != nil {
					span.RecordError(err)
				}
				return err
			}
		}
		p.ctx.Logger.IncCounter("audio.processed")
		if p.ctx.Telemetry != nil {
			span.AddEvent("file_copied")
		}
		return nil
	}

	// Use ffmpeg for actual conversion
	p.ctx.Logger.Info("Converting %s to %s (format: %s, quality: %s)",
		input, output, p.outputFormat, p.outputQuality)

	if p.ctx.DryRun {
		p.ctx.Logger.Info("[DRY-RUN] Would convert: %s", input)
		p.ctx.Logger.IncCounter("audio.processed")
		return nil
	}

	// Convert using ffmpeg with metadata preservation
	conversionStart := time.Now()
	if err := p.convertWithFFmpeg(ctx, input, output, meta); err != nil {
		if p.ctx.Telemetry != nil {
			p.ctx.Telemetry.RecordFileFailed(ctx, "audio", "conversion_failed")
			span.RecordError(err)
		}
		return fmt.Errorf("conversion failed: %w", err)
	}

	// Record metrics
	if p.ctx.Telemetry != nil {
		conversionDuration := time.Since(conversionStart)
		p.ctx.Telemetry.RecordConversionDuration(ctx, conversionDuration, inputFormat, p.outputFormat)
		span.AddEvent("conversion_complete", trace.WithAttributes(
			attribute.Float64("conversion.duration_s", conversionDuration.Seconds()),
			attribute.Float64("total.duration_s", time.Since(startTime).Seconds())))
	}

	p.ctx.Logger.IncCounter("audio.processed")

	return nil
}

// convertWithFFmpeg converts audio using ffmpeg and preserves metadata
func (p *AudioProcessor) convertWithFFmpeg(ctx context.Context, input, output string, meta *metadata.Metadata) error {
	// Ensure output directory exists
	outputDir := filepath.Dir(output)
	if err := p.ctx.Storage.CreateDir(outputDir); err != nil {
		return err
	}
	// Build ffmpeg command (factored to helper for unit testing)
	args := p.buildFFmpegArgs(input, output, meta)

	// Create command with context for cancellation
	cmd := exec.CommandContext(ctx, "ffmpeg", args...)
	if output, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("ffmpeg failed: %w\nOutput: %s", err, string(output))
	}

	return nil
}

// buildFFmpegArgs constructs the ffmpeg CLI args for the given input/output and metadata.
// This is factored out for unit testing of the argument construction logic.
func (p *AudioProcessor) buildFFmpegArgs(input, output string, meta *metadata.Metadata) []string {
	args := []string{"-i", input}

	switch p.outputFormat {
	case "flac":
		args = append(args, "-c:a", "flac")
		if p.bitDepth > 0 {
			args = append(args, "-sample_fmt", fmt.Sprintf("s%d", p.bitDepth))
		}
	case "mp3":
		args = append(args, "-c:a", "libmp3lame")
		if p.outputQuality == "lossless" {
			args = append(args, "-q:a", "0")
		} else {
			args = append(args, "-b:a", "320k")
		}
	case "aac":
		args = append(args, "-c:a", "aac")
		args = append(args, "-b:a", "256k")
	default:
		args = append(args, "-c:a", "copy")
	}

	if p.sampleRate > 0 {
		args = append(args, "-ar", fmt.Sprintf("%d", p.sampleRate))
	}

	if meta != nil {
		if meta.Title != "" && meta.Title != "Unknown" {
			args = append(args, "-metadata", "title="+meta.Title)
		}
		if meta.Artist != "" && meta.Artist != "Unknown" {
			args = append(args, "-metadata", "artist="+meta.Artist)
		}
		if meta.Album != "" && meta.Album != "Unknown" {
			args = append(args, "-metadata", "album="+meta.Album)
		}
		if meta.AlbumArtist != "" && meta.AlbumArtist != "Unknown" {
			args = append(args, "-metadata", "album_artist="+meta.AlbumArtist)
		}
		if meta.Year != "" && meta.Year != "Unknown" {
			args = append(args, "-metadata", "date="+meta.Year)
		}
		if meta.Genre != "" && meta.Genre != "Unknown" {
			args = append(args, "-metadata", "genre="+meta.Genre)
		}
		if meta.Track != "" && meta.Track != "Unknown" {
			args = append(args, "-metadata", "track="+meta.Track)
		}
		if meta.Composer != "" && meta.Composer != "Unknown" {
			args = append(args, "-metadata", "composer="+meta.Composer)
		}
	}

	args = append(args, "-y", output)
	return args
}

// CanProcess checks if this processor can handle the file
func (p *AudioProcessor) CanProcess(path string) bool {
	return p.ctx.Validator.IsAudioFile(path)
}

// GetOutputExtension returns the output file extension
func (p *AudioProcessor) GetOutputExtension() string {
	return "." + p.outputFormat
}

// VideoProcessor processes video files
type VideoProcessor struct {
	*BaseProcessor
	outputFormat string
	videoCodec   string
	audioCodec   string
	quality      string
	resolution   string
}

// NewVideoProcessor creates a new video processor
func NewVideoProcessor(ctx *ProcessorContext, outputFormat, videoCodec, audioCodec, quality, resolution string) *VideoProcessor {
	return &VideoProcessor{
		BaseProcessor: NewBaseProcessor(ctx),
		outputFormat:  outputFormat,
		videoCodec:    videoCodec,
		audioCodec:    audioCodec,
		quality:       quality,
		resolution:    resolution,
	}
}

// Process processes a video file
func (p *VideoProcessor) Process(ctx context.Context, input, output string) error {
	// Start span for video processing
	startTime := time.Now()
	var span trace.Span
	if p.ctx.Telemetry != nil {
		ctx, span = p.ctx.Telemetry.StartSpan(ctx, "processor.video.process",
			attribute.String("input.path", input),
			attribute.String("output.path", output),
			attribute.String("video.codec", p.videoCodec),
			attribute.String("audio.codec", p.audioCodec))
		defer span.End()
	}

	p.ctx.Logger.Info("Processing video: %s -> %s", input, output)

	// Validate input
	fileInfo, err := p.ctx.Validator.ValidateFile(input)
	if err != nil {
		if p.ctx.Telemetry != nil {
			span.RecordError(err)
		}
		return fmt.Errorf("validation failed: %w", err)
	}

	if fileInfo.Type != validator.VideoType {
		err := fmt.Errorf("not a video file")
		if p.ctx.Telemetry != nil {
			span.RecordError(err)
		}
		return err
	}

	// Extract metadata
	meta, err := p.ctx.Metadata.ExtractMetadata(input)
	if err != nil {
		p.ctx.Logger.Warn("Failed to extract metadata: %v", err)
		meta = &metadata.Metadata{}
	}

	// Check if conversion is needed
	inputFormat := strings.ToLower(filepath.Ext(input))
	inputFormat = strings.TrimPrefix(inputFormat, ".")

	if inputFormat == p.outputFormat {
		p.ctx.Logger.Info("File already in target format, copying: %s", input)
		if !p.ctx.DryRun {
			if err := p.ctx.Storage.Copy(input, output); err != nil {
				if p.ctx.Telemetry != nil {
					span.RecordError(err)
				}
				return err
			}
		}
		p.ctx.Logger.IncCounter("video.processed")
		if p.ctx.Telemetry != nil {
			span.AddEvent("file_copied")
		}
		return nil
	}

	// Use ffmpeg for actual conversion
	p.ctx.Logger.Info("Converting %s to %s (codec: %s/%s, quality: %s)",
		input, output, p.videoCodec, p.audioCodec, p.quality)

	if p.ctx.DryRun {
		p.ctx.Logger.Info("[DRY-RUN] Would convert: %s", input)
		p.ctx.Logger.IncCounter("video.processed")
		return nil
	}

	// Convert using ffmpeg with metadata preservation
	conversionStart := time.Now()
	if err := p.convertWithFFmpeg(ctx, input, output, meta); err != nil {
		if p.ctx.Telemetry != nil {
			p.ctx.Telemetry.RecordFileFailed(ctx, "video", "conversion_failed")
			span.RecordError(err)
		}
		return fmt.Errorf("conversion failed: %w", err)
	}

	// Record metrics
	if p.ctx.Telemetry != nil {
		conversionDuration := time.Since(conversionStart)
		p.ctx.Telemetry.RecordConversionDuration(ctx, conversionDuration, inputFormat, p.outputFormat)
		span.AddEvent("conversion_complete", trace.WithAttributes(
			attribute.Float64("conversion.duration_s", conversionDuration.Seconds()),
			attribute.Float64("total.duration_s", time.Since(startTime).Seconds())))
	}

	p.ctx.Logger.IncCounter("video.processed")

	return nil
}

// convertWithFFmpeg converts video using ffmpeg and preserves metadata
func (p *VideoProcessor) convertWithFFmpeg(ctx context.Context, input, output string, meta *metadata.Metadata) error {
	// Ensure output directory exists
	outputDir := filepath.Dir(output)
	if err := p.ctx.Storage.CreateDir(outputDir); err != nil {
		return err
	}
	// Build ffmpeg command (factored to helper for unit testing)
	args := p.buildFFmpegArgs(input, output, meta)

	// Use the provided context which already has timeout from caller
	cmd := exec.CommandContext(ctx, "ffmpeg", args...)

	// Capture stderr for error messages
	stderr, err := cmd.StderrPipe()
	if err != nil {
		return fmt.Errorf("failed to create stderr pipe: %w", err)
	}

	p.ctx.Logger.Debug("Starting ffmpeg conversion with args: %v", args)

	if err := cmd.Start(); err != nil {
		return fmt.Errorf("failed to start ffmpeg: %w", err)
	}

	// Monitor progress in background
	go func() {
		buf := make([]byte, 1024)
		for {
			n, err := stderr.Read(buf)
			if err != nil {
				break
			}
			if n > 0 {
				output := string(buf[:n])
				// Log progress periodically (every time we see "time=" in output)
				if strings.Contains(output, "time=") {
					p.ctx.Logger.Debug("Conversion progress: %s", strings.TrimSpace(output))
				}
			}
		}
	}()

	// Wait for completion
	if err := cmd.Wait(); err != nil {
		if ctx.Err() == context.DeadlineExceeded {
			return fmt.Errorf("conversion timed out after 30 minutes")
		}
		return fmt.Errorf("ffmpeg conversion failed: %w", err)
	}

	p.ctx.Logger.Debug("Conversion completed successfully")

	return nil
}

// CanProcess checks if this processor can handle the file
func (p *VideoProcessor) CanProcess(path string) bool {
	return p.ctx.Validator.IsVideoFile(path)
}

// buildFFmpegArgs constructs the ffmpeg CLI args for video conversion.
// Factored out for unit testing of argument construction logic.
func (p *VideoProcessor) buildFFmpegArgs(input, output string, meta *metadata.Metadata) []string {
	args := []string{"-i", input, "-progress", "pipe:1", "-nostats"}

	// Add video codec settings
	switch p.videoCodec {
	case "h264":
		args = append(args, "-c:v", "libx264")
		switch p.quality {
		case "high":
			args = append(args, "-preset", "slow", "-crf", "16")
		case "medium":
			args = append(args, "-preset", "medium", "-crf", "20")
		case "low":
			args = append(args, "-preset", "fast", "-crf", "24")
		default:
			args = append(args, "-preset", "medium", "-crf", "20")
		}
	case "h265", "hevc":
		args = append(args, "-c:v", "libx265")
		switch p.quality {
		case "high":
			args = append(args, "-preset", "slow", "-crf", "18")
		case "medium":
			args = append(args, "-preset", "medium", "-crf", "22")
		case "low":
			args = append(args, "-preset", "fast", "-crf", "26")
		default:
			args = append(args, "-preset", "medium", "-crf", "22")
		}
	case "copy":
		args = append(args, "-c:v", "copy")
	default:
		args = append(args, "-c:v", p.videoCodec)
	}

	// Add audio codec settings
	switch p.audioCodec {
	case "aac":
		args = append(args, "-c:a", "aac", "-b:a", "192k")
	case "ac3":
		args = append(args, "-c:a", "ac3", "-b:a", "384k")
	case "opus":
		args = append(args, "-c:a", "libopus", "-b:a", "128k")
	case "copy":
		args = append(args, "-c:a", "copy")
	default:
		args = append(args, "-c:a", p.audioCodec)
	}

	if p.resolution != "" && p.resolution != "keep" {
		args = append(args, "-s", p.resolution)
	}

	if meta != nil {
		if meta.Title != "" && meta.Title != "Unknown" {
			args = append(args, "-metadata", "title="+meta.Title)
		}
		if meta.Show != "" && meta.Show != "Unknown" {
			args = append(args, "-metadata", "show="+meta.Show)
		}
		if meta.Season != "" && meta.Season != "Unknown" {
			args = append(args, "-metadata", "season_number="+meta.Season)
		}
		if meta.Episode != "" && meta.Episode != "Unknown" {
			args = append(args, "-metadata", "episode_sort="+meta.Episode)
		}
		if meta.Year != "" && meta.Year != "Unknown" {
			args = append(args, "-metadata", "date="+meta.Year)
		}
		if meta.Genre != "" && meta.Genre != "Unknown" {
			args = append(args, "-metadata", "genre="+meta.Genre)
		}
		if meta.Director != "" && meta.Director != "Unknown" {
			args = append(args, "-metadata", "director="+meta.Director)
		}
		if meta.Comment != "" && meta.Comment != "Unknown" {
			args = append(args, "-metadata", "comment="+meta.Comment)
		}
	}

	args = append(args, "-y", output)
	return args
}

// GetOutputExtension returns the output file extension
func (p *VideoProcessor) GetOutputExtension() string {
	return "." + p.outputFormat
}
