# Feature: Audio File Conversion to FLAC

## User Story

**As a** media library curator
**I want to** convert audio files from various formats to FLAC
**So that** I have a consistent, lossless, high-quality audio archive

---

## Business Value

Media libraries often contain mixed formats (MP3, AAC, M4A, OGG, WAV) with varying quality levels and inconsistent metadata. This creates challenges:
- Quality degradation from lossy formats
- Metadata inconsistencies across formats
- Compatibility issues with media servers
- Complex library management

**Value delivered**:
- Lossless quality preservation (no generation loss)
- Standardized metadata format (Vorbis comments)
- Better Plex/Jellyfin/Music Assistant compatibility
- Simplified downstream processing
- ~30-50% disk space savings vs. WAV

**Success metrics**:
- 99%+ successful conversion rate
- <10 seconds per file conversion time
- 100% metadata preservation
- Zero audio quality loss

---

## Acceptance Criteria

### Scenario 1: Basic MP3 to FLAC Conversion ✅

**Given** a valid MP3 file located at `/input/test-song.mp3`
**And** the file is 5.2 MB in size
**And** the file has ID3v2.3 tags with:
  - Artist: "Test Artist"
  - Album: "Test Album"
  - Title: "Test Song"
  - Year: "2024"
**When** the audio conversion process is executed
**Then** a FLAC file should be created at `/output/test-song.flac`
**And** the FLAC file should be a valid FLAC audio stream
**And** the FLAC file should contain Vorbis comments with:
  - ARTIST: "Test Artist"
  - ALBUM: "Test Album"
  - TITLE: "Test Song"
  - DATE: "2024"
**And** the audio data should be bit-identical to source (lossless)
**And** the original MP3 file should remain unchanged at `/input/test-song.mp3`
**And** a SHA256 checksum should be calculated and stored for the output
**And** the conversion should complete in <10 seconds

**Test File**: `test/acceptance/audio_conversion_test.go::TestMP3toFLACConversion`

---

### Scenario 2: Multiple Input Format Support ✅

**Given** the following files exist in `/input/`:
  - `song1.mp3` (MP3/320kbps)
  - `song2.aac` (AAC/256kbps)
  - `song3.m4a` (ALAC/lossless)
  - `song4.ogg` (Vorbis/q8)
  - `song5.wav` (PCM/44.1kHz/16-bit)
  - `song6.opus` (Opus/128kbps)
**When** the batch conversion process is executed
**Then** 6 FLAC files should be created in `/output/`
**And** each output file should:
  - Be a valid FLAC file
  - Preserve original audio quality
  - Maintain metadata
  - Have unique SHA256 checksum
**And** the conversion summary should report "6 of 6 successful"

**Test File**: `test/acceptance/audio_conversion_test.go::TestMultipleFormatSupport`

---

### Scenario 3: Metadata Preservation ✅

**Given** an MP3 file with comprehensive ID3v2.4 tags:
Artist: Pink Floyd
Album: The Dark Side of the Moon
Title: Time
Year: 1973
Track: 4/10
Disc: 1/1
Genre: Progressive Rock
Album Artist: Pink Floyd
Comment: Remastered 2011
Album Art: [embedded JPEG, 600x600px, 150KB]
**When** the file is converted to FLAC
**Then** all metadata should be converted to Vorbis comments:
ARTIST=Pink Floyd
ALBUM=The Dark Side of the Moon
TITLE=Time
DATE=1973
TRACKNUMBER=4
TOTALTRACKS=10
DISCNUMBER=1
TOTALDISCS=1
GENRE=Progressive Rock
ALBUMARTIST=Pink Floyd
COMMENT=Remastered 2011
**And** the album art should be embedded as FLAC PICTURE block
**And** the album art should maintain original resolution (600x600px)
**And** all tags should be readable by `metaflac --list`

**Test File**: `test/acceptance/audio_conversion_test.go::TestMetadataPreservation`

---

### Scenario 4: Invalid File Rejection ❌

**Given** a file named `corrupted.mp3` that contains:
  - Invalid audio data (random bytes)
  - Correct `.mp3` extension
  - Readable file permissions
**When** conversion is attempted
**Then** the conversion should fail immediately
**And** the error message should be:
Error: Invalid audio file 'corrupted.mp3'
Reason: File header validation failed
Details: Not a valid MP3/audio file
**And** no output file should be created
**And** the failure should be logged at ERROR level with:
  - File path
  - Error reason
  - Timestamp
**And** if in batch mode, processing should continue with next file
**And** the final summary should report this as a failure

**Test File**: `test/acceptance/audio_conversion_test.go::TestInvalidFileRejection`

---

### Scenario 5: Dry Run Mode 🔍

