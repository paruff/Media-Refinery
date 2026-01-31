import os
import tempfile
import pytest
from app.services.execution_service import execute_normalization_plan
from app.models.saga import SagaFileMoveLog, SagaLogStatus
from sqlalchemy import select
from app.core.database import AsyncSessionLocal


def test_saga_prepare_commit_cleanup():
    # Test Prepare-Commit-Cleanup lifecycle
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "out_saga.mp4")
        # Create a dummy source file
        with open(out_path, "wb") as f:
            f.write(b"dummy")
        plan = {"id": "sagaid", "target_path": out_path}
        execute_normalization_plan(plan)

        # Check WAL
        async def check_log():
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(SagaFileMoveLog).where(SagaFileMoveLog.plan_id == "sagaid")
                )
                log = result.scalars().first()
                assert log is not None
                assert log.status == SagaLogStatus.committed

        import asyncio

        asyncio.run(check_log())
        # Output should exist
        assert os.path.exists(out_path)


def test_saga_rollback_on_failure(monkeypatch):
    # Simulate failure and check rollback
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "fail_saga.mp4")
        with open(out_path, "wb") as f:
            f.write(b"dummy")
        plan = {"id": "failsaga", "target_path": out_path}
        import app.services.execution_service as es

        def fail_plan(plan_dict):
            raise RuntimeError("ffmpeg failed")

        monkeypatch.setattr(es, "execute_normalization_plan", fail_plan)
        with pytest.raises(RuntimeError):
            es.execute_normalization_plan(plan)

        # Check WAL for failed status
        async def check_log():
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(SagaFileMoveLog).where(SagaFileMoveLog.plan_id == "failsaga")
                )
                log = result.scalars().first()
                assert log is not None
                assert log.status == SagaLogStatus.failed

        import asyncio

        asyncio.run(check_log())
