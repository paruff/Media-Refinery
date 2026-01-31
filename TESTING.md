# Testing Guide

## Test Philosophy
Media-Refinery follows **strict TDD** (Test-Driven Development):
1. Write test first (it fails)
2. Write minimum code to pass
3. Refactor
4. Repeat

## Test Structure
tests/
├── unit/           # Fast, isolated tests (70% of tests)
├── integration/    # Real dependency tests (20% of tests)
├── e2e/           # Full workflow tests (10% of tests)
└── features/      # BDD tests (Gherkin/Behave)

## Running Tests
```bash
# All tests
pytest

# Specific test type
pytest tests/unit/
pytest tests/integration/
pytest tests/e2e/

# With coverage
pytest --cov=app --cov=src --cov-report=term-missing

# Watch mode (auto-rerun on changes)
pytest-watch

# BDD tests
behave tests/features/
```

## Writing Tests

### Unit Test Example
```python
import pytest
from pathlib import Path
from media_refinery.audio.converter import AudioConverter

class TestAudioConverter:
    @pytest.fixture
    def converter(self):
        return AudioConverter(format="flac")

    def test_build_command_basic(self, converter):
        """Test FFmpeg command building."""
        cmd = converter.build_ffmpeg_command(
            Path("input.mp3"),
            Path("output.flac")
        )

        assert "ffmpeg" in cmd
        assert "-i" in cmd
        assert "input.mp3" in cmd
```

### Integration Test Example
```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_ffmpeg_conversion_real():
    """Test real FFmpeg conversion."""
    converter = AudioConverter()
    result = await converter.convert_file(
        Path("testdata/sample.mp3"),
        Path("/tmp/output.flac")
    )

    assert result.success
    assert Path("/tmp/output.flac").exists()
```

### Async Test Example
```python
@pytest.mark.asyncio
async def test_async_function():
    """Test async operation."""
    result = await some_async_function()
    assert result is not None
```

## Test Coverage Requirements
- **Overall**: >85%
- **Critical paths** (checksums, file ops): 100%
- **New features**: >90%

## Mocking
```python
from unittest.mock import Mock, AsyncMock, patch

@pytest.mark.asyncio
async def test_with_mock():
    """Test with mocked dependency."""
    mock_ffmpeg = AsyncMock(return_value="success")

    with patch('media_refinery.audio.converter.execute_ffmpeg', mock_ffmpeg):
        result = await convert_file(Path("input.mp3"))

    assert result.success
    mock_ffmpeg.assert_called_once()
```

## Fixtures
```python
@pytest.fixture
def temp_audio_file(tmp_path: Path) -> Path:
    """Create temporary audio file."""
    audio_file = tmp_path / "test.mp3"
    audio_file.write_bytes(b"dummy mp3 data")
    return audio_file

@pytest.fixture
async def async_converter():
    """Create and cleanup async converter."""
    converter = AsyncConverter()
    await converter.initialize()

    yield converter

    await converter.cleanup()
