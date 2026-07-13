import os
from celery import Celery

# Use environment variables for broker and backend, fallback to localhost for development
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")

celery_app = Celery(
    "omnimem_celery",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["workers.tasks"]
)

# Optional configuration, see the application user guide.
celery_app.conf.update(
    result_expires=3600,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Strict exception handling: Do not swallow exceptions
    task_reject_on_worker_lost=True,
    task_acks_late=True,
)

if __name__ == '__main__':
    celery_app.start()
