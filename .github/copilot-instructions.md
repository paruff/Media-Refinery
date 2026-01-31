# Copilot Instructions for Media-Refinery

## 🎯 Project Overview

**Media-Refinery** is a Python-based media processing pipeline for audio and video normalization, metadata enhancement, and library organization. The project follows modern Python practices with strong typing, async/await patterns, and comprehensive testing.

**Tech Stack**:
- Python 3.11+
- FastAPI (API layer)
- Pydantic (configuration & validation)
- SQLAlchemy + Alembic (database & migrations)
- Celery + Redis (distributed task execution, optional)
- Pytest + Behave (testing)
- Docker (containerization)

**Key External Dependencies**:
- FFmpeg (audio/video processing)
- Beets (music library organization)
- Radarr/Sonarr/Tdarr APIs (media server integrations)

---

## 📁 Project Structure

```
media-refinery/
├── app/                    # FastAPI application (API, models, services)
│   ├── api/               # REST API endpoints
│   ├── models/            # SQLAlchemy models
│   ├── schemas/           # Pydantic schemas
│   └── services/          # Business logic services
├── src/                   # Core processing modules
│   ├── media_refinery/
│   │   ├── audio/        # Audio conversion logic
│   │   ├── video/        # Video conversion logic
│   │   ├── processor/    # Batch processing, worker pools
│   │   ├── state/        # State management, checksums
│   │   └── config/       # Configuration models
├── tests/                 # Comprehensive test suite
│   ├── unit/             # Unit tests (fast, isolated)
│   ├── integration/      # Integration tests (real dependencies)
│   ├── e2e/              # End-to-end tests (full workflows)
│   └── features/         # BDD tests (Gherkin/Behave)
├── alembic/              # Database migrations
├── docs/                 # Documentation
├── profiles/             # Processing profiles (encoding configs)
├── sample_media/         # Test media files
└── work/                 # Runtime artifacts (logs, db, temp files)
```

---

## 🔑 Core Principles (ALWAYS FOLLOW)

### 1. Test-Driven Development (TDD)
**CRITICAL**: Write tests BEFORE implementation. No exceptions.

```python
# CORRECT ORDER:
# 1. Write test first (fails)
# 2. Implement minimum code to pass
# 3. Refactor
# 4. Repeat

# WRONG: Don't write implementation first, then tests
```

**Test Pyramid** (target distribution):
- 70% Unit tests (fast, isolated, mock dependencies)
- 20% Integration tests (real dependencies like FFmpeg)
- 10% E2E tests (full workflows, UI to database)

**Coverage Target**: >85% overall, 100% for critical paths (checksums, file operations, state management)

### 2. Type Hints Everywhere
All functions must have complete type hints:

```python
from typing import Optional, List, Dict
from pathlib import Path

# CORRECT:
async def convert_audio(
    input_path: Path,
    output_path: Path,
    format: str = "flac",
    preserve_metadata: bool = True
) -> AudioConversionResult:
    """Convert audio file to specified format.
    
    Args:
        input_path: Path to input audio file
        output_path: Path to output file
        format: Target audio format (default: flac)
        preserve_metadata: Whether to preserve ID3/Vorbis tags
        
    Returns:
        AudioConversionResult containing success status and metadata
        
    Raises:
        FileNotFoundError: If input file doesn't exist
        InvalidAudioFormatError: If format is unsupported
    """
    pass

# WRONG: No type hints
def convert_audio(input_path, output_path, format="flac"):
    pass
```

### 3. Async/Await for I/O Operations
Use `asyncio` for all I/O operations (file operations, subprocess calls, HTTP requests):

```python
import asyncio
from pathlib import Path

# CORRECT: Async subprocess execution
async def execute_ffmpeg(args: List[str]) -> str:
    """Execute FFmpeg command asynchronously."""
    process = await asyncio.create_subprocess_exec(
        "ffmpeg", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        raise FFmpegError(f"FFmpeg failed: {stderr.decode()}")
    
    return stdout.decode()

# WRONG: Blocking subprocess
def execute_ffmpeg(args):
    result = subprocess.run(["ffmpeg"] + args, capture_output=True)
    return result.stdout.decode()
```

### 4. Pydantic for Configuration & Validation
All configuration must use Pydantic models:

