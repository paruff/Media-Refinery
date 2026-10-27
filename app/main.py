import asyncio
import contextlib
import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.auth import require_token
from app.api.v1.items import router as items_router
from app.api.v1.ops import router as ops_router
from app.api.v1.ops import secured as ops_secured_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal, init_db
from app.core.orchestrator import PipelineConfig
from app.core.watcher import InputWatcher
from app.services.refinery import build_orchestrator
from app.ui.routes import HERE as UI_DIR
from app.ui.routes import router as ui_router

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
    orchestrator = build_orchestrator(
        AsyncSessionLocal, PipelineConfig.from_settings(), logger=logger
    )
    worker = asyncio.create_task(orchestrator.run_forever())
    watcher = InputWatcher(settings.INPUT_DIR, AsyncSessionLocal, logger=logger)
    watcher.run()  # non-blocking; must run on the loop thread
    app.state.orchestrator = orchestrator
    app.state.watcher = watcher
    try:
        yield
    finally:
        watcher.stop()
        orchestrator.running = False
        worker.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker


app = FastAPI(title="Media Normalizer Daemon Edition", lifespan=lifespan)

app.include_router(
    ops_router, include_in_schema=False
)  # /health and /ready stay at the root for probes
app.include_router(ops_router, prefix="/api/v1")
secured = [Depends(require_token)]
app.include_router(ops_secured_router, prefix="/api/v1", dependencies=secured)
app.include_router(items_router, prefix="/api/v1", dependencies=secured)
app.include_router(ui_router)
app.mount("/ui/static", StaticFiles(directory=UI_DIR / "static"), name="ui-static")
