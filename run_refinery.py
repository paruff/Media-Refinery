import argparse
import os

from app.core.config import settings
from app.main import app

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Media Refinery Daemon")
    parser.add_argument(
        "--distributed",
        action="store_true",
        help="Enable distributed (Celery/Redis) execution",
    )
    args = parser.parse_args()
    if args.distributed:
        os.environ["MEDIA_REFINERY_DISTRIBUTED"] = "1"
    import uvicorn

    uvicorn.run(
        app, host=settings.API_HOST, port=8000
    )  # R-API-1: token required off-loopback