```python
from pydantic import BaseModel, Field, validator
from pathlib import Path

class AudioConfig(BaseModel):
    """Audio processing configuration."""
    
    format: str = Field(default="flac", description="Target audio format")
    compression_level: int = Field(default=5, ge=0, le=8)
    preserve_metadata: bool = Field(default=True)
    sample_rate: Optional[int] = Field(default=None, description="Target sample rate (Hz)")
    
    @validator('format')
    def validate_format(cls, v):
        """Ensure format is supported."""
        supported = {"flac", "mp3", "aac", "ogg", "opus", "wav"}
        if v not in supported:
            raise ValueError(f"Unsupported format: {v}. Must be one of {supported}")
        return v
    
    class Config:
        """Pydantic config."""
        frozen = True  # Immutable config
        extra = "forbid"  # Raise error on unknown fields
```

### 5. Pathlib Over String Paths
Always use `pathlib.Path` for file operations:

```python
from pathlib import Path

# CORRECT:
def process_file(input_path: Path, output_dir: Path) -> Path:
    """Process file and return output path."""
    output_path = output_dir / f"{input_path.stem}.flac"
    
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)
    
    return output_path

# WRONG: String manipulation
def process_file(input_path, output_dir):
    output_path = os.path.join(output_dir, input_path.split("/")[-1].replace(".mp3", ".flac"))
    return output_path
```

### 6. Structured Logging
Use structured logging with context:

```python
import structlog

logger = structlog.get_logger(__name__)

async def convert_file(input_path: Path) -> None:
    """Convert file with structured logging."""
    
    # Bind context to all log messages in this function
    log = logger.bind(
        input_file=str(input_path),
        operation="audio_conversion"
    )
    
    log.info("starting_conversion", format="flac")
    
    try:
        result = await _do_conversion(input_path)
        log.info("conversion_complete", 
                 duration_ms=result.duration_ms,
                 output_size_mb=result.size_mb)
    except Exception as e:
        log.error("conversion_failed", error=str(e), exc_info=True)
        raise
```

### 7. Error Handling Patterns
Specific exception types with clear messages:

```python
# Define custom exceptions
class MediaRefineryError(Exception):
    """Base exception for Media-Refinery."""
    pass

class InvalidAudioFormatError(MediaRefineryError):
    """Raised when audio format is invalid or unsupported."""
    pass

class FFmpegError(MediaRefineryError):
    """Raised when FFmpeg execution fails."""
    
    def __init__(self, message: str, command: List[str], stderr: str):
        super().__init__(message)
        self.command = command
        self.stderr = stderr

# Use in code
async def validate_audio_format(path: Path) -> str:
    """Validate audio file format.
    
    Raises:
        InvalidAudioFormatError: If format is unsupported
        FileNotFoundError: If file doesn't exist
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    
    # Detect format using FFprobe
    format_name = await detect_format(path)
    
    if format_name not in SUPPORTED_FORMATS:
        raise InvalidAudioFormatError(
            f"Unsupported format '{format_name}' in file: {path}. "
            f"Supported formats: {', '.join(SUPPORTED_FORMATS)}"
        )
    
    return format_name
```

---

## 🧪 Testing Guidelines

### Test Structure

```python
# tests/unit/test_audio_converter.py
import pytest
from pathlib import Path
from media_refinery.audio.converter import AudioConverter

class TestAudioConverter:
    """Unit tests for AudioConverter."""
    
    @pytest.fixture
    def converter(self):
        """Create converter instance."""
        return AudioConverter(format="flac", compression_level=5)
    
    @pytest.fixture
    def temp_audio_file(self, tmp_path: Path) -> Path:
        """Create temporary audio file for testing."""
        audio_file = tmp_path / "test.mp3"
        # Create dummy MP3 file
        audio_file.write_bytes(b"dummy mp3 data")
        return audio_file
    
    def test_build_ffmpeg_command_basic(self, converter: AudioConverter):
        """Test FFmpeg command building with basic options."""
        input_path = Path("/input/song.mp3")
        output_path = Path("/output/song.flac")
        
        command = converter.build_ffmpeg_command(input_path, output_path)
        
        assert "ffmpeg" in command
        assert "-i" in command
        assert str(input_path) in command
        assert str(output_path) in command
        assert "-c:a" in command
        assert "flac" in command
    
    @pytest.mark.asyncio
    async def test_convert_file_success(
        self,
        converter: AudioConverter,
        temp_audio_file: Path,
        tmp_path: Path
    ):
        """Test successful file conversion."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        result = await converter.convert_file(
            temp_audio_file,
            output_dir
        )
        
        assert result.success is True
        assert result.output_path.exists()
        assert result.output_path.suffix == ".flac"
    
    @pytest.mark.asyncio
    async def test_convert_file_invalid_input(
        self,
        converter: AudioConverter,
        tmp_path: Path
    ):
        """Test conversion with non-existent file."""
        nonexistent = tmp_path / "nonexistent.mp3"
        output_dir = tmp_path / "output"
        
        with pytest.raises(FileNotFoundError) as exc_info:
            await converter.convert_file(nonexistent, output_dir)
        
        assert "not found" in str(exc_info.value).lower()
```

