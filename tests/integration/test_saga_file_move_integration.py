import os
import tempfile
import time
import uuid

from sqlalchemy import select

from app.models.saga import SagaFileMoveLog, SagaLogStatus
from app.services.execution_service import execute_normalization_plan


def test_saga_file_move_integration():
    # Simulate a real cross-volume move scenario
    with tempfile.TemporaryDirectory() as tmpdir:
        import asyncio

        from app.core.database import init_db

        asyncio.run(init_db())
        out_path = os.path.join(tmpdir, "out_integ_saga.mp4")
        with open(out_path, "wb") as f:
            f.write(b"dummy")
        plan_id = f"sagainteg-{uuid.uuid4()}"
        plan = {"id": plan_id, "target_path": out_path}
        execute_normalization_plan(plan)

        # Wait for WAL commit
        def check():
            async def _check():
                from app.core.database import AsyncSessionLocal

                async with AsyncSessionLocal() as session:
                    result = await session.execute(
                        select(SagaFileMoveLog).where(
                            SagaFileMoveLog.plan_id == plan_id
                        )
                    )
                    log = result.scalars().first()
                    return log and log.status == SagaLogStatus.committed

            for _ in range(10):
                if asyncio.run(_check()):
                    return True
                time.sleep(0.5)
            return False

        assert check()
        assert os.path.exists(out_path)
