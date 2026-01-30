# Media Refinery

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

## Testing
Run tests using pytest:
```bash
pytest
```
