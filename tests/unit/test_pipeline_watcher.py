import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.pipeline import PipelineCoordinator
from app.core.watcher import DebounceHandler, InputWatcher
from app.models.media import FileState, MediaItem


def _factory(session):
    factory = MagicMock()
    factory.return_value.__aenter__.return_value = session
    factory.return_value.__aexit__.return_value = False
    return factory


async def _add_item(session, path, state=FileState.pending):
    item = MediaItem(source_path=path, state=state)
    session.add(item)
    await session.commit()
    return item


@pytest.mark.asyncio
async def test_process_unknown_and_not_pending_are_skipped(async_session):
    coord = PipelineCoordinator(_factory(async_session))
    coord.scanner.run = AsyncMock()
    await coord.process("missing")
    done = await _add_item(async_session, "/a.mkv", FileState.scanned)
    await coord.process(done.id)
    coord.scanner.run.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_pending_moves_to_scanning_and_runs_scanner(async_session):
    item = await _add_item(async_session, "/b.mkv")
    coord = PipelineCoordinator(_factory(async_session))
    coord.scanner.run = AsyncMock()
    await coord.process(item.id)
    assert item.state == FileState.scanning
    coord.scanner.run.assert_awaited_once_with(item.id)


@pytest.mark.asyncio
async def test_process_scanner_failure_marks_error(async_session):
    item = await _add_item(async_session, "/c.mkv")
    coord = PipelineCoordinator(_factory(async_session))
    coord.scanner.run = AsyncMock(side_effect=RuntimeError("ffprobe died"))
    await coord.process(item.id)
    assert item.state == FileState.error
    assert item.error_log == "ffprobe died"


@pytest.mark.asyncio
async def test_coordinator_worker_loop_drains_queue():
    coord = PipelineCoordinator(MagicMock())
    seen = []

    async def fake_process(media_id):
        seen.append(media_id)
        coord.running = False

    coord.process = fake_process
    await coord.start()
    await coord.enqueue("m1")
    await asyncio.sleep(0.05)
    await coord.stop()
    assert seen == ["m1"]


def test_debounce_handler_ignores_dirs_and_temp_files():
    queue = {}
    handler = DebounceHandler(queue, loop=None)
    handler.on_created(SimpleNamespace(is_directory=True, src_path="/in/d"))
    handler.on_created(SimpleNamespace(is_directory=False, src_path="/in/a.part"))
    handler.on_created(SimpleNamespace(is_directory=False, src_path="/in/a.mkv"))
    handler.on_moved(SimpleNamespace(is_directory=False, dest_path="/in/b.tmp"))
    handler.on_moved(SimpleNamespace(is_directory=False, dest_path="/in/b.mkv"))
    assert set(queue) == {"/in/a.mkv", "/in/b.mkv"}


@pytest.mark.asyncio
async def test_startup_scan_skips_excluded(tmp_path, async_session):
    (tmp_path / "ok.mkv").write_bytes(b"x")
    (tmp_path / "skip.part").write_bytes(b"x")
    watcher = InputWatcher(str(tmp_path), _factory(async_session))
    await watcher.startup_scan()
    assert [p.rsplit("/", 1)[-1] for p in watcher.processing_queue] == ["ok.mkv"]


@pytest.mark.asyncio
async def test_insert_if_new_inserts_once_and_enqueues(async_session, tmp_path):
    f = tmp_path / "a.mkv"
    f.write_bytes(b"x")
    coordinator = SimpleNamespace(enqueue=AsyncMock())
    watcher = InputWatcher("/in", _factory(async_session), coordinator=coordinator)
    await watcher.insert_if_new(str(f))
    await watcher.insert_if_new(str(f))
    coordinator.enqueue.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_queue_inserts_stable_files_and_drops_missing(
    tmp_path, async_session, monkeypatch
):
    monkeypatch.setattr("app.core.watcher.STABILITY_WINDOW", 0)
    stable = tmp_path / "stable.mkv"
    stable.write_bytes(b"x")
    watcher = InputWatcher(str(tmp_path), _factory(async_session))
    watcher.processing_queue[str(stable)] = 0
    watcher.processing_queue[str(tmp_path / "gone.mkv")] = 0
    watcher.insert_if_new = AsyncMock()
    calls = 0

    async def fake_sleep(secs):
        nonlocal calls
        calls += 1
        if calls == 2:  # first pass records the signature, second inserts
            raise asyncio.CancelledError

    with patch("asyncio.sleep", fake_sleep), pytest.raises(asyncio.CancelledError):
        await watcher.process_queue()
    watcher.insert_if_new.assert_awaited_once_with(str(stable))
    assert not watcher.processing_queue


