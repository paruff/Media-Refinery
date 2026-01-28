# Copilot Instructions for Media-Refinery

## Project Overview

Media-Refinery is a robust media normalization pipeline built with Go and Docker, designed to transform unorganized media libraries into well-structured, metadata-rich archives. This document provides guidance for AI coding assistants (GitHub Copilot, Cursor, etc.) to maintain consistency, quality, and best practices.

## Core Principles

### 1. Idempotency & Safety
- **All operations MUST be idempotent**: Running the same operation multiple times should produce the same result without side effects
- **Always implement dry-run mode**: Every file operation should support a preview mode
- **Implement atomic operations**: Use rename operations instead of in-place modifications
- **Rollback capability**: Track all changes to enable rollback on failure
- **Checksum verification**: Validate file integrity before and after operations

### 2. Go Best Practices

#### Code Structure
```go
// Package organization follows Go standards
// pkg/       - Reusable library code
// cmd/       - Application entry points
// internal/  - Private application code
// test/      - Integration and end-to-end tests
```

#### Error Handling
```go
// ALWAYS wrap errors with context
if err != nil {
    return fmt.Errorf("failed to process file %s: %w", filename, err)
}

// Use structured logging with context
logger.Error("operation failed",
    "file", filename,
    "operation", "transcode",
    "error", err,
)

// Never ignore errors - handle or explicitly document why ignoring
// AVOID: _ = someOperation()
// PREFER: 
if err := someOperation(); err != nil {
    logger.Warn("non-critical operation failed", "error", err)
}
```

#### Context Management
```go
// Always accept context.Context as first parameter
func ProcessMedia(ctx context.Context, path string, opts Options) error {
    // Check context cancellation
    select {
    case <-ctx.Done():
        return ctx.Err()
    default:
    }
    
    // Pass context to all downstream calls
    return processWithTimeout(ctx, path, opts)
}

// Use context for timeouts and cancellation
ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
defer cancel()
```

#### Concurrency Patterns
```go
// Use worker pools with proper error handling
type Result struct {
    File string
    Err  error
}

func processFiles(ctx context.Context, files []string, workers int) error {
    var wg sync.WaitGroup
    fileChan := make(chan string, len(files))
    resultChan := make(chan Result, len(files))
    
    // Start workers
    for i := 0; i < workers; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            for file := range fileChan {
                select {
                case <-ctx.Done():
                    return
                case resultChan <- processFile(ctx, file):
                }
            }
        }()
    }
    
    // Send work
    go func() {
        for _, file := range files {
            select {
            case <-ctx.Done():
                return
            case fileChan <- file:
            }
        }
        close(fileChan)
    }()
    
    // Wait for completion
    go func() {
        wg.Wait()
        close(resultChan)
    }()
    
    // Collect results
    var errors []error
    for result := range resultChan {
        if result.Err != nil {
            errors = append(errors, result.Err)
        }
    }
    
    if len(errors) > 0 {
        return fmt.Errorf("processing failed: %v", errors)
    }
    return nil
}
```

#### Resource Management
```go
// Always use defer for cleanup
func processFile(path string) error {
    f, err := os.Open(path)
    if err != nil {
        return fmt.Errorf("open file: %w", err)
    }
    defer f.Close()
    
    // Use sync.Pool for frequently allocated objects
    var bufferPool = sync.Pool{
        New: func() interface{} {
            return make([]byte, 32*1024)
        },
    }
    
    buf := bufferPool.Get().([]byte)
    defer bufferPool.Put(buf)
    
    return process(f, buf)
}
```

### 3. Docker Best Practices

#### Dockerfile Standards
```dockerfile
# Multi-stage build for minimal image size
FROM golang:1.21-alpine AS builder

# Install build dependencies
RUN apk add --no-cache git make

WORKDIR /build

# Cache dependencies layer
COPY go.mod go.sum ./
RUN go mod download

# Build application
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo \
    -ldflags="-w -s" -o /app/refinery ./cmd/refinery

# Final stage - minimal runtime image
FROM alpine:3.19

# Add non-root user
RUN addgroup -g 1000 refinery && \
    adduser -D -u 1000 -G refinery refinery

# Install runtime dependencies
RUN apk add --no-cache \
    ffmpeg \
    ca-certificates \
    tzdata

WORKDIR /app

# Copy binary from builder
COPY --from=builder /app/refinery .

# Create required directories with proper permissions
RUN mkdir -p /app/work /app/input /app/output && \
    chown -R refinery:refinery /app

USER refinery

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["/app/refinery", "health"]

ENTRYPOINT ["/app/refinery"]
```

