import os
from app.models.media import NormalizationPlan
from sqlalchemy.ext.asyncio import AsyncSession

# Celery setup

from app.schemas.normalization_plan import NormalizationPlanSchema

# Distributed execution toggle (env or CLI flag)
USE_DISTRIBUTED = bool(int(os.getenv("MEDIA_REFINERY_DISTRIBUTED", "0")))
if USE_DISTRIBUTED:
    from celery import Celery

    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    celery_app = Celery(
        "media_refinery",
        broker=REDIS_URL,
        backend=REDIS_URL,
    )

    @celery_app.task(name="execute_normalization_plan")
    def execute_normalization_plan(plan_dict):
        return _execute_normalization_plan(plan_dict)

else:
    celery_app = None

    def execute_normalization_plan(plan_dict):
        return _execute_normalization_plan(plan_dict)


def _execute_normalization_plan(plan_dict):
    """
    Celery task to execute a normalization plan.
    Validates input using Pydantic schema. Idempotent, atomic, rollback-safe, and transactional for DB.
    """
    import asyncio
    import logging
    from filelock import FileLock, Timeout
    from pathlib import Path
    import shutil
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import update
    from app.models.media import NormalizationPlan as DBPlan, PlanStatus
    import traceback

    logger = logging.getLogger("CeleryWorker")
    try:
        plan = NormalizationPlanSchema(**plan_dict)
    except Exception as e:
        logger.error(f"Invalid NormalizationPlan: {e}\nInput: {plan_dict}")
        return

    src = Path(plan.target_path)  # For demo, use target_path as src
    staging_dir = Path("/tmp/staging") / plan.id
    output_file = Path(plan.target_path)
    lock_path = output_file.with_suffix(output_file.suffix + ".lock")
    lock = FileLock(str(lock_path))

    async def do_work():
        async with AsyncSessionLocal() as session:
            try:
                # Set plan status to executing
                await session.execute(
                    update(DBPlan)
                    .where(DBPlan.id == plan.id)
                    .values(plan_status=PlanStatus.executing)
                )
                await session.commit()
            except Exception as e:
                logger.error(f"Failed to update plan status to executing: {e}")
                await session.rollback()
                return
            try:
                with lock.acquire(timeout=10):
                    # Idempotency: check if output exists and is valid (simulate checksum)
                    if output_file.exists() and output_file.stat().st_size > 0:
                        logger.info(f"Output {output_file} already exists, skipping.")
                        await session.execute(
                            update(DBPlan)
                            .where(DBPlan.id == plan.id)
                            .values(plan_status=PlanStatus.completed)
                        )
                        await session.commit()
                        return
                    # Stage: copy to staging (simulate atomic op)
                    os.makedirs(staging_dir, exist_ok=True)
                    staged_file = staging_dir / src.name
                    try:
                        shutil.copy2(src, staged_file)
                    except Exception as e:
                        logger.error(f"Failed to copy to staging: {e}")
                        raise

                    # Transcode (simulate with async subprocess)
                    async def run_ffmpeg():
                        proc = await asyncio.create_subprocess_exec(
                            "ffmpeg",
                            "-version",
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )
                        out, err = await proc.communicate()
                        if proc.returncode != 0:
                            raise RuntimeError(f"ffmpeg failed: {err.decode()}")

                    try:
                        await run_ffmpeg()
                    except Exception as e:
                        logger.error(f"Transcode failed: {e}")
                        # Rollback staging
                        if staged_file.exists():
                            os.remove(staged_file)
                        await session.execute(
                            update(DBPlan)
                            .where(DBPlan.id == plan.id)
                            .values(plan_status=PlanStatus.failed, execution_log=str(e))
                        )
                        await session.commit()
                        raise
                    # Atomic move to output
                    try:
                        shutil.move(str(staged_file), str(output_file))
                    except Exception as e:
                        logger.error(f"Atomic move failed: {e}")
                        # Rollback staging
                        if staged_file.exists():
                            os.remove(staged_file)
                        await session.execute(
                            update(DBPlan)
                            .where(DBPlan.id == plan.id)
                            .values(plan_status=PlanStatus.failed, execution_log=str(e))
                        )
                        await session.commit()
                        raise
                    logger.info(f"[Worker] Done: {plan.id}")
                    await session.execute(
                        update(DBPlan)
                        .where(DBPlan.id == plan.id)
                        .values(plan_status=PlanStatus.completed)
                    )
                    await session.commit()
            except Timeout:
                logger.error(f"Could not acquire lock for {output_file}")
                await session.execute(
                    update(DBPlan)
                    .where(DBPlan.id == plan.id)
                    .values(plan_status=PlanStatus.failed, execution_log="Lock timeout")
                )
                await session.commit()
            except Exception as e:
                logger.error(f"Task failed: {e}\n{traceback.format_exc()}")
                # Rollback output
                if output_file.exists():
                    try:
                        os.remove(output_file)
                    except Exception:
                        pass
                await session.execute(
                    update(DBPlan)
                    .where(DBPlan.id == plan.id)
                    .values(plan_status=PlanStatus.failed, execution_log=str(e))
                )
                await session.commit()
                raise

    # Run the async DB+task logic in event loop
    try:
        asyncio.run(do_work())
    except Exception as e:
        logger.error(f"execute_normalization_plan failed: {e}")


class ExecutionService:
    def __init__(self, db: AsyncSession, staging_root: str = "/staging"):
        self.db = db
        self.staging_root = staging_root

    async def execute_plan(self, plan: NormalizationPlan, distributed: bool = None):
        # distributed: override for this call; otherwise use global
        use_dist = distributed if distributed is not None else USE_DISTRIBUTED
        plan_schema = NormalizationPlanSchema.from_orm(plan)
        if use_dist:
            if not celery_app:
                raise RuntimeError("Celery/Redis not enabled or not configured!")
            celery_app.send_task(
                "execute_normalization_plan", args=[plan_schema.dict()]
            )
        else:
            _execute_normalization_plan(plan_schema.dict())
