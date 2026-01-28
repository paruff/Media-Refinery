# System Architecture

The Media Refinery system is designed as a production-grade media normalization and organization pipeline. Its flexible and modular architecture enables safe and reliable processing of multimedia libraries. Below is an overview of the top-level components and their interactions.

## Core Design Principles
- **Idempotency**: Operations produce consistent results when run multiple times.
- **Safety**: Features such as dry-run mode and transaction-like rollback ensure no accidental data loss.
- **Extensibility**: A highly modular design allows for easy addition of new functionalities and integrations.
- **Observability**: Granular logging and error reporting enhance the ability to monitor operations.

## Core System Components

### 1. Configuration System (`pkg/config`)
- YAML-based configuration files.
- Environment variable support for overriding defaults.
- Strong validation and error handling mechanisms.

### 2. Logger (`pkg/logger`)
- Provides structured logging in text or JSON formats.
- Ensures thread-safe operations with configurable log levels.
- Includes counters for tracking system observability.

### 3. Validator (`pkg/validator`)
- Validates file types and computes SHA-256 checksums.
- Performs second-level validation by scanning for malicious files.
- Ensures compliance with input path constraints.

### 4. Metadata System (`pkg/metadata`)
- Extracts and parses filename metadata.
- Cleans up and standardizes metadata tags.
- Supports customizable path templates.
- Facilitates metadata merging for enriched information.

### 5. Storage System (`pkg/storage`)
- Handles file movement with safety mechanisms.
- Supports dry-runs and transaction-like rollback.
- Provides intelligent backups to prevent data loss.

### 6. Processors (`pkg/processors`)
- Plugin-based processors for handling multimedia content.
    - **Audio Processing**: Converts audio formats to FLAC.
    - **Video Processing**: Handles video normalization into MKV and H.264/AAC compression formats.
- Provides hooks for extensibility.

### 7. Pipeline Orchestration (`pkg/pipeline`)
- Coordinates workflow steps such as scanning, validation, processing, and reporting.
- Optimized for concurrency with advanced error handling.
- Tracks and reports performance metrics.

### 8. Integrations Layer (`pkg/integrations`)
- Leverages APIs of third-party systems for auxiliary functions.
    - **Beets**: Organizes and manages music libraries using MusicBrainz metadata.
    - **Tdarr**: Automates transcoding workflows with hardware acceleration.
    - **Radarr**: Enhances movie metadata and collection organization.
    - **Sonarr**: Manages episodic TV content with metadata from TVDB.

## Typical Workflow
The workflow for processing media files involves the following key steps:
1. **Scan**: Identify media files in input directories.
2. **Validate**: Check the integrity and format of each file.
3. **Extract**: Retrieve metadata and attributes.
4. **Process**: Transform files into user-defined formats.
5. **Organize**: Rename files and arrange them into folder structures compatible with Plex and Music Assistant.
6. **Verify**: Confirm successful processing.
7. **Report**: Record statistics and log analysis.

## Safe Operating Features
- **Dry-Run Mode**: Executes a simulated run to validate workflows without modifying files.
- **Rollback Mechanisms**: Ensures that failed processing results in no data loss.
- **Checksum Validation**: Safeguards file integrity during all operations.
- **Concurrent Processing**: Speeds up operations using a tunable worker pool.

## Directory Structure
Example setup for media processing:
```
media-refinery/
├── input/              # Input media files.
├── output/             # Output files after processing.
├── work/               # Temporary workspace.
├── config/             # Configuration files.
│   ├── beets/
│   ├── tdarr/
│   ├── radarr/
│   ├── sonarr/
│   └── plex/
```

## Future Enhancements
The project roadmap includes:
- Adding a web UI for real-time monitoring.
- Supporting cloud storage systems like S3.
- Direct API integrations with MusicBrainz, TMDB, and TVDB.
- Advanced duplicate detection algorithms.
- System-wide Prometheus metrics export for distributed setups.