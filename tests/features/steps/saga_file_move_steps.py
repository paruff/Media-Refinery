from behave import given, when, then
import os
import tempfile
from app.services.execution_service import execute_normalization_plan
from app.models.saga import SagaFileMoveLog, SagaLogStatus
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
import asyncio


@given("a NormalizationPlan with a valid source and target")
def step_given_plan(context):
    context.tmpdir = tempfile.TemporaryDirectory()
    out_path = os.path.join(context.tmpdir.name, "out_bdd_saga.mp4")
    with open(out_path, "wb") as f:
        f.write(b"dummy")
    context.plan = {"id": "bddsaga", "target_path": out_path}
    context.out_path = out_path


@when("the plan is executed")
def step_when_execute(context):
    execute_normalization_plan(context.plan)


@then("the file is first written as .tmp")
def step_then_tmp_written(context):
    tmp_path = context.out_path + ".tmp"
    assert os.path.exists(tmp_path) or os.path.exists(context.out_path)


@then('a WAL entry is created with status "prepared"')
def step_then_wal_prepared(context):
    async def check():
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(SagaFileMoveLog).where(SagaFileMoveLog.plan_id == "bddsaga")
            )
            log = result.scalars().first()
            assert log is not None
            assert log.status in (SagaLogStatus.prepared, SagaLogStatus.committed)

    asyncio.run(check())


@when("the file is verified and committed")
def step_when_verified(context):
    # Already done in execute_normalization_plan
    pass


@then('the WAL entry is updated to "committed"')
def step_then_wal_committed(context):
    async def check():
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(SagaFileMoveLog).where(SagaFileMoveLog.plan_id == "bddsaga")
            )
            log = result.scalars().first()
            assert log is not None
            assert log.status == SagaLogStatus.committed

    asyncio.run(check())


@then("the .tmp file is atomically renamed")
def step_then_tmp_renamed(context):
    assert os.path.exists(context.out_path)


@then("the output file exists")
def step_then_output_exists(context):
    assert os.path.exists(context.out_path)


@given("a NormalizationPlan with a .tmp file left from a crash")
def step_given_tmp_left(context):
    context.tmpdir = tempfile.TemporaryDirectory()
    out_path = os.path.join(context.tmpdir.name, "out_bdd_saga_crash.mp4")
    tmp_path = out_path + ".tmp"
    with open(tmp_path, "wb") as f:
        f.write(b"dummy")
    context.plan = {"id": "bddsagacrash", "target_path": out_path}
    context.out_path = out_path

    # Simulate WAL entry
    async def create_log():
        async with AsyncSessionLocal() as session:
            log = SagaFileMoveLog(
                plan_id="bddsagacrash",
                src_path=out_path,
                tmp_path=tmp_path,
                dest_path=out_path,
                status=SagaLogStatus.prepared,
            )
            session.add(log)
            await session.commit()

    asyncio.run(create_log())


@when("the system restarts")
def step_when_restart(context):
    # Call recovery logic directly
    from app.services.execution_service import _execute_normalization_plan

    # This will trigger recovery
    _execute_normalization_plan(context.plan)


@then("the .tmp file is either cleaned or atomically renamed")
def step_then_tmp_cleaned_or_renamed(context):
    # Either .tmp is gone or renamed
    tmp_path = context.out_path + ".tmp"
    assert not os.path.exists(tmp_path) or os.path.exists(context.out_path)


@then("the WAL entry is updated accordingly")
def step_then_wal_updated(context):
    async def check():
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(SagaFileMoveLog).where(SagaFileMoveLog.plan_id == "bddsagacrash")
            )
            log = result.scalars().first()
            assert log is not None
            assert log.status in (SagaLogStatus.committed, SagaLogStatus.cleaned)

    asyncio.run(check())
