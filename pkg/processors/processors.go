package processors

import (
	"fmt"
	"path/filepath"
	"strings"

	"github.com/paruff/media-refinery/pkg/logger"
	"github.com/paruff/media-refinery/pkg/metadata"
	"github.com/paruff/media-refinery/pkg/storage"
	"github.com/paruff/media-refinery/pkg/validator"
)

// Processor is the interface for media processors
type Processor interface {
	// Process processes a single file
	Process(input string, output string) error
	
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
func (p *AudioProcessor) Process(input, output string) error {
	p.ctx.Logger.Info("Processing audio: %s -> %s", input, output)
	
	// Validate input
	fileInfo, err := p.ctx.Validator.ValidateFile(input)
	if err != nil {
		return fmt.Errorf("validation failed: %w", err)
	}
	
	if fileInfo.Type != validator.AudioType {
		return fmt.Errorf("not an audio file")
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
			return p.ctx.Storage.Copy(input, output)
		}
		return nil
	}
	
	// In a real implementation, this would use ffmpeg or similar
	// For now, we'll simulate the conversion
	p.ctx.Logger.Info("Converting %s to %s (format: %s, quality: %s)", 
		input, output, p.outputFormat, p.outputQuality)
	
	if p.ctx.DryRun {
		p.ctx.Logger.Info("[DRY-RUN] Would convert: %s", input)
		return nil
	}
	
	// Simulate conversion by copying (in real implementation, use ffmpeg)
	if err := p.ctx.Storage.Copy(input, output); err != nil {
		return fmt.Errorf("conversion failed: %w", err)
	}
	
	// Update metadata on output file
	if err := p.ctx.Metadata.UpdateMetadata(output, meta); err != nil {
		p.ctx.Logger.Warn("Failed to update metadata: %v", err)
	}
	
	p.ctx.Logger.IncCounter("audio.processed")
	
	return nil
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
func (p *VideoProcessor) Process(input, output string) error {
	p.ctx.Logger.Info("Processing video: %s -> %s", input, output)
	
	// Validate input
	fileInfo, err := p.ctx.Validator.ValidateFile(input)
	if err != nil {
		return fmt.Errorf("validation failed: %w", err)
	}
	
	if fileInfo.Type != validator.VideoType {
		return fmt.Errorf("not a video file")
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
			return p.ctx.Storage.Copy(input, output)
		}
		return nil
	}
	
	// In a real implementation, this would use ffmpeg
	p.ctx.Logger.Info("Converting %s to %s (codec: %s/%s, quality: %s)", 
		input, output, p.videoCodec, p.audioCodec, p.quality)
	
	if p.ctx.DryRun {
		p.ctx.Logger.Info("[DRY-RUN] Would convert: %s", input)
		return nil
	}
	
	// Simulate conversion by copying (in real implementation, use ffmpeg)
	if err := p.ctx.Storage.Copy(input, output); err != nil {
		return fmt.Errorf("conversion failed: %w", err)
	}
	
	// Update metadata on output file
	if err := p.ctx.Metadata.UpdateMetadata(output, meta); err != nil {
		p.ctx.Logger.Warn("Failed to update metadata: %v", err)
	}
	
	p.ctx.Logger.IncCounter("video.processed")
	
	return nil
}

// CanProcess checks if this processor can handle the file
func (p *VideoProcessor) CanProcess(path string) bool {
	return p.ctx.Validator.IsVideoFile(path)
}

// GetOutputExtension returns the output file extension
func (p *VideoProcessor) GetOutputExtension() string {
	return "." + p.outputFormat
}