#### Docker Compose Patterns
```yaml
version: '3.9'

services:
  refinery:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        - BUILD_VERSION=${VERSION:-dev}
    image: media-refinery:${VERSION:-latest}
    container_name: media-refinery
    
    # Resource limits
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
    
    # Environment configuration
    environment:
      - TZ=${TZ:-UTC}
      - LOG_LEVEL=${LOG_LEVEL:-info}
      - DRY_RUN=${DRY_RUN:-false}
    
    # Volume mounts
    volumes:
      - ./config.yaml:/app/config.yaml:ro
      - ${INPUT_DIR:-./input}:/input:ro
      - ${OUTPUT_DIR:-./output}:/output
      - ${WORK_DIR:-./work}:/work
      - refinery-cache:/app/cache
    
    # Networking
    networks:
      - media-network
    
    # Health check
    healthcheck:
      test: ["CMD", "/app/refinery", "health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    
    # Restart policy
    restart: unless-stopped
    
    # Logging
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

volumes:
  refinery-cache:
    driver: local

networks:
  media-network:
    driver: bridge
```

### 4. Testing Standards

#### Test Structure
```go
// test/integration_test.go
package test

import (
    "context"
    "testing"
    "time"
    
    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/require"
)

// TestProcessMedia_AudioConversion tests audio file conversion
func TestProcessMedia_AudioConversion(t *testing.T) {
    // Arrange
    ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
    defer cancel()
    
    testCases := []struct {
        name        string
        inputFile   string
        wantFormat  string
        wantErr     bool
        errContains string
    }{
        {
            name:       "convert MP3 to FLAC",
            inputFile:  "testdata/audio.mp3",
            wantFormat: "flac",
            wantErr:    false,
        },
        {
            name:        "invalid input file",
            inputFile:   "testdata/nonexistent.mp3",
            wantErr:     true,
            errContains: "file not found",
        },
    }
    
    for _, tc := range testCases {
        t.Run(tc.name, func(t *testing.T) {
            // Act
            result, err := ProcessMedia(ctx, tc.inputFile, defaultOptions)
            
            // Assert
            if tc.wantErr {
                require.Error(t, err)
                if tc.errContains != "" {
                    assert.Contains(t, err.Error(), tc.errContains)
                }
                return
            }
            
            require.NoError(t, err)
            assert.Equal(t, tc.wantFormat, result.Format)
            assert.FileExists(t, result.OutputPath)
        })
    }
}

// Use table-driven tests for comprehensive coverage
func TestChecksumValidation(t *testing.T) {
    tests := []struct {
        name     string
        file     string
        checksum string
        want     bool
    }{
        {"valid SHA256", "test.txt", "abc123...", true},
        {"invalid checksum", "test.txt", "wrong", false},
        {"missing file", "missing.txt", "abc123...", false},
    }
    
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got := ValidateChecksum(tt.file, tt.checksum)
            assert.Equal(t, tt.want, got)
        })
    }
}

// Benchmark critical paths
func BenchmarkProcessMedia(b *testing.B) {
    ctx := context.Background()
    
    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        _ = ProcessMedia(ctx, "testdata/sample.mp3", defaultOptions)
    }
}
```

#### Test Coverage Requirements
- **Minimum 80% code coverage** for all packages
- **100% coverage** for critical paths (file operations, checksums, database operations)
- **Integration tests** for all external dependencies (ffmpeg, beets, API calls)
- **End-to-end tests** for complete workflows

#### Testing Commands
```bash
# Run all tests
make test

# Run tests with coverage
make test-coverage

# Run integration tests only
make test-integration

# Run tests with race detector
go test -race ./...

# Run specific test
go test -v -run TestProcessMedia_AudioConversion ./test/

# Generate coverage report
go test -coverprofile=coverage.out ./...
go tool cover -html=coverage.out -o coverage.html
```

