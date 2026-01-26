# Media Refinery

A production-grade media normalization pipeline that transforms chaotic legacy libraries into pristine, metadata-rich archives optimized for Plex and Music Assistant.

## Features

### Core Capabilities
- **Idempotent Processing**: Safe to run multiple times on the same data
- **Verifiable Operations**: Checksum validation and operation tracking
- **Safe by Default**: Dry-run mode, transaction-like operations with rollback
- **Observable**: Structured logging with counters and metrics
- **Third-Party Integrations**: Leverages beets, Tdarr, Radarr, and Sonarr APIs

### Media Support
- **Audio**: MP3, FLAC, AAC, M4A, OGG, WAV → FLAC (configurable)
- **Video**: AVI, MP4, MKV, MOV, WMV, FLV → MKV/H264/AAC (configurable)

### Professional Integrations
- **Beets**: Music library management and authoritative metadata
- **Tdarr**: Automated transcoding with quality profiles
- **Radarr**: Movie organization with TMDB metadata
- **Sonarr**: TV show organization with TVDB metadata

### Processing Pipeline
- Metadata extraction and cleanup
- Format normalization to canonical formats
- Consistent folder structures and naming conventions
- Concurrent processing with configurable workers
- Progress tracking and error recovery

## Quick Start

### Docker Installation (Recommended)

For the complete experience with all integrations:

```bash
# Clone and setup
git clone https://github.com/paruff/media-refinery.git
cd media-refinery

# Create configuration
cp config.example.yaml config.yaml

# Edit config.yaml and add your API keys (see DOCKER.md)

# Start all services
docker-compose up -d

# Process media
docker-compose run --rm media-refinery -config /app/config.yaml
```

See [DOCKER.md](DOCKER.md) for detailed Docker setup instructions.

### Standalone Installation

Without Docker:

```bash
# Build from source
go build -o media-refinery ./cmd/refinery

# Or install directly
go install github.com/paruff/media-refinery/cmd/refinery@latest
```

### Basic Usage

1. Generate a default configuration:
```bash
./media-refinery -init
```

2. Edit `config.yaml` to customize settings

3. Run a dry-run to preview operations:
```bash
./media-refinery -config config.yaml -dry-run
```

4. Process your media:
```bash
./media-refinery -config config.yaml
```

### Command-Line Options

```bash
media-refinery [options]

Options:
  -config string       Path to configuration file
  -input string        Input directory containing media files
  -output string       Output directory for processed files
  -dry-run            Perform a dry run without modifying files
  -init               Generate a default configuration file
  -version            Show version information
  -log-level string   Log level (debug, info, warn, error)
  -concurrency int    Number of concurrent workers
```

## Configuration

The configuration file uses YAML format. Here's a comprehensive example:

```yaml
# Directory settings
input_dir: ./input
output_dir: ./output
work_dir: ./work

# Safety settings
dry_run: false
verify_checksums: true

# Processing settings
concurrency: 4
chunk_size: 100

# Audio processing
audio:
  enabled: true
  output_format: flac
  output_quality: lossless
  supported_types:
    - mp3
    - flac
    - aac
    - m4a
    - ogg
    - wav
  normalize: true
  bit_depth: 16
  sample_rate: 44100

# Video processing
video:
  enabled: true
  output_format: mkv
  video_codec: h264
  audio_codec: aac
  supported_types:
    - avi
    - mp4
    - mkv
    - mov
    - wmv
    - flv
  quality: high
  resolution: keep

# Metadata settings
metadata:
  fetch_online: false
  sources:
    - local
  embed_artwork: true
  cleanup_tags: true

# Organization settings
organization:
  music_pattern: "{artist}/{album}/{track} - {title}"
  video_pattern: "{type}/{title} ({year})/Season {season}/{title} - S{season}E{episode}"
  use_symlinks: false

# Logging settings
logging:
  level: info
  format: text
  output_file: ""

# Third-party integrations
integrations:
  # Beets - Music metadata and library management
  beets:
    enabled: false
    url: http://localhost:8337
    token: ""
  
  # Tdarr - Automated transcoding
  tdarr:
    enabled: false
    url: http://localhost:8265
    api_key: ""
    library_id: ""
  
  # Radarr - Movie metadata and organization
  radarr:
    enabled: false
    url: http://localhost:7878
    api_key: ""
  
  # Sonarr - TV show metadata and organization
  sonarr:
    enabled: false
    url: http://localhost:8989
    api_key: ""
```

## Architecture

### Package Structure

