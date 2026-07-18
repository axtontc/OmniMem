from core.celery_app import celery_app


@celery_app.task(bind=True, max_retries=3)
def placeholder_task(self, data: dict):
    """
    Placeholder task for Zone 1 (Z_1) background workers.
    Tasks will perform embedding generation and graph aggregations.
    """
    try:
        # Task logic will be injected here in later tasks
        return {"status": "success", "data": data}
    except Exception as exc:
        # Zero swallowed exceptions policy (from T8 description)
        raise self.retry(exc=exc, countdown=2**self.request.retries)