### 5. GitOps Principles

#### Version Control Standards
```yaml
# .gitignore essentials
# Binaries
/media-refinery
*.exe
*.dll
*.so
*.dylib

# Test artifacts
*.test
*.out
coverage.html
coverage.out

# Working directories
/work/
/input/
/output/
*.log

# Configuration (keep examples)
config.yaml
!config.example.yaml

# Dependencies
/vendor/

# IDE
.vscode/
.idea/
*.swp
*.swo
```

#### Commit Message Convention
```
<type>(<scope>): <subject>

<body>

<footer>

Types:
- feat: New feature
- fix: Bug fix
- docs: Documentation changes
- style: Code style changes (formatting)
- refactor: Code refactoring
- test: Test additions/changes
- chore: Build process or auxiliary tool changes
- perf: Performance improvements

Examples:
feat(audio): add FLAC to MP3 conversion support
fix(checksum): handle empty file checksum validation
docs(readme): update installation instructions
test(integration): add audio conversion test suite
```

#### Branch Strategy
```
main          - Production-ready code
├── develop   - Integration branch
    ├── feature/audio-flac-support
    ├── feature/video-transcoding
    ├── fix/checksum-validation
    └── refactor/error-handling
```

#### CI/CD Pipeline (.github/workflows/ci.yml)
```yaml
name: CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

env:
  GO_VERSION: '1.21'

jobs:
  test:
    name: Test
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Set up Go
        uses: actions/setup-go@v4
        with:
          go-version: ${{ env.GO_VERSION }}
      
      - name: Cache Go modules
        uses: actions/cache@v3
        with:
          path: ~/go/pkg/mod
          key: ${{ runner.os }}-go-${{ hashFiles('**/go.sum') }}
          restore-keys: |
            ${{ runner.os }}-go-
      
      - name: Download dependencies
        run: go mod download
      
      - name: Run tests
        run: make test
      
      - name: Run tests with race detector
        run: go test -race ./...
      
      - name: Generate coverage
        run: make test-coverage
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.out
  
  lint:
    name: Lint
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Set up Go
        uses: actions/setup-go@v4
        with:
          go-version: ${{ env.GO_VERSION }}
      
      - name: golangci-lint
        uses: golangci/golangci-lint-action@v3
        with:
          version: latest
          args: --timeout=5m
  
  build:
    name: Build
    runs-on: ubuntu-latest
    needs: [test, lint]
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Build Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: false
          tags: media-refinery:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
      
      - name: Test Docker image
        run: |
          docker run --rm media-refinery:${{ github.sha }} version
          docker run --rm media-refinery:${{ github.sha }} health
  
  integration:
    name: Integration Tests
    runs-on: ubuntu-latest
    needs: build
    
    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Set up Go
        uses: actions/setup-go@v4
        with:
          go-version: ${{ env.GO_VERSION }}
      
      - name: Install FFmpeg
        run: sudo apt-get update && sudo apt-get install -y ffmpeg
      
      - name: Run integration tests
        run: make test-integration
        env:
          DATABASE_URL: postgres://postgres:test@localhost:5432/test
```

### 6. Configuration Management

