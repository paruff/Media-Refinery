import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.supervisor import DaemonSupervisor


@pytest.fixture
def sup(tmp_path):
    orch = MagicMock()
    orch.running = False
    return DaemonSupervisor(orch, MagicMock(), str(tmp_path), str(tmp_path))


@pytest.mark.asyncio
async def test_shutdown_sets_flag_and_stops_orchestrator(sup):
    sup.orchestrator.running = True
    await sup.shutdown()
    assert sup._shutdown.is_set()
    assert sup.orchestrator.running is False


@pytest.mark.asyncio
async def test_backoff_doubles_and_caps(sup):
    sup._max_backoff = 4
    with patch("asyncio.sleep", AsyncMock()) as sleep:
        for _ in range(4):
            await sup._backoff_wait()
    assert [c.args[0] for c in sleep.await_args_list] == [1, 2, 4, 4]


@pytest.mark.asyncio
async def test_health_ok_enables_orchestrator(sup):
    await sup._health_checks()
    assert sup.orchestrator.running is True


@pytest.mark.asyncio
async def test_health_missing_path_backs_off(sup):
    sup.staging_dir = "/definitely/not/here"
    with patch("asyncio.sleep", AsyncMock()):
        await sup._health_checks()
    assert sup.orchestrator.running is False
    assert sup._backoff == 2


@pytest.mark.asyncio
async def test_health_disk_full_pauses(sup):
    with (
        patch("shutil.disk_usage", return_value=(100, 99, 1)),
        patch("asyncio.sleep", AsyncMock()),
    ):
        await sup._health_checks()
    assert sup.orchestrator.running is False


@pytest.mark.asyncio
async def test_heartbeat_fires_only_when_due(sup):
    summary = MagicMock()
    summary.json.return_value = "{}"
    sup.reporting_service.get_summary = AsyncMock(return_value=summary)
    sup._last_heartbeat = datetime.now(UTC)
    await sup._maybe_heartbeat()
    sup.reporting_service.get_summary.assert_not_awaited()
    sup._last_heartbeat = datetime.now(UTC) - timedelta(hours=2)
    await sup._maybe_heartbeat()
    sup.reporting_service.get_summary.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_exits_cleanly_after_shutdown(sup, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    async def stop():
        await sup.shutdown()

    sup.orchestrator.run_forever = AsyncMock(side_effect=stop)
    with pytest.raises(SystemExit) as exc:
        await asyncio.wait_for(sup.run(), 3)
    assert exc.value.code == 0


@pytest.mark.asyncio
async def test_run_logs_crash_and_backs_off(sup, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    async def boom():
        await sup.shutdown()
        raise RuntimeError("crash")

    sup.orchestrator.run_forever = AsyncMock(side_effect=boom)
    with patch("asyncio.sleep", AsyncMock()), pytest.raises(SystemExit):
        await asyncio.wait_for(sup.run(), 3)
    assert "crash" in (tmp_path / "crash.log").read_text()