```
media-refinery/
├── cmd/
│   └── refinery/           # Main application entry point
└── pkg/
    ├── config/             # Configuration management
    ├── logger/             # Structured logging and observability
    ├── validator/          # File validation and checksums
    ├── metadata/           # Metadata extraction and formatting
    ├── storage/            # Safe file operations with rollback
    ├── processors/         # Audio and video processors
    ├── pipeline/           # Main orchestration pipeline
    └── integrations/       # Third-party API clients
        ├── beets/          # Beets music library client
        ├── tdarr/          # Tdarr transcoding client
        ├── radarr/         # Radarr movie client
        └── sonarr/         # Sonarr TV show client
```

### Design Principles

1. **Idempotency**: Running the same operation multiple times produces the same result
2. **Safety**: All operations can be verified before execution (dry-run mode)
3. **Observability**: Detailed logging with counters for monitoring
4. **Extensibility**: Plugin-like processor architecture for easy extension
5. **Resilience**: Transaction-like operations with rollback capability

## Plex & Music Assistant Optimization

### Music Organization
The default music pattern organizes files for optimal Plex scanning:
```
{artist}/{album}/{track} - {title}
```

Example output:
```
output/
└── The Beatles/
    └── Abbey Road/
        ├── 01 - Come Together.flac
        ├── 02 - Something.flac
        └── ...
```

### Video Organization
The default video pattern supports both movies and TV shows:
```
{type}/{title} ({year})/Season {season}/{title} - S{season}E{episode}
```

Example output:
```
output/
└── TV Shows/
    └── Breaking Bad (2008)/
        └── Season 1/
            ├── Breaking Bad - S01E01.mkv
            ├── Breaking Bad - S01E02.mkv
            └── ...
```

## Processing Pipeline Flow

1. **Scan**: Discover all media files in input directory
2. **Validate**: Check file types and compute checksums
3. **Extract**: Pull metadata from files and filenames
4. **Process**: Convert to canonical formats (FLAC, MKV/H264/AAC)
5. **Organize**: Apply naming conventions and folder structure
6. **Verify**: Confirm successful processing
7. **Report**: Log statistics and any errors

## Safety Features

### Dry-Run Mode
Preview all operations without modifying files:
```bash
./media-refinery -dry-run
```

### Checksum Verification
Verify file integrity before and after processing:
```yaml
verify_checksums: true
```

### Operation Rollback
If processing fails, rollback completed operations:
```go
if err := pipe.Run(); err != nil {
    pipe.Rollback()
}
```

## Performance

- **Concurrent Processing**: Configurable worker pool for parallel operations
- **Efficient I/O**: Streaming operations for large files
- **Resource Management**: Bounded memory usage with chunked processing

## Observability

### Logging
Structured logging with multiple formats:
- Text format for human readability
- JSON format for log aggregation

### Metrics
Built-in counters for monitoring:
- Files processed by type
- Success/failure rates
- Operation counts

### Example Log Output
```
[2024-01-26 14:48:00] INFO: Starting media refinery pipeline
[2024-01-26 14:48:00] INFO: Input directory: ./input
[2024-01-26 14:48:00] INFO: Output directory: ./output
[2024-01-26 14:48:01] INFO: Found 150 media files
[2024-01-26 14:48:45] INFO: Processing completed
[2024-01-26 14:48:45] INFO: === Processing Statistics ===
[2024-01-26 14:48:45] INFO: Audio files processed: 120
[2024-01-26 14:48:45] INFO: Video files processed: 30
```

## Extending the Pipeline

### Adding a New Processor

Implement the `Processor` interface:

```go
type CustomProcessor struct {
    *BaseProcessor
}

func (p *CustomProcessor) Process(input, output string) error {
    // Your processing logic
    return nil
}

func (p *CustomProcessor) CanProcess(path string) bool {
    // Check if this processor can handle the file
    return true
}

func (p *CustomProcessor) GetOutputExtension() string {
    return ".custom"
}
```

### Adding Metadata Sources

Extend the `MetadataExtractor` to fetch from online sources:

```go
// Implement fetching from MusicBrainz, TMDB, etc.
func (e *MetadataExtractor) FetchOnlineMetadata(file string) (*Metadata, error) {
    // Your API calls here
    return &Metadata{}, nil
}
```

## Requirements

- Go 1.21 or later
- For actual media processing (not just simulation):
  - FFmpeg for audio/video conversion
  - taglib for metadata manipulation

## Future Enhancements

- Integration with FFmpeg for actual format conversion
- Online metadata fetching (MusicBrainz, TMDB, TVDB)
- Resume capability for interrupted processing
- Web UI for monitoring and configuration
- Docker container support
- Batch processing with job queues
- Support for more exotic formats

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

See LICENSE file for details.

## Acknowledgments

Built with a focus on production-grade reliability, observability, and safety for managing precious media archives.