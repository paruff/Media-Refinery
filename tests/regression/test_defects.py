"""Regression tests pinning the known defects D1-D9 (spec.md section 1)."""

import ast
import asyncio
import hashlib
import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import func, select

from app.core.pipeline import PipelineCoordinator
from app.core.scanner import ScannerService
from app.core.watcher import DebounceHandler, InputWatcher
from app.models.media import FileState, MediaItem

pytestmark = pytest.mark.regression

APP_DIR = Path(__file__).resolve().parents[2] / "app"


def _factory(session):
    factory = MagicMock()
    factory.return_value.__aenter__.return_value = session
    factory.return_value.__aexit__.return_value = False
    return factory


def _ffprobe(mocker, streams):
    payload = json.dumps({"streams": streams, "format": {"format_name": "x"}})

    async def fake_exec(*args, **kwargs):
        proc = MagicMock()
        proc.returncode = 0
        proc.communicate = AsyncMock(return_value=(payload.encode(), b""))
        return proc

    mocker.patch("asyncio.create_subprocess_exec", side_effect=fake_exec)


AUDIO_ONLY = [{"codec_type": "audio", "codec_name": "mp3", "channels": 2}]


def _spy_fingerprints(mocker, audio="afp", video="vfp"):
    return (
        mocker.patch(
            "app.services.fingerprint_service.FingerprintService.fingerprint_audio",
            return_value=audio,
        ),
        mocker.patch(
            "app.services.fingerprint_service.FingerprintService.fingerprint_video",
            return_value=video,
        ),
    )


# --- D1 ---------------------------------------------------------------------
@pytest.mark.asyncio
async def test_d1_audio_file_gets_audio_fingerprint_not_video(
    async_session, tmp_path, mocker
):
    song = tmp_path / "song.mp3"
    song.write_bytes(b"x")
    item = MediaItem(source_path=str(song), state=FileState.scanning)
    async_session.add(item)
    await async_session.commit()
    _ffprobe(mocker, AUDIO_ONLY)
    audio, video = _spy_fingerprints(mocker)

    await ScannerService(_factory(async_session)).run(item.id)

    audio.assert_called_once()
    video.assert_not_called()
    assert item.audio_fingerprint == "afp"
    assert item.video_fingerprint is None


# --- D2 ---------------------------------------------------------------------
@pytest.mark.asyncio
async def test_d2_multiple_duplicate_matches_do_not_raise(
    async_session, tmp_path, mocker
):
    song = tmp_path / "new.mp3"
    song.write_bytes(b"x")
    for n in (1, 2):
        async_session.add(
            MediaItem(source_path=f"/lib/{n}.mp3", audio_fingerprint="dup")
        )
    item = MediaItem(source_path=str(song), state=FileState.scanning)
    async_session.add(item)
    await async_session.commit()
    _ffprobe(mocker, AUDIO_ONLY)
    _spy_fingerprints(mocker, audio="dup")

    await ScannerService(_factory(async_session)).run(item.id)  # must not raise

    assert item.state == FileState.error
    assert "Duplicate audio fingerprint" in item.error_log


# --- D3 ---------------------------------------------------------------------
def _write_video(folder, frame_for):
    """Write 50 frames as a PNG sequence (cv2 reads `f_%03d.png` as a video; no ffmpeg needed)."""
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    folder.mkdir()
    for i in range(50):
        frame = np.zeros((64, 64, 3), dtype=np.uint8)  # black leader
        if i >= 5:
            frame = frame_for(np, i)
        cv2.imwrite(str(folder / f"f_{i:03d}.png"), frame)
    return folder / "f_%03d.png"


def test_d3_black_leader_videos_with_different_content_do_not_collide(tmp_path):
    from app.services.fingerprint_service import FingerprintService

    def gradient(np, i):
        return np.tile(np.linspace(0, 255, 64, dtype=np.uint8), (64, 1))[
            ..., None
        ].repeat(3, 2)

    def stripes(np, i):
        frame = np.zeros((64, 64, 3), dtype=np.uint8)
        frame[:, ::8] = 255
        return frame

    a = _write_video(tmp_path / "a", gradient)
    b = _write_video(tmp_path / "b", stripes)
    a2 = _write_video(tmp_path / "a2", gradient)

    fp_a = FingerprintService.fingerprint_video(str(a))
    assert fp_a is not None
    assert fp_a != FingerprintService.fingerprint_video(str(b))
    assert fp_a == FingerprintService.fingerprint_video(str(a2))
    assert len(fp_a.split("-")) >= 6  # duration + >=5 frame hashes