### Test Naming Convention
```python
# Pattern: test_<function_name>_<scenario>_<expected_result>

def test_convert_audio_valid_mp3_succeeds():
    """Test audio conversion succeeds for valid MP3."""
    pass

def test_convert_audio_corrupted_file_raises_error():
    """Test audio conversion raises error for corrupted file."""
    pass

def test_build_ffmpeg_command_with_metadata_includes_map_flag():
    """Test FFmpeg command includes metadata mapping flag."""
    pass
```

### Parametrized Tests
```python
@pytest.mark.parametrize("input_format,expected_codec", [
    ("mp3", "libmp3lame"),
    ("aac", "aac"),
    ("flac", "flac"),
    ("ogg", "libvorbis"),
    ("opus", "libopus"),
    ("wav", "pcm_s16le"),
])
def test_format_to_codec_mapping(input_format: str, expected_codec: str):
    """Test format to FFmpeg codec mapping."""
    codec = get_codec_for_format(input_format)
    assert codec == expected_codec
```

### Async Test Fixtures
```python
import pytest
import asyncio

@pytest.fixture
async def async_converter():
    """Create and cleanup async converter."""
    converter = AsyncAudioConverter()
    await converter.initialize()
    
    yield converter
    
    await converter.cleanup()

@pytest.mark.asyncio
async def test_async_conversion(async_converter):
    """Test async conversion."""
    result = await async_converter.convert(Path("input.mp3"))
    assert result.success
```

---

## 🏗️ Code Organization Patterns

### Service Layer Pattern
```python
# app/services/audio_service.py
from typing import List, Optional
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job, JobStatus
from src.media_refinery.audio.converter import AudioConverter

class AudioService:
    """Service for audio processing operations."""
    
    def __init__(self, db: AsyncSession, converter: AudioConverter):
        """Initialize service with dependencies."""
        self.db = db
        self.converter = converter
        self.logger = structlog.get_logger(__name__)
    
    async def process_audio_file(
        self,
        job_id: int,
        input_path: Path,
        output_dir: Path
    ) -> Job:
        """Process audio file and update job status.
        
        Args:
            job_id: Database job ID
            input_path: Path to input audio file
            output_dir: Directory for output files
            
        Returns:
            Updated Job model
        """
        job = await self.db.get(Job, job_id)
        
        try:
            job.status = JobStatus.PROCESSING
            await self.db.commit()
            
            # Perform conversion
            result = await self.converter.convert_file(input_path, output_dir)
            
            # Update job with results
            job.status = JobStatus.COMPLETED
            job.output_path = str(result.output_path)
            job.checksum = result.checksum
            await self.db.commit()
            
            self.logger.info("audio_processing_complete", job_id=job_id)
            
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            await self.db.commit()
            
            self.logger.error("audio_processing_failed", 
                            job_id=job_id, 
                            error=str(e))
            raise
        
        return job
```

### Repository Pattern (Database Access)
```python
# app/repositories/job_repository.py
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.job import Job, JobStatus

class JobRepository:
    """Repository for Job database operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(self, **kwargs) -> Job:
        """Create new job."""
        job = Job(**kwargs)
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        return job
    
    async def get_by_id(self, job_id: int) -> Optional[Job]:
        """Get job by ID."""
        return await self.db.get(Job, job_id)
    
    async def get_pending_jobs(self, limit: int = 100) -> List[Job]:
        """Get pending jobs."""
        stmt = (
            select(Job)
            .where(Job.status == JobStatus.PENDING)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def update_status(self, job_id: int, status: JobStatus) -> Job:
        """Update job status."""
        job = await self.get_by_id(job_id)
        job.status = status
        await self.db.commit()
        return job
```

