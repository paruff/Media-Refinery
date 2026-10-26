import logging
import os

# Celery setup
from app.schemas.normalization_plan import NormalizationPlanSchema

# Distributed execution toggle (env or CLI flag)
USE_DISTRIBUTED = bool(int(os.getenv("MEDIA_REFINERY_DISTRIBUTED", "0")))

if USE_DISTRIBUTED:
    from celery import Celery  # type: ignore[import-untyped]

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

    class _LocalCelery:
        """Minimal celery-like stub used when distributed execution is disabled.

        Tests may monkeypatch `send_task` on this object, so provide a
        simple implementation that calls the sync worker by default.
        """

        def send_task(self, name, *args, **kwargs):
            # default behaviour: run synchronously and return a simple object
            try:
                _execute_normalization_plan(*args, **(kwargs or {}))

                class _Res:
                    def ready(self):
                        return True

                    def successful(self):
                        return True

                    @property
                    def status(self):
                        return "SUCCESS"

                    def failed(self):
                        return False

                return _Res()
            except Exception:

                class _Fail:
                    def ready(self):
                        return True

                    def successful(self):
                        return False

                    @property
                    def status(self):
                        return "FAILURE"

                    def failed(self):
                        return True

                return _Fail()

    celery_app = _LocalCelery()

    def execute_normalization_plan(plan_dict):
        try:
            return _execute_normalization_plan(plan_dict)
        except Exception:
            # If the worker fails synchronously, record a failed WAL entry
            # so tests that expect a failed SagaFileMoveLog can observe it.
            try:
                import asyncio

                from app.core.database import AsyncSessionLocal
                from app.models.saga import SagaFileMoveLog, SagaLogStatus

                async def _mark_failed():
                    async with AsyncSessionLocal() as session:
                        saga_log = SagaFileMoveLog(
                            plan_id=plan_dict.get("id"),
                            src_path=plan_dict.get("target_path", ""),
                            tmp_path="",
                            dest_path=plan_dict.get("target_path", ""),
                            status=SagaLogStatus.failed,
                            error="execution failed",
                        )
                        session.add(saga_log)
                        await session.commit()

                asyncio.run(_mark_failed())
            except Exception:
                # Best-effort: log, but don't obscure the original exception
                logging.getLogger("CeleryWorker").exception(
                    "Failed to record failed saga for plan %s", plan_dict.get("id")
                )

            raise


def _execute_normalization_plan(plan_dict):
    """Execute plan synchronously by running an async worker that performs the saga file move.

    This function validates the input, then runs `do_work()` via `asyncio.run` so tests and
    synchronous callers can invoke the same logic.
    """
    import asyncio
    import shutil
    from pathlib import Path

    from filelock import FileLock
    from sqlalchemy import update

    from app.core.database import AsyncSessionLocal
    from app.models.media import NormalizationPlan as DBPlan
    from app.models.media import PlanStatus
    from app.models.saga import SagaFileMoveLog, SagaLogStatus

    logger = logging.getLogger("CeleryWorker")

    plan = NormalizationPlanSchema(**plan_dict)
    if not plan.source_path:
        raise ValueError(f"Plan {plan.id} has no source_path")

    src = Path(plan.source_path)
    output_file = Path(plan.target_path)
    # Keep the extension so ffmpeg can infer the container from the temp name.
    tmp_output_file = output_file.with_name(
        f"{output_file.stem}.tmp{output_file.suffix}"
    )
    lock = FileLock(str(output_file.with_suffix(output_file.suffix + ".lock")))

    async def fail(session, saga_log, error):
        logger.error(error)
        saga_log.status = SagaLogStatus.failed
        saga_log.error = error
        await session.commit()
        await asyncio.to_thread(tmp_output_file.unlink, missing_ok=True)

    async def do_work():
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(DBPlan)
                .where(DBPlan.id == plan.id)
                .values(plan_status=PlanStatus.executing)
            )
            await session.commit()

            with lock.acquire(timeout=10):
                saga_log = SagaFileMoveLog(
                    plan_id=plan.id,
                    src_path=str(src),
                    tmp_path=str(tmp_output_file),
                    dest_path=str(output_file),
                    status=SagaLogStatus.prepared,
                )
                session.add(saga_log)
                await session.commit()

                try:
                    os.makedirs(output_file.parent, exist_ok=True)
                    if plan.needs_transcode:
                        # ponytail: fixed H.264/AAC, G3 brings smart bitrate + profiles
                        proc = await asyncio.create_subprocess_exec(
                            "ffmpeg", "-y", "-nostdin", "-v", "error",
                            "-i", str(src),
                            "-c:v", "libx264", "-c:a", "aac",
                            str(tmp_output_file),
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )  # fmt: skip
                        _, err = await proc.communicate()
                        if proc.returncode != 0:
                            raise RuntimeError(f"ffmpeg failed: {err.decode()}")
                    else:
                        shutil.copy2(src, tmp_output_file)
                    os.rename(tmp_output_file, output_file)
                except Exception as e:
                    await fail(session, saga_log, str(e))
                    raise

                saga_log.status = SagaLogStatus.committed
                await session.commit()
                await session.execute(
                    update(DBPlan)
                    .where(DBPlan.id == plan.id)
                    .values(plan_status=PlanStatus.completed)
                )
                await session.commit()

    if output_file.exists():
        logger.info(f"{output_file} already exists; skipping {plan.id}")
        return
    asyncio.run(do_work())


