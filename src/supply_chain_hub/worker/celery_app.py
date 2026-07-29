from celery import Celery

from supply_chain_hub.settings.config import get_settings

settings = get_settings()

celery_app = Celery(
    "supply_chain_hub",
    broker=settings.redis_url,
    include=["supply_chain_hub.worker.tasks"],
)
celery_app.conf.update(
    broker_connection_retry_on_startup=True,
    broker_transport_options={
        "visibility_timeout": settings.import_lease_seconds * 2,
    },
    result_backend=None,
    task_acks_late=True,
    task_ignore_result=True,
    task_reject_on_worker_lost=True,
    task_serializer="json",
    accept_content=["json"],
    worker_prefetch_multiplier=1,
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "dispatch-durable-import-jobs": {
            "task": "imports.dispatch_queued",
            "schedule": 15.0,
        },
        "recover-expired-import-leases": {
            "task": "imports.recover_stale",
            "schedule": 30.0,
        },
    },
)
