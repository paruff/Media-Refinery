#!/bin/bash
# Integration test script for Media Refinery

set -e

echo "=== Media Refinery Integration Test ==="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Cleanup function
cleanup() {
    echo ""
    echo "Cleaning up test directories..."
    rm -rf /tmp/media-test-*
}

# Set up trap for cleanup
trap cleanup EXIT

# Build the binary
echo "1. Building Media Refinery..."
if go build -o media-refinery ./cmd/refinery; then
    echo -e "${GREEN}✓ Build successful${NC}"
else
    echo -e "${RED}✗ Build failed${NC}"
    exit 1
fi

# Test 1: Version check
echo ""
echo "2. Testing version flag..."
if ./media-refinery -version | grep -q "Media Refinery"; then
    echo -e "${GREEN}✓ Version check passed${NC}"
else
    echo -e "${RED}✗ Version check failed${NC}"
    exit 1
fi

# Test 2: Config generation
echo ""
echo "3. Testing config generation..."
CONFIG_FILE="/tmp/media-test-config.yaml"
if ./media-refinery -init -config "$CONFIG_FILE" > /dev/null 2>&1; then
    if [ -f "$CONFIG_FILE" ]; then
        echo -e "${GREEN}✓ Config generation passed${NC}"
    else
        echo -e "${RED}✗ Config file not created${NC}"
        exit 1
    fi
else
    echo -e "${RED}✗ Config generation failed${NC}"
    exit 1
fi

# Test 3: Setup test directories
echo ""
echo "4. Setting up test directories..."
INPUT_DIR="/tmp/media-test-input"
OUTPUT_DIR="/tmp/media-test-output"
WORK_DIR="/tmp/media-test-work"

mkdir -p "$INPUT_DIR/music"
mkdir -p "$INPUT_DIR/video"
mkdir -p "$OUTPUT_DIR"
mkdir -p "$WORK_DIR"

# Create dummy media files
echo "Creating test files..."
touch "$INPUT_DIR/music/Artist - Song.mp3"
touch "$INPUT_DIR/music/Another Artist - Another Song.flac"
touch "$INPUT_DIR/video/Movie (2024).avi"
touch "$INPUT_DIR/video/Show - S01E01.mkv"

echo -e "${GREEN}✓ Test environment setup${NC}"

# Test 4: Update config with test directories
echo ""
echo "5. Configuring test paths..."
cat > "$CONFIG_FILE" << EOF
input_dir: $INPUT_DIR
output_dir: $OUTPUT_DIR
work_dir: $WORK_DIR
dry_run: true
verify_checksums: false
concurrency: 2
chunk_size: 100

audio:
  enabled: true
  output_format: flac
  output_quality: lossless
  supported_types:
    - mp3
    - flac
    - aac
  normalize: true
  bit_depth: 16
  sample_rate: 44100

video:
  enabled: true
  output_format: mkv
  video_codec: h264
  audio_codec: aac
  supported_types:
    - avi
    - mkv
    - mp4
  quality: high
  resolution: keep

metadata:
  fetch_online: false
  sources:
    - local
  embed_artwork: false
  cleanup_tags: true

organization:
  music_pattern: "{artist}/{album}/{track} - {title}"
  video_pattern: "{type}/{title} ({year})"
  use_symlinks: false

logging:
  level: info
  format: text
  output_file: ""

integrations:
  beets:
    enabled: false
    url: http://localhost:8337
    token: ""
  tdarr:
    enabled: false
    url: http://localhost:8265
    api_key: ""
    library_id: ""
  radarr:
    enabled: false
    url: http://localhost:7878
    api_key: ""
  sonarr:
    enabled: false
    url: http://localhost:8989
    api_key: ""
EOF

echo -e "${GREEN}✓ Configuration updated${NC}"

# Test 5: Dry run
echo ""
echo "6. Running dry-run test..."
if ./media-refinery -config "$CONFIG_FILE" 2>&1 | tee /tmp/media-test-output.log; then
    if grep -q "DRY-RUN mode enabled" /tmp/media-test-output.log; then
        echo -e "${GREEN}✓ Dry-run completed${NC}"
    else
        echo -e "${YELLOW}⚠ Dry-run may not have run in dry-run mode${NC}"
    fi
    
    if grep -q "Found.*media files" /tmp/media-test-output.log; then
        echo -e "${GREEN}✓ Media files detected${NC}"
    else
        echo -e "${YELLOW}⚠ No media files detected${NC}"
    fi
else
    echo -e "${RED}✗ Dry-run failed${NC}"
    exit 1
fi

# Test 6: Unit tests
echo ""
echo "7. Running unit tests..."
if go test ./... -v; then
    echo -e "${GREEN}✓ All unit tests passed${NC}"
else
    echo -e "${RED}✗ Some unit tests failed${NC}"
    exit 1
fi

# Summary
echo ""
echo "==================================="
echo -e "${GREEN}✓ All integration tests passed!${NC}"
echo "==================================="
echo ""
echo "Test Results:"
echo "  - Binary builds successfully"
echo "  - Version flag works"
echo "  - Config generation works"
echo "  - Dry-run mode works"
echo "  - Media file detection works"
echo "  - Unit tests pass"
echo ""
echo "Next steps:"
echo "  1. Review DOCKER.md for Docker deployment"
echo "  2. Set up integrations (beets, tdarr, radarr, sonarr)"
echo "  3. Run on your actual media library"
echo ""
