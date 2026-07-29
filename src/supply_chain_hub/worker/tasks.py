from uuid import UUID

from celery import Task
from sqlalchemy.exc import OperationalError

from supply_chain_hub.application import integration_services
from supply_chain_hub.domain.exceptions import ResourceNotFoundError
from supply_chain_hub.infrastructure.db.session import SessionLocal
from supply_chain_hub.settings.config import get_settings
from supply_chain_hub.worker.celery_app import celery_app
from supply_chain_hub.worker.queueing import publish_import_job


@celery_app.task(
    bind=True,
    name="imports.process",
    max_retries=None,
)
def process_import_job_task(
    self: Task,
    import_job_id: str,
) -> dict[str, object]:
    job_id = UUID(import_job_id)
    worker_id = str(self.request.hostname or "unknown-worker")
    task_id = str(self.request.id) if self.request.id is not None else None
    try:
        with SessionLocal() as session:
            job = integration_services.execute_import_job(
                session,
                job_id,
                worker_id=worker_id,
                celery_task_id=task_id,
            )
        return {"job_id": str(job.id), "status": job.status.value}
    except ResourceNotFoundError:
        return {"job_id": import_job_id, "status": "not_found"}
    except Exception as error:
        try:
            with SessionLocal() as session:
                disposition = integration_services.record_import_failure(
                    session,
                    job_id,
                    error,
                    worker_id=worker_id,
                    celery_task_id=task_id,
                )
        except OperationalError as persistence_error:
            raise self.retry(
                exc=persistence_error,
                countdown=get_settings().import_retry_base_seconds,
            ) from persistence_error
        if disposition.retry_scheduled:
            raise self.retry(
                exc=error,
                countdown=disposition.retry_delay_seconds or 0,
            ) from error
        return {
            "job_id": import_job_id,
            "status": "failed",
            "failure_code": disposition.failure_code,
        }


@celery_app.task(name="imports.dispatch_queued")
def dispatch_queued_imports_task() -> dict[str, int]:
    published = 0
    with SessionLocal() as session:
        job_ids = [
            job.id for job in integration_services.jobs_due_for_dispatch(session)
        ]
    for job_id in job_ids:
        task_id = publish_import_job(job_id)
        if task_id is not None:
            with SessionLocal() as session:
                integration_services.mark_job_dispatched(session, job_id)
            published += 1
    return {"eligible": len(job_ids), "published": published}


@celery_app.task(name="imports.recover_stale")
def recover_stale_imports_task() -> dict[str, int]:
    with SessionLocal() as session:
        recovered_ids = integration_services.recover_stale_imports(session)
    published = 0
    for job_id in recovered_ids:
        if publish_import_job(job_id) is not None:
            with SessionLocal() as session:
                integration_services.mark_job_dispatched(session, job_id)
            published += 1
    return {"recovered": len(recovered_ids), "published": published}
