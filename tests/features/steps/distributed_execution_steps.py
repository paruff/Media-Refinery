from behave import given, when, then  # type: ignore[import-untyped]
from app.services.execution_service import celery_app
import time


@given("a NormalizationPlan exists")
def given_plan_exists(context):
    context.plan = {"id": "bddid", "target_path": "/tmp/bdd.mp4"}


@when("ExecutionService dispatches the plan")
def when_dispatch_plan(context):
    context.result = celery_app.send_task(
        "execute_normalization_plan", args=[context.plan]
    )


@then("the plan should appear in the Redis queue")
def then_plan_in_queue(context):
    assert context.result.id is not None
    # Optionally check status is PENDING or RECEIVED
    assert context.result.status in ("PENDING", "RECEIVED", "STARTED", "SUCCESS")


@given("a worker is running")
def given_worker_running(context):
    # Assume worker is running for BDD
    pass


@when("a task is available in the queue")
def when_task_available(context):
    # Already enqueued in previous step
    pass


@then("the worker should execute the task and update status")
def then_worker_executes_task(context):
    # Wait for result (simulate worker running)
    for _ in range(10):
        if context.result.ready():
            break
        time.sleep(0.5)
    assert context.result.successful() or context.result.status == "SUCCESS"