# --- D4 ---------------------------------------------------------------------
@pytest.mark.asyncio
async def test_d4_identity_is_content_hash_and_a_rename_is_a_move(
    async_session, tmp_path
):
    old = tmp_path / "old.mkv"
    old.write_bytes(b"same bytes")
    watcher = InputWatcher(str(tmp_path), _factory(async_session))
    await watcher.insert_if_new(str(old))

    new = old.rename(tmp_path / "renamed.mkv")
    await watcher.insert_if_new(str(new))

    rows = (await async_session.execute(select(MediaItem))).scalars().all()
    assert len(rows) == 1
    assert rows[0].id == hashlib.sha256(b"same bytes").hexdigest()
    assert rows[0].source_path == str(new)


# --- D5 ---------------------------------------------------------------------
@pytest.mark.asyncio
async def test_d5_watcher_events_are_handed_to_the_loop_thread():
    loop = asyncio.get_running_loop()
    loop_thread = threading.get_ident()
    writers = []

    class RecordingQueue(dict):
        def __setitem__(self, key, value):
            writers.append(threading.get_ident())
            super().__setitem__(key, value)

    queue = RecordingQueue()
    handler = DebounceHandler(queue, loop)
    event = SimpleNamespace(is_directory=False, src_path="/in/a.mkv")
    await asyncio.to_thread(handler.on_created, event)
    await asyncio.sleep(0.05)

    assert "/in/a.mkv" in queue
    assert writers == [loop_thread]


@pytest.mark.asyncio
async def test_d5_stability_check_does_not_block_files_serially(
    async_session, tmp_path, monkeypatch
):
    monkeypatch.setattr("app.core.watcher.STABILITY_WINDOW", 0.2)
    monkeypatch.setattr("app.core.watcher.POLL_INTERVAL", 0.05)
    watcher = InputWatcher(str(tmp_path), _factory(async_session))
    watcher.insert_if_new = AsyncMock()
    for n in range(5):
        path = tmp_path / f"{n}.mkv"
        path.write_bytes(b"x")
        watcher.processing_queue[str(path)] = time.time()

    start = time.monotonic()
    task = asyncio.create_task(watcher.process_queue())
    while watcher.insert_if_new.await_count < 5 and time.monotonic() - start < 3:
        await asyncio.sleep(0.02)
    elapsed = time.monotonic() - start
    task.cancel()

    assert watcher.insert_if_new.await_count == 5
    assert elapsed < 0.8  # serial blocking would need >= 5 * 0.2s


# --- D6 ---------------------------------------------------------------------
def _plan(tmp_path, **extra):
    src = tmp_path / "source.mkv"
    src.write_bytes(b"source bytes")
    return {
        "id": "d6plan",
        "media_item_id": "d6item",
        "source_path": str(src),
        "target_path": str(tmp_path / "out" / "final.mkv"),
        **extra,
    }, src


