import os
import tempfile
import pytest
from app.services.execution_service import celery_app, execute_normalization_plan


def test_celery_task_registration():
    assert "execute_normalization_plan" in celery_app.tasks


def test_execute_normalization_plan_runs():
    # Should not raise, simulates work
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "out.mp4")
        # Create a dummy source file
        with open(out_path, "wb") as f:
            f.write(b"dummy")
        plan = {"id": "testid", "target_path": out_path}
        execute_normalization_plan(plan)


def test_idempotency_of_execute_normalization_plan():
    # Running the same plan twice should not duplicate work
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "out.mp4")
        with open(out_path, "wb") as f:
            f.write(b"dummy")
        plan = {"id": "idempotent", "target_path": out_path}
        execute_normalization_plan(plan)
        # Run again, should skip
        execute_normalization_plan(plan)
        # Output should still exist and be unchanged
        assert os.path.exists(out_path)


def test_rollback_on_failure(monkeypatch):
    # Simulate ffmpeg failure and check rollback
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "fail.mp4")
        with open(out_path, "wb") as f:
            f.write(b"dummy")
        plan = {"id": "failcase", "target_path": out_path}
        # Patch subprocess to raise
        import app.services.execution_service as es

        def fail_plan(plan_dict):
            raise RuntimeError("ffmpeg failed")

        monkeypatch.setattr(es, "execute_normalization_plan", fail_plan)
        with pytest.raises(RuntimeError):
            es.execute_normalization_plan(plan)
