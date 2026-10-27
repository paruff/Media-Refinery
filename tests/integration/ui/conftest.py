"""Live uvicorn + Playwright harness for the G10 web UI tests."""

import asyncio
import threading
import time
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest
import uvicorn

from app.core.config import settings
from app.core.database import get_async_session
from app.core.orchestrator import PipelineOrchestrator
from app.main import app
from tests.pipeline_helpers import make_config, make_session_factory

Setup = Callable[..., "asyncio.Future"]


@contextmanager
def serve(tmp_path: Path, setup: Setup, run_pipeline: bool):
    """Serve `app` on a free port against a fresh DB; `setup(cfg, factory)` seeds it."""
    state: dict = {}
    ready, stop = threading.Event(), threading.Event()

    async def main() -> None:
        cfg = make_config(tmp_path)
        engine, factory = await make_session_factory(tmp_path)
        await setup(cfg, factory)
        orch = PipelineOrchestrator(factory, cfg, poll_interval=0.2)

        async def session():
            async with factory() as s:
                yield s

        app.dependency_overrides[get_async_session] = session
        app.state.orchestrator = orch
        server = uvicorn.Server(
            uvicorn.Config(app, port=0, lifespan="off", log_level="warning")
        )
        serving = asyncio.create_task(server.serve())
        worker = asyncio.create_task(orch.run_forever()) if run_pipeline else None
        while not server.started:
            await asyncio.sleep(0.05)
        state["url"] = (
            f"http://127.0.0.1:{server.servers[0].sockets[0].getsockname()[1]}"
        )
        ready.set()
        while not stop.is_set():
            await asyncio.sleep(0.1)
        orch.running = False
        server.should_exit = True
        await serving
        if worker:
            worker.cancel()
        await engine.dispose()

    thread = threading.Thread(target=lambda: asyncio.run(main()), daemon=True)
    thread.start()
    assert ready.wait(30), "UI server did not start"
    try:
        yield state["url"]
    finally:
        stop.set()
        thread.join(15)
        app.dependency_overrides.clear()
        if hasattr(app.state, "orchestrator"):
            del app.state.orchestrator


@pytest.fixture(autouse=True)
def _loopback(monkeypatch):
    monkeypatch.setattr(settings, "API_HOST", "127.0.0.1")
    monkeypatch.setattr(settings, "API_TOKEN", "")


@pytest.fixture
def live(tmp_path):
    """Factory: live(setup, run_pipeline=False) -> base URL."""
    stack: list = []

    def _live(setup: Setup, run_pipeline: bool = False) -> str:
        cm = serve(tmp_path, setup, run_pipeline)
        stack.append(cm)
        return cm.__enter__()

    yield _live
    for cm in reversed(stack):
        cm.__exit__(None, None, None)


def wait_until(predicate, timeout: float = 30, interval: float = 0.3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


__all__ = ["httpx", "live", "wait_until"]