def test_d6_transcode_runs_ffmpeg_on_the_source_not_the_target(tmp_path, mocker):
    from app.services.execution_service import _execute_normalization_plan

    plan, src = _plan(tmp_path, needs_transcode=True)
    calls = []

    async def fake_exec(*args, **kwargs):
        calls.append(args)
        out = Path(args[-1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"encoded")
        proc = MagicMock()
        proc.returncode = 0
        proc.communicate = AsyncMock(return_value=(b"", b""))
        return proc

    mocker.patch("asyncio.create_subprocess_exec", side_effect=fake_exec)
    _execute_normalization_plan(plan)

    assert calls, "ffmpeg was never invoked"
    argv = calls[0]
    assert "-version" not in argv
    assert argv[argv.index("-i") + 1] == str(src)
    assert argv[-1] != plan["target_path"]  # written to a temp name, then renamed
    assert Path(plan["target_path"]).read_bytes() == b"encoded"


def test_d6_execution_failures_propagate(tmp_path, mocker):
    from app.services.execution_service import (
        _execute_normalization_plan,
        execute_normalization_plan,
    )

    plan, _ = _plan(tmp_path, needs_transcode=True)

    async def failing_exec(*args, **kwargs):
        proc = MagicMock()
        proc.returncode = 1
        proc.communicate = AsyncMock(return_value=(b"", b"boom"))
        return proc

    mocker.patch("asyncio.create_subprocess_exec", side_effect=failing_exec)
    with pytest.raises(RuntimeError, match="ffmpeg failed"):
        _execute_normalization_plan(plan)
    with pytest.raises(RuntimeError):
        execute_normalization_plan(plan)
    assert not Path(plan["target_path"]).exists()


# --- D7 ---------------------------------------------------------------------
def _exec_plan(src, dst):
    return SimpleNamespace(
        id="p",
        needs_transcode=False,
        media_item=SimpleNamespace(source_path=str(src), state=None),
        target_path=str(dst),
        execution_log="",
        plan_status=None,
    )


@pytest.mark.asyncio
async def test_d7_execute_plan_keeps_the_original(tmp_path):
    from app.services.execution_service import ExecutionService

    src = tmp_path / "in" / "a.flac"
    src.parent.mkdir()
    src.write_bytes(b"audio")
    dst = tmp_path / "out" / "a.flac"
    plan = _exec_plan(src, dst)

    await ExecutionService(AsyncMock()).execute_plan(plan)

    assert src.read_bytes() == b"audio"  # R-SAFE-1: original untouched
    assert dst.read_bytes() == b"audio"


@pytest.mark.asyncio
async def test_d7_execute_plan_reports_failure_instead_of_success(tmp_path):
    from app.services.execution_service import ExecutionService

    plan = _exec_plan(tmp_path / "missing.flac", tmp_path / "out" / "a.flac")

    with pytest.raises(FileNotFoundError):
        await ExecutionService(AsyncMock()).execute_plan(plan)

    assert "Moved to output" not in plan.execution_log
    assert plan.plan_status == "failed"


# --- D8 ---------------------------------------------------------------------
@pytest.mark.asyncio
async def test_d8_pipeline_timestamps_are_tz_aware_and_stop_cancels_worker(
    async_session,
):
    item = MediaItem(source_path="/x.mkv", state=FileState.pending)
    async_session.add(item)
    await async_session.commit()
    coord = PipelineCoordinator(_factory(async_session))
    coord.scanner.run = AsyncMock()
    await coord.process(item.id)
    assert item.updated_at.tzinfo is not None

    await coord.start()
    worker = coord._worker
    await coord.stop()
    assert worker.done()


def test_d8_no_naive_utcnow_stub_scanner_or_print_in_app():
    import app.core.pipeline as pipeline

    assert not hasattr(pipeline, "MediaScanner")
    for path in APP_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "utcnow":
                pytest.fail(f"{path}:{node.lineno} uses naive utcnow()")
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "print"
            ):
                pytest.fail(f"{path}:{node.lineno} calls print()")


# --- D9 ---------------------------------------------------------------------
@pytest.mark.asyncio
async def test_d9_lifespan_replaces_on_event_and_logs_outside_cwd(
    tmp_path, monkeypatch
):
    from app.core.config import settings
    from app.main import app

    assert app.router.on_startup == [] and app.router.on_shutdown == []

    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    monkeypatch.setattr(settings, "INPUT_DIR", str(tmp_path / "input"))
    monkeypatch.setattr(settings, "LOG_DIR", str(tmp_path / "logs"))
    (tmp_path / "input").mkdir()

    async with app.router.lifespan_context(app):
        assert app.state.watcher is not None
        assert app.state.orchestrator is not None

    assert not (workdir / "rotation.log").exists()
    assert (tmp_path / "logs" / "rotation.log").exists()


# --- R-SAFE-1 (issue G1: _prune_old_errors must not delete rows) -------------
@pytest.mark.asyncio
async def test_prune_old_errors_keeps_media_item_rows(async_session):
    from datetime import UTC, datetime, timedelta

    from app.services.validator_service import ValidatorService

    old = datetime.now(UTC) - timedelta(days=90)
    item = MediaItem(
        source_path="/old.mkv", state=FileState.error, error_log="boom", updated_at=old
    )
    async_session.add(item)
    await async_session.commit()

    service = ValidatorService.__new__(ValidatorService)
    service.db = async_session
    await service._prune_old_errors()

    count = (await async_session.execute(select(func.count(MediaItem.id)))).scalar_one()
    assert count == 1
