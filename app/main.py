from fastapi import FastAPI
from app.core.config import settings
from app.core.database import init_db
from app.api.v1.health import router as health_router
import logging
import sys

app = FastAPI(title="Media Normalizer Daemon Edition")

# Structured logging setup
logger = logging.getLogger("uvicorn")
logger.setLevel(logging.INFO)
formatter = logging.Formatter(
    "%(asctime)s %(levelname)s %(name)s %(message)s"
)
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setFormatter(formatter)
file_handler = logging.FileHandler("rotation.log")
file_handler.setFormatter(formatter)
logger.addHandler(stdout_handler)
logger.addHandler(file_handler)

@app.on_event("startup")
async def on_startup():
    await init_db()

app.include_router(health_router, prefix="/health")