#### Configuration Structure
```yaml
# config.yaml - Main configuration file
# All paths should be absolute or relative to config file location
version: "1.0"

# Logging configuration
logging:
  level: info  # debug, info, warn, error
  format: json # json, text
  output: stdout # stdout, file
  file_path: /var/log/refinery.log

# Processing settings
processing:
  # Dry run mode - preview changes without applying
  dry_run: false
  
  # Verify checksums before and after operations
  verify_checksums: true
  
  # Number of concurrent workers
  concurrency: 4
  
  # Batch size for file processing
  chunk_size: 100
  
  # Enable automatic rollback on error
  auto_rollback: true

# Directory paths
paths:
  input: /input
  output: /output
  work: /work
  cache: /cache

# Audio processing
audio:
  enabled: true
  output_format: flac
  bitrate: 320k
  sample_rate: 44100
  channels: 2
  preserve_metadata: true
  
  # Supported input formats
  input_formats:
    - mp3
    - aac
    - m4a
    - ogg
    - wav

# Video processing
video:
  enabled: true
  output_format: mkv
  video_codec: h264
  audio_codec: aac
  preset: medium # ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow
  crf: 23 # 0-51, lower = better quality
  
  # Hardware acceleration
  hardware_acceleration:
    enabled: false
    type: none # none, nvidia, intel, amd
  
  # Supported input formats
  input_formats:
    - avi
    - mp4
    - mkv
    - mov
    - wmv
    - flv

# External service integrations
integrations:
  # Beets music library manager
  beets:
    enabled: false
    config_path: /config/beets/config.yaml
    auto_import: true
  
  # Tdarr transcoding
  tdarr:
    enabled: false
    url: http://tdarr:8265
    api_key: ${TDARR_API_KEY}
  
  # Radarr movie management
  radarr:
    enabled: false
    url: http://radarr:7878
    api_key: ${RADARR_API_KEY}
  
  # Sonarr TV show management
  sonarr:
    enabled: false
    url: http://sonarr:8989
    api_key: ${SONARR_API_KEY}

# Database configuration
database:
  type: sqlite # sqlite, postgres
  connection_string: /work/refinery.db
  max_connections: 10
  connection_timeout: 30s

# Monitoring and metrics
monitoring:
  enabled: true
  prometheus_port: 9090
  
  # Health check configuration
  health_check:
    enabled: true
    port: 8080
    path: /health
```

#### Environment Variable Support
```go
// Load configuration with environment variable expansion
func LoadConfig(path string) (*Config, error) {
    data, err := os.ReadFile(path)
    if err != nil {
        return nil, fmt.Errorf("read config: %w", err)
    }
    
    // Expand environment variables
    expanded := os.ExpandEnv(string(data))
    
    var cfg Config
    if err := yaml.Unmarshal([]byte(expanded), &cfg); err != nil {
        return nil, fmt.Errorf("parse config: %w", err)
    }
    
    // Validate configuration
    if err := cfg.Validate(); err != nil {
        return nil, fmt.Errorf("invalid config: %w", err)
    }
    
    return &cfg, nil
}

// Validation ensures configuration is correct
func (c *Config) Validate() error {
    if c.Processing.Concurrency < 1 {
        return errors.New("concurrency must be at least 1")
    }
    
    if c.Processing.ChunkSize < 1 {
        return errors.New("chunk_size must be at least 1")
    }
    
    // Validate paths exist and are accessible
    for name, path := range map[string]string{
        "input":  c.Paths.Input,
        "output": c.Paths.Output,
        "work":   c.Paths.Work,
    } {
        if err := validatePath(path); err != nil {
            return fmt.Errorf("invalid %s path: %w", name, err)
        }
    }
    
    return nil
}
```

### 7. Observability & Monitoring

#### Structured Logging
```go
import (
    "go.uber.org/zap"
    "go.uber.org/zap/zapcore"
)

// Initialize logger with proper configuration
func NewLogger(level string, format string) (*zap.Logger, error) {
    var zapLevel zapcore.Level
    if err := zapLevel.UnmarshalText([]byte(level)); err != nil {
        return nil, fmt.Errorf("invalid log level: %w", err)
    }
    
    config := zap.Config{
        Level:            zap.NewAtomicLevelAt(zapLevel),
        Development:      false,
        Encoding:         format, // json or console
        EncoderConfig:    zap.NewProductionEncoderConfig(),
        OutputPaths:      []string{"stdout"},
        ErrorOutputPaths: []string{"stderr"},
    }
    
    return config.Build()
}

// Use structured logging throughout
logger.Info("processing file",
    zap.String("file", filename),
    zap.String("format", format),
    zap.Int64("size", fileSize),
    zap.Duration("duration", elapsed),
)

logger.Error("processing failed",
    zap.String("file", filename),
    zap.Error(err),
    zap.Stack("stacktrace"),
)
```

