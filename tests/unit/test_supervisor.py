import asyncio
from unittest.mock import MagicMock, AsyncMock
from app.core.supervisor import DaemonSupervisor


def test_supervisor_backoff(monkeypatch):
    orchestrator = MagicMock()
    reporting_service = AsyncMock()
    supervisor = DaemonSupervisor(orchestrator, reporting_service, "/tmp", "/tmp")
    supervisor._backoff = 2
    called = []

    async def fake_sleep(secs):
        called.append(secs)

    monkeypatch.setattr("asyncio.sleep", fake_sleep)
    asyncio.run(supervisor._backoff_wait())
    assert called[0] == 2
    assert supervisor._backoff == 4


def test_supervisor_health_checks_disk_full(monkeypatch, tmp_path):
    orchestrator = MagicMock()
    reporting_service = AsyncMock()
    supervisor = DaemonSupervisor(
        orchestrator, reporting_service, str(tmp_path), str(tmp_path)
    )
    monkeypatch.setattr("os.path.exists", lambda p: True)
    monkeypatch.setattr("shutil.disk_usage", lambda p: (100, 96, 4))  # 4% free
    called = []

    async def fake_backoff():
        called.append(True)

    supervisor._backoff_wait = fake_backoff
    asyncio.run(supervisor._health_checks())
    assert not supervisor.orchestrator.running
    assert called


def test_supervisor_health_checks_path_missing(monkeypatch, tmp_path):
    orchestrator = MagicMock()
    # Ensure .running property returns True before, then False after health check
    running_state = {"value": True}
    type(orchestrator).running = property(lambda self: running_state["value"])
    reporting_service = AsyncMock()
    supervisor = DaemonSupervisor(
        orchestrator, reporting_service, str(tmp_path), str(tmp_path)
    )
    monkeypatch.setattr("os.path.exists", lambda p: False)
    called = []

    async def fake_backoff():
        called.append(True)
        running_state["value"] = False

    supervisor._backoff_wait = fake_backoff
    asyncio.run(supervisor._health_checks())
    assert not supervisor.orchestrator.running
    assert called