### FastAPI Endpoint Pattern
```python
# app/api/endpoints/audio.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.job import JobCreate, JobResponse
from app.services.audio_service import AudioService
from app.dependencies import get_db, get_audio_service

router = APIRouter(prefix="/audio", tags=["audio"])

@router.post("/convert", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def convert_audio(
    job_data: JobCreate,
    audio_service: AudioService = Depends(get_audio_service)
) -> JobResponse:
    """Submit audio conversion job.
    
    Args:
        job_data: Job creation data
        audio_service: Injected audio service
        
    Returns:
        Created job information
        
    Raises:
        HTTPException: If job creation fails
    """
    try:
        job = await audio_service.create_conversion_job(
            input_path=job_data.input_path,
            output_dir=job_data.output_dir,
            format=job_data.format
        )
        return JobResponse.from_orm(job)
        
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Job creation failed: {str(e)}"
        )

@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job_status(
    job_id: int,
    audio_service: AudioService = Depends(get_audio_service)
) -> JobResponse:
    """Get job status by ID."""
    job = await audio_service.get_job(job_id)
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )
    
    return JobResponse.from_orm(job)
```

---

## 🔄 Concurrency Patterns

### Worker Pool with Semaphore
```python
import asyncio
from typing import List, Callable, Any

class WorkerPool:
    """Async worker pool for concurrent task execution."""
    
    def __init__(self, max_workers: int = 4):
        """Initialize worker pool.
        
        Args:
            max_workers: Maximum concurrent workers
        """
        self.semaphore = asyncio.Semaphore(max_workers)
        self.logger = structlog.get_logger(__name__)
    
    async def execute_task(
        self,
        task: Callable,
        *args: Any,
        **kwargs: Any
    ) -> Any:
        """Execute single task with semaphore."""
        async with self.semaphore:
            return await task(*args, **kwargs)
    
    async def execute_all(
        self,
        tasks: List[Callable],
        *args: Any,
        **kwargs: Any
    ) -> List[Any]:
        """Execute all tasks concurrently.
        
        Args:
            tasks: List of async callables
            
        Returns:
            List of results in same order as tasks
        """
        coroutines = [
            self.execute_task(task, *args, **kwargs)
            for task in tasks
        ]
        
        return await asyncio.gather(*coroutines)

# Usage:
pool = WorkerPool(max_workers=4)
results = await pool.execute_all([
    convert_file1,
    convert_file2,
    convert_file3,
])
```

---

## 📝 Documentation Standards

### Docstring Format (Google Style)
```python
def complex_function(
    param1: str,
    param2: int,
    optional_param: Optional[bool] = None
) -> Dict[str, Any]:
    """One-line summary of function.
    
    More detailed description if needed. Can span multiple lines
    and include examples or usage notes.
    
    Args:
        param1: Description of first parameter
        param2: Description of second parameter
        optional_param: Description of optional parameter.
            Defaults to None.
            
    Returns:
        Dictionary containing:
            - key1: Description of key1
            - key2: Description of key2
            
    Raises:
        ValueError: If param2 is negative
        TypeError: If param1 is not a string
        
    Example:
        >>> result = complex_function("test", 42)
        >>> print(result["key1"])
        'value1'
    """
    pass
```

---

## 🚨 Common Mistakes to Avoid

### ❌ DON'T: Write implementation before tests
```python
# WRONG ORDER:
def convert_audio(path):
    # Implementation first
    pass

def test_convert_audio():
    # Test second
    pass
```

✅ **DO: Write test first**
```python
# CORRECT ORDER:
def test_convert_audio():
    # Test first (fails)
    result = convert_audio("input.mp3")
    assert result.success

def convert_audio(path):
    # Implementation second (to pass test)
    pass
```

### ❌ DON'T: Use blocking I/O in async functions
```python
# WRONG:
async def bad_function():
    with open("file.txt") as f:  # Blocking!
        data = f.read()
    return data
```

✅ **DO: Use async I/O**
```python
# CORRECT:
import aiofiles

async def good_function():
    async with aiofiles.open("file.txt") as f:
        data = await f.read()
    return data
```

### ❌ DON'T: Ignore type hints
```python
# WRONG:
def process(data):
    return data.upper()
```

✅ **DO: Always add type hints**
```python
# CORRECT:
def process(data: str) -> str:
    """Process string data."""
    return data.upper()
```

### ❌ DON'T: Catch generic exceptions
```python
# WRONG:
try:
    risky_operation()
except:  # Too broad!
    pass
```

✅ **DO: Catch specific exceptions**
```python
# CORRECT:
try:
    risky_operation()
except FileNotFoundError:
    logger.error("File not found")
    raise
except PermissionError:
    logger.error("Permission denied")
    raise
```

---

## 🔧 Development Workflow

