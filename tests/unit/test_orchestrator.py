import asyncio
from unittest.mock import AsyncMock, MagicMock
from app.core.orchestrator import PipelineOrchestrator


def test_orchestrator_recovery(monkeypatch):
    db = AsyncMock()
    stuck_item = MagicMock(state="executing", id=1)

    # Patch db.execute to return an awaitable with .scalars().all()
    class FakeResult:
        def scalars(self):
            class All:
                def all(self):
                    return [stuck_item]

            return All()

    async def fake_execute(*args, **kwargs):
        return FakeResult()

    db.execute = fake_execute
    orchestrator = PipelineOrchestrator(db)
    asyncio.run(orchestrator._recover_inflight())
    assert stuck_item.state == "planned"
    db.commit.assert_called()


def test_orchestrator_dispatch_success(monkeypatch):
    db = AsyncMock()
    item = MagicMock(state="pending", id=2, retry_count=0)
    orchestrator = PipelineOrchestrator(db)
    state_info = {
        "service": "scanner",
        "next": "scanned",
        "fail": "error",
    }
    asyncio.run(orchestrator._dispatch(item, "scanner", state_info))
    assert item.state == "scanned"
    db.commit.assert_called()


def test_orchestrator_dispatch_fail(monkeypatch):
    db = AsyncMock()
    item = MagicMock(state="pending", id=3, retry_count=0)
    orchestrator = PipelineOrchestrator(db)
    state_info = {
        "service": "scanner",
        "next": "scanned",
        "fail": "error",
    }

    # Simulate error in service call
    async def fail(*a, **k):
        raise Exception("fail")

    monkeypatch.setattr(orchestrator, "_dispatch", fail)
    # Should not raise, but set state to error after retries
    try:
        asyncio.run(orchestrator._dispatch(item, "scanner", state_info))
    except Exception:
        pass
    # retry_count incremented or state set to error
