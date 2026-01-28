# Media Refinery

Media Refinery is a robust media normalization pipeline designed for transforming unorganized libraries into well-structured, metadata-rich archives. It optimizes your media collections for platforms such as Plex and Music Assistant, providing idempotent, verifiable, and highly configurable operations.

---

## 🚀 Features

### Core Capabilities:
- **Idempotent Processing**: Runs safely multiple times without duplication or errors.
- **Comprehensive Verification**: Secure checksum validation and robust tracking of all operations.
- **Fail-Safe Operations**: Includes a dry-run mode and supports automatic rollback.
- **Observability**: Intuitive, structured logging with built-in counters.

### Supported Media Formats:
- **Audio**: Transforms MP3, FLAC, AAC, M4A, OGG, WAV → FLAC.
- **Video**: Converts AVI, MP4, MKV, MOV, WMV, FLV → MKV/H.264/AAC.

### Professional-grade Integrations:
- **Beets**: Automates music library cleanup with MusicBrainz metadata integration.
- **Tdarr**: Enables transcoding with powerful quality profiles and hardware acceleration.
- **Radarr**: Simplifies movie organization using TMDB metadata.
- **Sonarr**: Streamlines TV show management with TVDB metadata.

---

## 📒 Table of Contents
- [Quick Start](#-quick-start)
- [Usage Examples](#-usage-examples)
- [Configuration](#-configuration)
- [Contribution Guide](#-contribution-guide)

---

## ⚡ Quick Start

### Option 1: Docker Installation (Recommended)
```bash
# Clone the repository
git clone https://github.com/paruff/media-refinery.git
cd media-refinery

# Copy an example config file and edit it to include API keys
cp config.example.yaml config.yaml

# Start Media Refinery as a Docker service
docker-compose up -d

docker-compose run --rm media-refinery -config /app/config.yaml
```

### Option 2: Standalone Installation
```bash
# Build from source
go build -o media-refinery ./cmd/refinery

# OR install directly using Go Modules
go install github.com/paruff/media-refinery/cmd/refinery@latest

# Run the application
./media-refinery -init -config config.yaml
```
For specifics, check [DOCKER.md](./DOCKER.md).

---

## 🌟 Usage Examples
```bash
# Generate the default configuration
./media-refinery -init

# Run Media Refinery in dry-run mode
./media-refinery -config config.yaml -dry-run

# Apply changes to the library
./media-refinery -config config.yaml
```

#### Command Line Reference:
```bash
media-refinery [options]

Options:
  -config string       Path to configuration file
  -input string        Input directory containing media files
  -output string       Output directory for processed files
  -dry-run             Perform a dry run without modifying files
  -init                Generate a default configuration file
  -version             Show version information
  -log-level string    Log level (debug, info, warn, error)
```

---

## ⚙ Configuration

Media Refinery uses YAML files to define settings for its workflows. Below is a minimal example configuration:

```yaml
input_dir: ./input
output_dir: ./output
work_dir: ./work

dry_run: false
verify_checksums: true

# Specify concurrency and chunk sizes as needed
concurrency: 4
chunk_size: 100

# Enable/Disable specific processing options
audio:
  enabled: true
  output_format: flac

video:
  enabled: true
  output_format: mkv
  video_codec: h264
```
Refer to `config.example.yaml` for a comprehensive overview of available configurations.

---

## 🌟 Contribution Guide

We welcome your contributions to Media Refinery! Here’s how you can get started:

1. **Fork the Repository:**
   - Create your feature branch using `git checkout -b feature/my-feature`.

2. **Run Tests Locally:**
   ```bash
   make test  # Run unit tests
   make test-coverage  # Generate a test coverage report
   ```

3. **Submit a Pull Request:**
   - Open a pull request with a clear description of your changes.

### 🛠 Tools & Frameworks
- **Language:** Go (`>1.21 required`)
- **Testing Frameworks:** Go’s built-in `testing` and custom integration tests.
- **Dependencies:** Managed via Go Modules.

---

## 🛡 License

See the [LICENSE](./LICENSE) file for license rights and limitations.