#### Metrics Collection
```go
import (
    "github.com/prometheus/client_golang/prometheus"
    "github.com/prometheus/client_golang/prometheus/promauto"
    "github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
    filesProcessed = promauto.NewCounterVec(
        prometheus.CounterOpts{
            Name: "refinery_files_processed_total",
            Help: "Total number of files processed",
        },
        []string{"type", "format", "status"},
    )
    
    processingDuration = promauto.NewHistogramVec(
        prometheus.HistogramOpts{
            Name:    "refinery_processing_duration_seconds",
            Help:    "Duration of file processing",
            Buckets: prometheus.DefBuckets,
        },
        []string{"type", "format"},
    )
    
    filesInProgress = promauto.NewGauge(
        prometheus.GaugeOpts{
            Name: "refinery_files_in_progress",
            Help: "Number of files currently being processed",
        },
    )
)

// Track metrics during processing
func processWithMetrics(ctx context.Context, file string) error {
    filesInProgress.Inc()
    defer filesInProgress.Dec()
    
    timer := prometheus.NewTimer(processingDuration.WithLabelValues(fileType, format))
    defer timer.ObserveDuration()
    
    err := process(ctx, file)
    
    status := "success"
    if err != nil {
        status = "error"
    }
    
    filesProcessed.WithLabelValues(fileType, format, status).Inc()
    
    return err
}

// Expose metrics endpoint
func startMetricsServer(port int) {
    http.Handle("/metrics", promhttp.Handler())
    http.ListenAndServe(fmt.Sprintf(":%d", port), nil)
}
```

### 8. Security Best Practices

#### Input Validation
```go
// Validate all file paths to prevent directory traversal
func validateFilePath(path string) error {
    // Clean the path
    cleanPath := filepath.Clean(path)
    
    // Ensure path doesn't escape working directory
    absPath, err := filepath.Abs(cleanPath)
    if err != nil {
        return fmt.Errorf("resolve path: %w", err)
    }
    
    workDir, err := filepath.Abs("/work")
    if err != nil {
        return fmt.Errorf("resolve work dir: %w", err)
    }
    
    if !strings.HasPrefix(absPath, workDir) {
        return errors.New("path escapes working directory")
    }
    
    return nil
}

// Validate file extensions
func validateFileExtension(filename string, allowed []string) error {
    ext := strings.ToLower(filepath.Ext(filename))
    ext = strings.TrimPrefix(ext, ".")
    
    for _, a := range allowed {
        if ext == strings.ToLower(a) {
            return nil
        }
    }
    
    return fmt.Errorf("unsupported file extension: %s", ext)
}
```

#### Secrets Management
```go
// Never hardcode secrets
// WRONG:
// apiKey := "sk-123456789"

// RIGHT:
// Load from environment or secure vault
apiKey := os.Getenv("API_KEY")
if apiKey == "" {
    return errors.New("API_KEY not set")
}

// Use secret management for Docker
// docker-compose.yml:
# secrets:
#   radarr_api_key:
#     file: ./secrets/radarr_api_key.txt
```

### 9. Performance Optimization

#### Memory Management
```go
// Use streaming for large files
func processLargeFile(path string) error {
    f, err := os.Open(path)
    if err != nil {
        return err
    }
    defer f.Close()
    
    // Stream processing with bounded memory
    reader := bufio.NewReaderSize(f, 32*1024)
    
    for {
        chunk, err := reader.ReadBytes('\n')
        if err != nil {
            if err == io.EOF {
                break
            }
            return err
        }
        
        if err := processChunk(chunk); err != nil {
            return err
        }
    }
    
    return nil
}

// Use memory pools for frequent allocations
var bytePool = sync.Pool{
    New: func() interface{} {
        return make([]byte, 64*1024)
    },
}

func processWithPool() error {
    buf := bytePool.Get().([]byte)
    defer bytePool.Put(buf)
    
    // Use buffer
    return nil
}
```

#### Database Optimization
```go
// Use prepared statements
stmt, err := db.PrepareContext(ctx, "INSERT INTO files (path, checksum) VALUES (?, ?)")
if err != nil {
    return err
}
defer stmt.Close()

// Batch inserts for better performance
tx, err := db.BeginTx(ctx, nil)
if err != nil {
    return err
}
defer tx.Rollback()

for _, file := range files {
    if _, err := tx.Stmt(stmt).ExecContext(ctx, file.Path, file.Checksum); err != nil {
        return err
    }
}

return tx.Commit()
```

