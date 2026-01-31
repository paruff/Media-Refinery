import asyncio
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.media import MediaItem

# Celery/Redis for distributed execution monitoring
from celery.result import AsyncResult

# Import your services here
# from app.services.scanner_service import ScannerService
# from app.services.classification_service import ClassificationService
# from app.services.enrichment_service import EnrichmentService
# from app.services.planning_service import PlanningService
# from app.services.execution_service import ExecutionService
# from app.services.validator_service import ValidatorService

STATE_MAP = {
    "pending": {
        "service": "scanner",
        "next": "scanned",
        "fail": "error",
    },
    "scanned": {
        "service": "classifier",
        "next": "classified",
        "fail": "error",
    },
    "classified": {
        "service": "enricher",
        "next": "enriched",
        "fail": "enrichment_failed",
    },
    "enriched": {
        "service": "planner",
        "next": "planned",
        "fail": "error",
    },
    "planned": {
        "service": "executor",
        "next": "executed",
        "fail": "error",
    },
    "executed": {
        "service": "validator",
        "next": "validated",
        "fail": "error",
    },
}


class PipelineOrchestrator:
    def __init__(self, db: AsyncSession, logger=None, poll_interval=5):
        self.db = db
        self.logger = logger or logging.getLogger("PipelineOrchestrator")
        self.poll_interval = poll_interval
        self.enrich_semaphore = asyncio.Semaphore(5)
        self.transcode_semaphore = asyncio.Semaphore(2)
        self.running = False

    async def run_forever(self):
        self.running = True
        await self._recover_inflight()
        while self.running:
            try:
                await self._process_actionable_items()
            except Exception as e:
                self.logger.error(f"Orchestrator loop error: {e}")
            await asyncio.sleep(self.poll_interval)

    async def _recover_inflight(self):
        # Move any stuck items in 'executing' back to 'planned' or 'error'
        result = await self.db.execute(
            select(MediaItem).where(MediaItem.state == "executing")
        )
        stuck = result.scalars().all()
        for item in stuck:
            item.state = "planned"
            item.updated_at = datetime.utcnow()
        await self.db.commit()

    async def _process_actionable_items(self):
        # Query for actionable items
        result = await self.db.execute(
            select(MediaItem).where(MediaItem.state.in_(STATE_MAP.keys()))
        )
        items = result.scalars().all()
        tasks = []
        for item in items:
            state_info = STATE_MAP[item.state]
            service_name = state_info["service"]
            coro = self._dispatch(item, service_name, state_info)
            # Concurrency control for enrichment and execution
            if service_name == "enricher":
                tasks.append(self._with_semaphore(self.enrich_semaphore, coro))
            elif service_name == "executor":
                tasks.append(self._with_semaphore(self.transcode_semaphore, coro))
            else:
                tasks.append(coro)
        if tasks:
            await asyncio.gather(*tasks)

    async def _with_semaphore(self, sem, coro):
        async with sem:
            return await coro

    async def _dispatch(self, item, service_name, state_info):
        try:
            # Executor: dispatch to Celery and monitor status
            if service_name == "executor":
                # Simulate sending task and monitoring status
                from app.services.execution_service import celery_app

                # In real code, get plan/task id from item
                # Here, just simulate a Celery task id
                task_id = getattr(item, "celery_task_id", None)
                if not task_id:
                    # Simulate sending task (would be done in ExecutionService)
                    # task = celery_app.send_task("execute_normalization_plan", args=[plan_dict])
                    # item.celery_task_id = task.id
                    item.celery_task_id = "fake-task-id"
                    item.state = "executing"
                else:
                    # Monitor status
                    result = AsyncResult(task_id, app=celery_app)
                    if result.state == "SUCCESS":
                        item.state = state_info["next"]
                        item.updated_at = datetime.utcnow()
                        item.retry_count = 0
                    elif result.state in ("FAILURE", "REVOKED"):
                        item.state = state_info["fail"]
                        item.updated_at = datetime.utcnow()
                        item.retry_count = getattr(item, "retry_count", 0) + 1
                        if item.retry_count > 3:
                            item.state = "error"
                    else:
                        # Still running
                        pass
            else:
                # Placeholder: Replace with actual service calls
                await asyncio.sleep(0.1)  # Simulate work
                # On success
                item.state = state_info["next"]
                item.updated_at = datetime.utcnow()
                item.retry_count = 0
                # Optionally, append to audit_log
        except Exception as e:
            item.state = state_info["fail"]
            item.updated_at = datetime.utcnow()
            item.retry_count = getattr(item, "retry_count", 0) + 1
            if item.retry_count > 3:
                item.state = "error"
            # Optionally, log traceback to execution_log
            self.logger.error(f"Error in {service_name} for {item.id}: {e}")
        await self.db.commit()