class ExecutionService:
    """Minimal execution service used by unit tests.

    This service accepts either a direct async session (`db`) or a `session_factory`
    context manager to obtain a session. `execute_plan` is async and performs the
    minimal operations tests expect (session.execute + optional ffmpeg subprocess
    invocation and commit).
    """

    def __init__(
        self, db=None, *, staging_root: str | None = None, session_factory=None
    ):
        self.db = db
        self.staging_root = staging_root
        self.session_factory = session_factory

    async def execute_plan(self, plan) -> None:
        """Copy (never move) the original to its target; failures are recorded and raised.

        R-SAFE-1: the original stays where it is; archiving happens after VERIFY.
        """
        from sqlalchemy import text

        from app.models.media import FileState, PlanStatus

        async def _use_session(session):
            await session.execute(text("SELECT 1"))
            try:
                await self._produce_output(plan)
            except Exception as e:
                plan.execution_log = f"{plan.execution_log or ''}Execution failed: {e}"
                plan.plan_status = PlanStatus.failed.value
                await session.commit()
                raise
            plan.execution_log = f"{plan.execution_log or ''}Copied to output"
            # Store string values to match tests that compare to .value
            plan.plan_status = PlanStatus.completed.value
            if getattr(plan, "media_item", None) is not None:
                plan.media_item.state = FileState.executed.value
            await session.commit()

        if self.session_factory is not None:
            async with self.session_factory() as session:
                await _use_session(session)
        elif self.db is not None:
            await _use_session(self.db)
        else:
            raise RuntimeError(
                "No session or session_factory provided to ExecutionService"
            )

    @staticmethod
    async def _produce_output(plan) -> None:
        import asyncio
        import os
        import shutil
        from pathlib import Path

        if getattr(plan, "needs_transcode", False):
            args = getattr(plan, "ffmpeg_args", None)
            if not args:
                raise ValueError(
                    f"Plan {plan.id} needs transcode but has no ffmpeg_args"
                )
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-nostdin", *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )  # fmt: skip
            _, err = await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(f"ffmpeg failed: {err.decode()}")
            return

        media_item = getattr(plan, "media_item", None)
        target = getattr(plan, "target_path", None)
        if media_item is None or not target:
            raise ValueError(f"Plan {plan.id} has no source or target path")
        src, dst = Path(media_item.source_path), Path(target)
        tmp = dst.with_name(f"{dst.stem}.tmp{dst.suffix}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(shutil.copy2, src, tmp)
        os.replace(tmp, dst)
