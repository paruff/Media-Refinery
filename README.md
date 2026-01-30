
# Media Refinery

![CI](https://github.com/paruff/Media-Refinery/actions/workflows/ci.yml/badge.svg)
![Coverage](https://codecov.io/gh/paruff/Media-Refinery/branch/main/graph/badge.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

Media Refinery is a Python-based media processing pipeline designed to handle audio and video processing tasks efficiently. This project is a conversion from a Go-based implementation to Python, leveraging modern Python practices.

## Features
- Audio and video processing modules
- Asyncio-based concurrency
- Pydantic for configuration validation
- Typer and Rich for a user-friendly CLI
- Organized testing with pytest

## Requirements
- Python 3.11+

## Installation
```bash
pip install .
```

## Usage
```bash
python -m media_refinery
```

## Convert Your Music Library
Media Refinery can help you convert a messy music library into a well-structured, metadata-enhanced `.flac` collection. Follow these steps:

### Using Docker
1. **Build the Docker Image**:
   ```bash
   docker build -t media-refinery .
   ```

2. **Run the Docker Container**:
   ```bash
   docker run --rm -v /path/to/your/music:/input -v /path/to/output:/output media-refinery
   ```
   Replace `/path/to/your/music` with the directory containing your music files and `/path/to/output` with the directory where you want the converted files to be saved.

3. **Verify the Output**:
   Check the `/path/to/output` directory for `.flac` files with embedded metadata (e.g., artist, album, title, album art).



## Quickstart

```bash
git clone https://github.com/paruff/Media-Refinery.git
cd Media-Refinery
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```


## Project Structure

```
media-refinery/
├── app/            # Main FastAPI application code (API, models, services)
├── src/            # Supporting modules (audio, video, pipeline, etc.)
├── config/         # Configuration files and templates
├── tests/          # Unit, integration, and BDD tests
├── sample_media/   # Sample media files for testing/demo
├── work/           # Working directory for runtime artifacts, logs, and db
├── docs/           # Documentation (see below)
├── .github/        # GitHub Actions workflows and templates
├── Makefile        # Common development commands
├── requirements.txt# Python dependencies
├── pyproject.toml  # Project metadata and tool config
├── README.md       # Project overview and usage
└── ...             # Other supporting files
```

## Documentation

All detailed documentation is now in the [docs/](docs/README.md) directory:

- [Architecture](docs/ARCHITECTURE.md)
- [Product Vision](docs/PRODUCT_VISION.md)
- [Implementation Summary](docs/SUMMARY.md)
- [Contribution Guide](docs/CONTRIBUTING.md)
- [Maintainers Guide](docs/MAINTAINERS_GUIDE.md)
- [Legacy Docs](docs/legacy/)

## Testing
Run tests using pytest:
```bash
pytest
```
