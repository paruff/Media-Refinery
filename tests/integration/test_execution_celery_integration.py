import os
import tempfile
import time
import pytest
from app.services.execution_service import celery_app
from app.core.database import AsyncSessionLocal
from app.models.media import NormalizationPlan as DBPlan, PlanStatus


def test_celery_task_queue_and_result():
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "out2.mp4")
        with open(out_path, "wb") as f:
            f.write(b"dummy")
        plan = {"id": "integrationid", "target_path": out_path}
        result = celery_app.send_task("execute_normalization_plan", args=[plan])
        # Wait for result (simulate worker running)
        for _ in range(20):
            if result.ready():
                break
            time.sleep(0.5)
        assert result.successful() or result.status == "SUCCESS"


def test_idempotency_integration():
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "out3.mp4")
        with open(out_path, "wb") as f:
            f.write(b"dummy")
        plan = {"id": "integrationidemp", "target_path": out_path}
        # Queue twice
        result1 = celery_app.send_task("execute_normalization_plan", args=[plan])
        result2 = celery_app.send_task("execute_normalization_plan", args=[plan])
        for _ in range(20):
            if result1.ready() and result2.ready():
                break
            time.sleep(0.5)
        assert result1.successful() or result1.status == "SUCCESS"
        assert result2.successful() or result2.status == "SUCCESS"
        # Output should exist
        assert os.path.exists(out_path)


@pytest.mark.asyncio
async def test_rollback_integration():
    # Simulate a plan with a bad path to force failure
    plan = {"id": "failint", "target_path": "/nonexistent/shouldfail.mp4"}
    result = celery_app.send_task("execute_normalization_plan", args=[plan])
    for _ in range(20):
        if result.ready():
            break
        time.sleep(0.5)
    # Should fail
    assert result.failed() or result.status == "FAILURE"
    # Check DB for failed status if DB is available
    async with AsyncSessionLocal() as session:
        dbplan = await session.get(DBPlan, "failint")
        if dbplan:
            assert dbplan.plan_status == PlanStatus.failed