**Given** dry run mode is enabled (`--dry-run` flag)
**And** there are 10 MP3 files in `/input/` (total 50 MB)
**When** the conversion process is executed
**Then** no output files should be created in `/output/`
**And** no changes should be made to the filesystem
**And** a preview report should be generated showing:
Dry Run Summary:
Input files: 10
Total size: 50.0 MB
Estimated output size: 48.5 MB (FLAC compression)
Estimated processing time: ~100 seconds
Files to be processed:

song1.mp3 → song1.flac (5.0 MB → 4.8 MB)
song2.mp3 → song2.flac (5.1 MB → 4.9 MB)
...

Validation results:

Valid files: 10
Invalid files: 0
Disk space required: 48.5 MB
Disk space available: 500 GB ✓

**And** validation errors (if any) should be reported
**And** the exit code should be 0 (success)

**Test File**: `test/acceptance/audio_conversion_test.go::TestDryRunMode`

---

### Scenario 6: Idempotent Re-runs ♻️

**Given** `/input/song.mp3` has been converted to `/output/song.flac`
**And** the checksum matches database record (SHA256: abc123...)
**And** both files exist and are unchanged
**When** the conversion process is run again on the same input
**Then** the system should detect the existing output
**And** should verify the checksum matches
**And** should skip re-conversion
**And** should log: "File already converted, checksum verified, skipping"
**And** should not consume CPU/disk I/O for conversion
**And** should return success (not an error)
**And** the total processing time should be minimal (<1 second)

**Test File**: `test/acceptance/audio_conversion_test.go::TestIdempotentRerun`

---

### Scenario 7: Partial Processing Recovery 🔄

**Given** a batch of 100 files is being processed
**And** 42 files have been successfully converted
**And** the checksums for these 42 files are stored in the database
**When** the process is interrupted (SIGINT, power loss, crash)
**And** the process is restarted
**Then** the system should:
  - Scan the output directory
  - Verify checksums of existing outputs
  - Skip the 42 already-processed files
  - Resume processing from file #43
  - Complete the remaining 58 files
**And** the progress should show: "Resuming from 42/100"
**And** no files should be re-processed
**And** the final summary should report: "100 of 100 successful"

**Test File**: `test/acceptance/audio_conversion_test.go::TestPartialRecovery`

---

### Scenario 8: Context Cancellation 🛑

**Given** a long-running batch conversion is in progress
**And** 25 of 100 files have been processed
**And** 4 workers are actively converting files
**When** the user sends SIGINT (Ctrl+C)
**Then** the context should be cancelled
**And** currently processing files (4) should complete gracefully
**And** no new files should start processing
**And** partial/incomplete output files should be cleaned up
**And** the cleanup should include:
  - Removing any `.tmp` files
  - Removing outputs without matching checksums
**And** a cancellation message should be logged: "Received cancellation signal, shutting down gracefully"
**And** the exit code should be 130 (SIGINT)
**And** the database should be updated with completed files

**Test File**: `test/acceptance/audio_conversion_test.go::TestContextCancellation`

---

### Scenario 9: Disk Space Validation 💾

**Given** the output directory `/output/` has only 100 MB free space
**And** the conversion job requires 500 MB (estimated)
**When** the conversion process starts
**Then** the system should check available disk space before processing
**And** should fail immediately with error:
Error: Insufficient disk space
Required: 500 MB
Available: 100 MB
Location: /output
**And** no conversions should be attempted
**And** no temporary files should be created
**And** the error should be logged at ERROR level
**And** the exit code should be 1 (error)

**Test File**: `test/acceptance/audio_conversion_test.go::TestDiskSpaceValidation`

---

### Scenario 10: Concurrent Processing ⚡

**Given** 100 MP3 files in `/input/` directory
**And** concurrency is set to 4 workers (`concurrency: 4` in config)
**When** batch conversion is executed
**Then** the system should:
  - Process exactly 4 files concurrently
  - Not exceed 4 concurrent FFmpeg processes
  - Use worker pool pattern for file distribution
  - Report progress: "Processing 4/100 files..."
**And** the total processing time should be ~25% of sequential processing
**And** memory usage should remain under 400 MB (100 MB per worker)
**And** CPU utilization should scale with worker count
**And** all 100 files should complete successfully
**And** no race conditions should occur (verified with `-race` flag)

**Test File**: `test/acceptance/audio_conversion_test.go::TestConcurrentProcessing`

---

## Non-Functional Requirements

### Performance

| Metric | Requirement | Test Method |
|--------|-------------|-------------|
| Single file conversion (5MB MP3) | <10 seconds | Benchmark test |
| Batch processing (100 files) | <5 minutes on 4 cores | Integration test |
| Memory per worker | <100 MB | Memory profiling |
| CPU utilization | >90% with concurrent workers | Resource monitoring |
| Startup time | <2 seconds | Integration test |

### Reliability

| Metric | Requirement | Test Method |
|--------|-------------|-------------|
| Success rate (valid files) | >99% | Fuzz testing, large corpus |
| Crash recovery | 100% resumable | Kill test during processing |
| Checksum verification | 100% | All outputs verified |
| Data integrity | Zero corruption | Bit-perfect comparison |

