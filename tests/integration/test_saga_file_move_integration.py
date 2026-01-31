import os
import tempfile
import time
from app.services.execution_service import execute_normalization_plan
from app.models.saga import SagaFileMoveLog, SagaLogStatus
from sqlalchemy import select
from app.core.database import AsyncSessionLocal


def test_saga_file_move_integration():
    # Simulate a real cross-volume move scenario
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "out_integ_saga.mp4")
        with open(out_path, "wb") as f:
            f.write(b"dummy")
        plan = {"id": "sagainteg", "target_path": out_path}
        execute_normalization_plan(plan)

        # Wait for WAL commit
        def check():
            async def _check():
                async with AsyncSessionLocal() as session:
                    result = await session.execute(
                        select(SagaFileMoveLog).where(
                            SagaFileMoveLog.plan_id == "sagainteg"
                        )
                    )
                    log = result.scalars().first()
                    return log and log.status == SagaLogStatus.committed

            import asyncio

            for _ in range(10):
                if asyncio.run(_check()):
                    return True
                time.sleep(0.5)
            return False

        assert check()
        assert os.path.exists(out_path)