### 10. Documentation Standards

#### Code Documentation
```go
// Package documentation at the top of each package
// Package processor provides media file processing capabilities.
//
// This package handles the conversion, transcoding, and normalization
// of audio and video files. It supports multiple formats and provides
// idempotent operations with full rollback support.
//
// Example usage:
//
//	cfg := processor.Config{
//	    InputDir:  "/input",
//	    OutputDir: "/output",
//	    DryRun:    true,
//	}
//
//	proc := processor.New(cfg)
//	if err := proc.ProcessAll(ctx); err != nil {
//	    log.Fatal(err)
//	}
package processor

// ProcessMedia converts a media file to the specified format.
//
// The function performs the following steps:
// 1. Validates input file exists and is accessible
// 2. Computes checksum of input file
// 3. Determines appropriate conversion strategy
// 4. Executes conversion in working directory
// 5. Validates output file integrity
// 6. Moves file to final destination
//
// Parameters:
//   - ctx: Context for cancellation and timeout control
//   - input: Path to input media file
//   - opts: Processing options including format, quality, etc.
//
// Returns:
//   - *Result: Processing result with output path and metadata
//   - error: Error if processing fails at any stage
//
// Example:
//
//	result, err := ProcessMedia(ctx, "/input/video.avi", Options{
//	    Format: "mkv",
//	    Codec:  "h264",
//	})
func ProcessMedia(ctx context.Context, input string, opts Options) (*Result, error) {
    // Implementation
}
```

#### API Documentation
```go
// Use OpenAPI/Swagger for HTTP APIs
// swagger:route POST /api/v1/process process processMedia
//
// Process a media file
//
// Converts the specified media file to the target format.
//
//     Consumes:
//     - application/json
//
//     Produces:
//     - application/json
//
//     Schemes: http, https
//
//     Security:
//       api_key:
//
//     Responses:
//       200: processResponse
//       400: errorResponse
//       500: errorResponse
```

## Quick Reference Checklist

When implementing new features or fixing bugs, ensure:

- [ ] Function accepts `context.Context` as first parameter
- [ ] All errors are wrapped with context using `fmt.Errorf` with `%w`
- [ ] Resources are cleaned up with `defer`
- [ ] Tests are written (unit + integration)
- [ ] Test coverage is >80%
- [ ] Logging uses structured format with appropriate levels
- [ ] Metrics are exposed for monitoring
- [ ] Configuration is validated on load
- [ ] Dry-run mode is supported
- [ ] Operations are idempotent
- [ ] File paths are validated against directory traversal
- [ ] Secrets are not hardcoded
- [ ] Code is formatted with `gofmt`
- [ ] Linting passes with `golangci-lint`
- [ ] Documentation is updated
- [ ] Commit message follows convention
- [ ] CI pipeline passes

## Common Patterns & Anti-Patterns

### ✅ DO
```go
// Use explicit error handling
if err := operation(); err != nil {
    return fmt.Errorf("operation failed: %w", err)
}

// Use structured logging
logger.Info("processing complete",
    "files", count,
    "duration", elapsed,
)

// Use table-driven tests
tests := []struct {
    name string
    input string
    want string
}{
    {"case1", "input1", "output1"},
    {"case2", "input2", "output2"},
}
```

### ❌ DON'T
```go
// Don't ignore errors
_ = operation() // NEVER DO THIS

// Don't use unstructured logging
log.Printf("Processed %d files in %v", count, elapsed)

// Don't repeat test code
func TestCase1(t *testing.T) { /* ... */ }
func TestCase2(t *testing.T) { /* ... */ }
// ... many similar tests
```

## Additional Resources

- [Effective Go](https://go.dev/doc/effective_go)
- [Go Code Review Comments](https://github.com/golang/go/wiki/CodeReviewComments)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [GitOps Principles](https://www.gitops.tech/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/)

---

*This document should be reviewed and updated regularly as the project evolves and new patterns emerge.*