### Scalability

| Metric | Requirement | Test Method |
|--------|-------------|-------------|
| Concurrent workers | 1-16 configurable | Load testing |
| Batch size | Up to 10,000 files | Large batch test |
| Max file size | 1 GB per file | Large file test |
| Total data volume | Unlimited (streaming) | Continuous processing test |

### Usability

| Metric | Requirement | Test Method |
|--------|-------------|-------------|
| Error messages | Clear, actionable | Manual review |
| Progress reporting | Real-time, accurate | Integration test |
| Logging | Structured, appropriate levels | Log analysis |
| Configuration | YAML with validation | Config test |

---

## Technical Constraints

1. **FFmpeg Dependency**: Must use FFmpeg (already in Docker image)
2. **Input Formats**: MP3, AAC, M4A, OGG, WAV, OPUS
3. **Output Format**: FLAC (v1.3.x or higher)
4. **Metadata**: ID3v2 → Vorbis comments mapping
5. **Docker Environment**: Must work in containerized environment
6. **Go Version**: Go 1.21+

---

## Test Strategy

### Unit Tests (`pkg/audio/`)

| File | Tests | Coverage Target |
|------|-------|-----------------|
| `converter_test.go` | Conversion logic (mocked FFmpeg) | >85% |
| `metadata_test.go` | Metadata mapping | >90% |
| `validator_test.go` | File validation | >90% |
| `checksum_test.go` | Checksum calculation | 100% |

### Integration Tests (`test/integration/`)

| File | Tests | Purpose |
|------|-------|---------|
| `audio_conversion_integration_test.go` | Real FFmpeg conversion | Verify FFmpeg integration |
| `format_support_integration_test.go` | All input formats → FLAC | Format compatibility |
| `metadata_integration_test.go` | Metadata preservation | End-to-end metadata |

### Acceptance Tests (`test/acceptance/`)

| File | Tests | Maps to Scenarios |
|------|-------|-------------------|
| `audio_conversion_test.go` | All 10 scenarios above | 1:1 mapping |

### Performance Tests
```bash
# Benchmark single file
go test -bench=BenchmarkMP3toFLAC -benchmem ./pkg/audio/

# Benchmark batch processing
go test -bench=BenchmarkBatchConversion -benchmem ./pkg/audio/

# Profile CPU
go test -cpuprofile=cpu.prof -bench=. ./pkg/audio/
go tool pprof cpu.prof

# Profile memory
go test -memprofile=mem.prof -bench=. ./pkg/audio/
go tool pprof mem.prof
```

---

## Definition of Done

- [x] All 10 acceptance criteria scenarios pass ✅
- [x] Unit tests >85% coverage ✅
- [x] Integration tests cover all input formats ✅
- [x] Acceptance tests automated in CI ✅
- [x] Performance benchmarks meet requirements ✅
- [x] Race detector passes (`go test -race`) ✅
- [x] Memory profiling shows no leaks ✅
- [x] Code reviewed and approved ✅
- [x] Documentation updated (README, API docs) ✅
- [x] No critical or high-priority bugs ✅
- [x] Dry-run mode tested and working ✅
- [x] Idempotency verified through tests ✅
- [x] Error handling comprehensive ✅
- [x] Logging structured and appropriate ✅

---

## Dependencies

- **FFmpeg**: Version 4.4+ (already in Docker image)
- **Checksum storage**: Database or file-based tracking
- **Test files**: Audio samples in `test/testdata/audio/`
  - Need samples: MP3, AAC, M4A, OGG, WAV, OPUS
  - Various bitrates and qualities
  - Files with/without metadata
  - Corrupted files for negative testing

---

## Out of Scope (Explicitly NOT Included)

- ❌ Video file conversion (separate feature)
- ❌ Obscure audio formats (AIFF, WMA, RA, etc.)
- ❌ Real-time streaming conversion
- ❌ Cloud storage integration (S3, GCS, Azure)
- ❌ Audio enhancement/normalization/EQ
- ❌ Web UI for conversion management
- ❌ API endpoints (command-line only for v1)
- ❌ Playlist generation
- ❌ Duplicate detection
- ❌ Audio fingerprinting

---

## Open Questions & Decisions

| Question | Decision | Date | Decided By |
|----------|----------|------|------------|
| Support configurable output formats? | FLAC only for v1, configurable in v2 | 2024-01-15 | Product Owner |
| Handle files with no metadata? | Create basic metadata from filename | 2024-01-15 | Team |
| Parallel processing limit? | Configurable via `config.yaml`, default 4 | 2024-01-16 | Team |
| Checksum algorithm? | SHA256 (good balance of speed/security) | 2024-01-16 | Security Team |
| Handle existing output files? | Verify checksum, skip if match, warn if mismatch | 2024-01-17 | Product Owner |

---

## Metrics & Observability

### Prometheus Metrics
