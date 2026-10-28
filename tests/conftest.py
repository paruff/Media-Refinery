import asyncio
import json
import os
import subprocess
import tempfile

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# One temp-file DB for the whole run (":memory:" is per-connection and per-loop).
os.environ["DATABASE_URL"] = (
    f"sqlite+aiosqlite:///{tempfile.mkdtemp(prefix='mr-test-')}/test.sqlite"
)

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
    Skip this mock for integration and corpus tests (they need real FFmpeg).
    """
    # Skip mocking for integration tests
    if any(d in str(request.fspath) for d in ("integration", "corpus")):
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
    yield


@pytest.fixture
def mock_ffprobe():
    """
    Returns a standard ffprobe JSON for H.264/DTS MKV files.
    """
    return FFPROBE_MKV_H264_DTS


@pytest.fixture(scope="session", autouse=True)
def create_app_tables():
    """Create the app schema in the temp DB before any test runs."""
    import app.models.saga  # noqa: F401
    from app.core.database import init_db

    asyncio.run(init_db())


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


@pytest.fixture
def make_audio():
    """Return a factory that renders a short real tone with ffmpeg (skips if absent)."""
    import shutil

    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not installed")

    def _make(path, seconds=1):
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency=440:duration={seconds}",
                str(path),
            ],
            check=True,
        )
        return path

    return _make


def pytest_collection_modifyitems(config, items):
    """Skip real-ffmpeg integration tests where ffmpeg is absent (CI sets REQUIRE_FFMPEG=1)."""
    import shutil

    if shutil.which("ffmpeg") or os.environ.get("REQUIRE_FFMPEG"):
        return
    skip = pytest.mark.skip(reason="ffmpeg not installed (see `make docker-test`)")
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(skip)
