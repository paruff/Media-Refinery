import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import FastAPI

from app.api.v1.health import router as health_router
from app.api.v1.summary import router as summary_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal, init_db
from app.core.pipeline import PipelineCoordinator
from app.core.watcher import InputWatcher

logger = logging.getLogger("uvicorn")
LOG_FILE_NAME = "rotation.log"


def configure_logging() -> None:
    """Structured logging to stdout and a rotating file under settings.LOG_DIR."""
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = str((log_dir / LOG_FILE_NAME).resolve())
    if any(getattr(h, "baseFilename", None) == log_file for h in logger.handlers):
        return
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    file_handler = RotatingFileHandler(log_file, maxBytes=5_000_000, backupCount=3)
    stdout_handler = logging.StreamHandler(sys.stdout)
    for handler in (stdout_handler, file_handler):
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    await init_db()
    coordinator = PipelineCoordinator(AsyncSessionLocal, logger=logger)
    await coordinator.start()
    watcher = InputWatcher(
        settings.INPUT_DIR, AsyncSessionLocal, logger=logger, coordinator=coordinator
    )
    watcher.run()  # non-blocking; must run on the loop thread
    app.state.coordinator = coordinator
    app.state.watcher = watcher
    try:
        yield
    finally:
        watcher.stop()
        await coordinator.stop()


app = FastAPI(title="Media Normalizer Daemon Edition", lifespan=lifespan)

app.include_router(health_router, prefix="/health")
app.include_router(summary_router)
