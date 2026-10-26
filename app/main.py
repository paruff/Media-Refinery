import asyncio
import logging
import sys

from fastapi import FastAPI

from app.api.v1.health import router as health_router
from app.api.v1.summary import router as summary_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal, init_db
from app.core.pipeline import PipelineCoordinator
from app.core.watcher import InputWatcher

app = FastAPI(title="Media Normalizer Daemon Edition")

# Structured logging setup
logger = logging.getLogger("uvicorn")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setFormatter(formatter)
file_handler = logging.FileHandler("rotation.log")
file_handler.setFormatter(formatter)
logger.addHandler(stdout_handler)
logger.addHandler(file_handler)

watcher = None
coordinator = None


@app.on_event("startup")
async def on_startup():
    await init_db()
    global coordinator, watcher  # noqa: PLW0603
    coordinator = PipelineCoordinator(AsyncSessionLocal, logger=logger)
    await coordinator.start()
    watcher = InputWatcher(
        settings.INPUT_DIR, AsyncSessionLocal, logger=logger, coordinator=coordinator
    )
    loop = asyncio.get_event_loop()
    loop.create_task(asyncio.to_thread(watcher.run))  # noqa: RUF006


@app.on_event("shutdown")
def on_shutdown():
    global watcher, coordinator  # noqa: PLW0602
    if watcher:
        watcher.stop()
    if coordinator:
        asyncio.create_task(coordinator.stop())  # noqa: RUF006


app.include_router(health_router, prefix="/health")
app.include_router(summary_router)
