from celery import Celery

app = Celery("omnimem_z1", broker="redis://localhost:6379/0", backend="redis://localhost:6379/1", include=["tasks"])

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,  # Ensure idempotency before acking
    worker_prefetch_multiplier=1,  # for heavy lifting, prevent prefetching
)
