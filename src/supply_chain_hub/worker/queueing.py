from uuid import UUID

from kombu.exceptions import OperationalError as BrokerOperationalError


def publish_import_job(import_job_id: UUID) -> str | None:
    """Publish only a durable job reference; return None if Redis is unavailable."""
    from supply_chain_hub.worker.tasks import process_import_job_task

    try:
        # Give the API a brief window to persist its dispatch receipt before a
        # fast local worker begins writing later stages of the teaching trail.
        result = process_import_job_task.apply_async(
            args=[str(import_job_id)],
            countdown=0.5,
        )
    except BrokerOperationalError:
        return None
    return str(result.id)
