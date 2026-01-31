from celery import Celery
import os

# Load broker URL from environment or default
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "media_refinery",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.services.execution_service"],
)

if __name__ == "__main__":
    celery_app.worker_main()