@pytest.mark.asyncio
async def test_run_and_stop_start_observer(tmp_path, async_session):
    watcher = InputWatcher(str(tmp_path), _factory(async_session))
    watcher.process_queue = AsyncMock()
    watcher.run()
    await asyncio.sleep(0)
    watcher.stop()
    watcher.process_queue.assert_awaited_once()


async def _run_passes(watcher, passes):
    calls = 0

    async def fake_sleep(secs):
        nonlocal calls
        calls += 1
        if calls == passes:
            raise asyncio.CancelledError

    with patch("asyncio.sleep", fake_sleep), pytest.raises(asyncio.CancelledError):
        await watcher.process_queue()


@pytest.mark.asyncio
async def test_failed_import_is_retried_then_dropped(
    tmp_path, async_session, monkeypatch
):
    monkeypatch.setattr("app.core.watcher.STABILITY_WINDOW", 0)
    f = tmp_path / "a.mkv"
    f.write_bytes(b"x")
    watcher = InputWatcher(str(tmp_path), _factory(async_session))
    watcher.processing_queue[str(f)] = 0
    watcher.insert_if_new = AsyncMock(side_effect=[OSError("db"), None])
    await _run_passes(watcher, 6)
    assert watcher.insert_if_new.await_count == 2  # failed once, retried, succeeded
    assert not watcher.processing_queue

    watcher.processing_queue[str(f)] = 0
    watcher.insert_if_new = AsyncMock(side_effect=OSError("always"))
    await _run_passes(watcher, 12)
    assert watcher.insert_if_new.await_count == 3  # MAX_IMPORT_ATTEMPTS, then dropped
    assert not watcher.processing_queue


@pytest.mark.asyncio
async def test_event_during_import_is_not_lost(tmp_path, async_session, monkeypatch):
    monkeypatch.setattr("app.core.watcher.STABILITY_WINDOW", 0)
    f = tmp_path / "a.mkv"
    f.write_bytes(b"x")
    watcher = InputWatcher(str(tmp_path), _factory(async_session))
    watcher.processing_queue[str(f)] = 0

    async def import_with_new_event(path):
        watcher.processing_queue[path] = 99  # second write event mid-import

    watcher.insert_if_new = AsyncMock(side_effect=import_with_new_event)
    await _run_passes(watcher, 2)
    assert str(f) in watcher.processing_queue


@pytest.mark.asyncio
async def test_import_file_rejects_file_that_grew_while_hashing(
    tmp_path, async_session, monkeypatch
):
    from app.core import watcher as w

    f = tmp_path / "a.mkv"
    f.write_bytes(b"x")
    real_hash = w.content_hash

    def growing_hash(path):
        digest = real_hash(path)
        with open(path, "ab") as fh:
            fh.write(b"more")
        return digest

    monkeypatch.setattr(w, "content_hash", growing_hash)
    with pytest.raises(w.FileChangedError):
        await w.import_file(str(f), _factory(async_session), MagicMock())


@pytest.mark.asyncio
async def test_watcher_uses_running_loop_and_scan_runs_off_loop(
    tmp_path, async_session
):
    watcher = InputWatcher(str(tmp_path), _factory(async_session))
    assert watcher.loop is asyncio.get_running_loop()
    with patch("asyncio.to_thread", wraps=asyncio.to_thread) as spy:
        await watcher.startup_scan()
    spy.assert_called_once()
