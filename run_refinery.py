import argparse
import os
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

    uvicorn.run(app, host="0.0.0.0", port=8000)