### 1. Feature Development
```bash
# 1. Create feature branch
git checkout -b feature/audio-metadata-preservation

# 2. Write test first (TDD)
# tests/unit/test_metadata.py

# 3. Run test (should fail)
pytest tests/unit/test_metadata.py -v

# 4. Implement minimum code to pass
# src/media_refinery/audio/metadata.py

# 5. Run test (should pass)
pytest tests/unit/test_metadata.py -v

# 6. Refactor if needed

# 7. Check coverage
pytest --cov=src/media_refinery/audio --cov-report=term-missing

# 8. Run all tests
pytest

# 9. Lint and format
make precommit

# 10. Commit
git add .
git commit -m "feat: add metadata preservation for audio conversion"

# 11. Push and create PR
git push origin feature/audio-metadata-preservation
```

### 2. Code Review Checklist
Before submitting PR, verify:
- [ ] Tests written BEFORE implementation
- [ ] All tests pass (`pytest`)
- [ ] Coverage >85% (`pytest --cov`)
- [ ] Type hints on all functions
- [ ] Docstrings on all public functions
- [ ] No blocking I/O in async functions
- [ ] Specific exception handling
- [ ] Structured logging used
- [ ] No hardcoded paths (use pathlib)
- [ ] Pydantic models for config
- [ ] Pre-commit hooks pass (`make precommit`)

---

## 🎯 File/Module Specific Instructions

### When Working on Audio Conversion (`src/media_refinery/audio/`)
1. Always use asyncio for FFmpeg subprocess calls
2. Validate audio format before processing
3. Calculate and store SHA256 checksums for all outputs
4. Preserve metadata (ID3v2 → Vorbis comments)
5. Support dry-run mode (preview without modification)
6. Log all operations with structured logging

### When Working on Video Conversion (`src/media_refinery/video/`)
1. Detect content type (B&W, comedy, documentary)
2. Apply appropriate encoding profiles (CRF values)
3. Preserve multi-audio tracks
4. Preserve subtitles
5. Validate output with FFprobe
6. Support hardware acceleration when available

### When Working on Batch Processing (`src/media_refinery/processor/`)
1. Use WorkerPool with configurable concurrency
2. Track progress with callbacks
3. Handle partial failures gracefully
4. Support cancellation via asyncio
5. Generate summary reports
6. Implement recovery from interruption

### When Working on State Management (`src/media_refinery/state/`)
1. Store checksums for idempotency
2. Detect already-processed files
3. Handle checksum mismatches (corruption)
4. Use JSON for state persistence
5. Implement cleanup for old state files

### When Working on API (`app/api/`)
1. Use FastAPI dependency injection
2. Validate input with Pydantic schemas
3. Return appropriate HTTP status codes
4. Include error details in responses
5. Document all endpoints with docstrings
6. Add OpenAPI examples

### When Working on Database Models (`app/models/`)
1. Use SQLAlchemy async
2. Define relationships clearly
3. Add indexes for queries
4. Include created_at/updated_at timestamps
5. Use enums for status fields
6. Write Alembic migrations for schema changes

---

## 🚀 Quick Reference Commands

```bash
# Development
make install          # Install dependencies
make dev             # Run in development mode
make test            # Run all tests
make test-unit       # Run unit tests only
make test-integration # Run integration tests
make coverage        # Generate coverage report
make precommit       # Run linters and formatters

# Docker
make docker-build    # Build Docker image
make docker-run      # Run in Docker
make docker-compose-up   # Start all services

# Database
make migrate         # Run Alembic migrations
make migrate-create  # Create new migration
make db-reset        # Reset database

# Quality
make lint           # Run linters (ruff, mypy)
make format         # Format code (black, isort)
make type-check     # Run mypy type checking
```

---

## 📚 Additional Resources

- [Architecture Documentation](docs/ARCHITECTURE.md)
- [Product Vision](docs/PRODUCT_VISION.md)
- [Contributing Guide](docs/CONTRIBUTING.md)
- [Security Policy](SECURITY.md)
- [FAQ](FAQ.md)

---

## ⚡ Summary for GPT-4.1

When working on Media-Refinery:

1. **ALWAYS write tests first** (TDD is non-negotiable)
2. **ALWAYS use type hints** on all functions
3. **ALWAYS use async/await** for I/O operations
4. **ALWAYS use Pydantic** for configuration
5. **ALWAYS use pathlib.Path** for file paths
6. **ALWAYS use structured logging** with context
7. **ALWAYS handle specific exceptions** (not generic)
8. **Target >85% test coverage**, 100% for critical paths

**Test Pyramid**: 70% unit / 20% integration / 10% E2E

**Quality Gates**:
- All tests must pass
- Type checking must pass (mypy)
- Linting must pass (ruff)
- Coverage must be >85%

**When in doubt**: Look at existing code in the same directory for patterns to follow.
