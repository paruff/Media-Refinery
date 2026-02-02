import asyncio
import json
import pytest
import pytest_asyncio
import subprocess
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.media import Base

pytest_plugins = ["pytest_mock"]

# Standard ffprobe JSON for H.264/DTS MKV
FFPROBE_MKV_H264_DTS = {
    "streams": [
        {
            "index": 0,
            "codec_name": "h264",
            "codec_type": "video",
            "width": 1920,
            "height": 1080,
            "r_frame_rate": "24/1",
        },
        {"index": 1, "codec_name": "dts", "codec_type": "audio", "channels": 6},
    ],
    "format": {
        "filename": "test.mkv",
        "nb_streams": 2,
        "format_name": "matroska,webm",
        "duration": "3600.0",
    },
}


@pytest.fixture(autouse=True)
def patch_create_subprocess_exec(mocker, request):
    """
    Globally patch asyncio.create_subprocess_exec to intercept all subprocess calls.
    Skip this mock for integration tests (they need real FFmpeg).
    """
    # Skip mocking for integration tests
    if "integration" in str(request.fspath):
        yield
        return

    async def _mocked_create_subprocess_exec(*args, **kwargs):
        class DummyProcess:
            def __init__(self):
                self.returncode = 0
                self.stdout = asyncio.StreamReader()
                self.stderr = asyncio.StreamReader()

            async def communicate(self):
                # Simulate ffprobe output if called
                if "ffprobe" in args[0]:
                    output = json.dumps(FFPROBE_MKV_H264_DTS).encode()
                    self.stdout.feed_data(output)
                    self.stdout.feed_eof()
                    self.stderr.feed_eof()
                    return (output, b"")
                # Simulate ffmpeg or other binaries
                self.stdout.feed_eof()
                self.stderr.feed_eof()
                return (b"", b"")

        return DummyProcess()

    mocker.patch(
        "asyncio.create_subprocess_exec", side_effect=_mocked_create_subprocess_exec
    )


@pytest.fixture
def mock_ffprobe():
    """
    Returns a standard ffprobe JSON for H.264/DTS MKV files.
    """
    return FFPROBE_MKV_H264_DTS


@pytest_asyncio.fixture(scope="session", autouse=True)
def apply_alembic_migrations():
    """Ensure all Alembic migrations are applied before tests run."""
    import shutil

    # Only run alembic if the command is available
    if shutil.which("alembic") is not None:
        subprocess.run(["alembic", "upgrade", "head"], check=True)


@pytest_asyncio.fixture(scope="function")
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session_factory = sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    async with async_session_factory() as session:
        yield session
    await engine.dispose()
