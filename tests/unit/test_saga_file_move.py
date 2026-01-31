import pytest
from sqlalchemy import select
import asyncio


def test_saga_prepare_commit_cleanup():
    import uuid
    import tempfile
    import os
    import importlib
    from sqlalchemy import text

    # Use a temp SQLite file DB for test isolation
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_saga.sqlite")
        os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
        # Reload app.core.database to pick up new DATABASE_URL
        import app.core.database

        importlib.reload(app.core.database)
        from app.core.database import init_db, AsyncSessionLocal
        from app.models.media import NormalizationPlan
        from app.models.saga import SagaFileMoveLog, SagaLogStatus

        asyncio.run(init_db())

        # Clear normalization_plans table
        async def clear_plans():
            async with AsyncSessionLocal() as session:
                await session.execute(text("DELETE FROM normalization_plans"))
                await session.commit()

        asyncio.run(clear_plans())
        out_path = os.path.join(tmpdir, "out_saga.mp4")
        with open(out_path, "wb") as f:
            f.write(b"dummy")
        plan_id = "sagaid"
        media_item_id = str(uuid.uuid4())

        async def insert_plan():
            async with AsyncSessionLocal() as session:
                plan = NormalizationPlan(
                    id=plan_id,
                    media_item_id=media_item_id,
                    target_path=out_path,
                    ffmpeg_args=[],
                    original_hash="dummyhash",
                )
                session.add(plan)
                await session.commit()

        asyncio.run(insert_plan())
        plan = {"id": plan_id, "target_path": out_path, "media_item_id": media_item_id}
        from app.services.execution_service import execute_normalization_plan

        execute_normalization_plan(plan)

        # Check WAL
        async def check_log():
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(SagaFileMoveLog).where(SagaFileMoveLog.plan_id == plan_id)
                )
                log = result.scalars().first()
                assert log is not None
                assert log.status == SagaLogStatus.committed

        asyncio.run(check_log())
        assert os.path.exists(out_path)


def test_saga_rollback_on_failure(monkeypatch):
    from sqlalchemy import select
    import uuid
    import tempfile
    import os
    import importlib
    from sqlalchemy import text

    # Use a temp SQLite file DB for test isolation
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_saga.sqlite")
        os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
        # Reload app.core.database to pick up new DATABASE_URL
        import app.core.database

        importlib.reload(app.core.database)
        from app.core.database import init_db, AsyncSessionLocal
        from app.models.media import NormalizationPlan
        from app.models.saga import SagaFileMoveLog, SagaLogStatus

        asyncio.run(init_db())

        # Clear normalization_plans table
        async def clear_plans():
            async with AsyncSessionLocal() as session:
                await session.execute(text("DELETE FROM normalization_plans"))
                await session.commit()

        asyncio.run(clear_plans())
        out_path = os.path.join(tmpdir, "fail_saga.mp4")
        with open(out_path, "wb") as f:
            f.write(b"dummy")
        plan_id = "failsaga"
        media_item_id = str(uuid.uuid4())

        async def insert_plan():
            async with AsyncSessionLocal() as session:
                plan = NormalizationPlan(
                    id=plan_id,
                    media_item_id=media_item_id,
                    target_path=out_path,
                    ffmpeg_args=[],
                    original_hash="dummyhash",
                )
                session.add(plan)
                await session.commit()

        asyncio.run(insert_plan())
        plan = {"id": plan_id, "target_path": out_path, "media_item_id": media_item_id}
        import app.services.execution_service as es

        def fail_plan(plan_dict):
            raise RuntimeError("ffmpeg failed")

        monkeypatch.setattr(es, "_execute_normalization_plan", fail_plan)
        with pytest.raises(RuntimeError):
            es.execute_normalization_plan(plan)

        # Check WAL for failed status
        async def check_log():
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(SagaFileMoveLog).where(SagaFileMoveLog.plan_id == plan_id)
                )
                log = result.scalars().first()
                assert log is not None
                assert log.status == SagaLogStatus.failed

        asyncio.run(check_log())
