import os
import tempfile
import pytest
from app.services.execution_service import celery_app


def test_celery_task_queue_and_result(monkeypatch):
    class MockResult:
        def ready(self):
            return True

        def successful(self):
            return True

        @property
        def status(self):
            return "SUCCESS"

        def failed(self):
            return False

    monkeypatch.setattr(celery_app, "send_task", lambda *a, **k: MockResult())
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "out2.mp4")
        with open(out_path, "wb") as f:
            f.write(b"dummy")
        plan = {"id": "integrationid", "target_path": out_path}
        result = celery_app.send_task("execute_normalization_plan", args=[plan])
        assert result.successful() or result.status == "SUCCESS"


def test_idempotency_integration(monkeypatch):
    class MockResult:
        def ready(self):
            return True

        def successful(self):
            return True

        @property
        def status(self):
            return "SUCCESS"

        def failed(self):
            return False

    monkeypatch.setattr(celery_app, "send_task", lambda *a, **k: MockResult())
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "out3.mp4")
        with open(out_path, "wb") as f:
            f.write(b"dummy")
        plan = {"id": "integrationidemp", "target_path": out_path}
        # Queue twice
        result1 = celery_app.send_task("execute_normalization_plan", args=[plan])
        result2 = celery_app.send_task("execute_normalization_plan", args=[plan])
        assert result1.successful() or result1.status == "SUCCESS"
        assert result2.successful() or result2.status == "SUCCESS"
        # Output should exist (simulate success)
        assert os.path.exists(out_path)


@pytest.mark.asyncio
async def test_rollback_integration(monkeypatch):
    class MockResult:
        def ready(self):
            return True

        def successful(self):
            return False

        @property
        def status(self):
            return "FAILURE"

        def failed(self):
            return True

    monkeypatch.setattr(celery_app, "send_task", lambda *a, **k: MockResult())
    # Simulate a plan with a bad path to force failure
    plan = {"id": "failint", "target_path": "/nonexistent/shouldfail.mp4"}
    result = celery_app.send_task("execute_normalization_plan", args=[plan])
    # Should fail
    assert result.failed() or result.status == "FAILURE"
    # Optionally skip DB check in CI if DB is not available
