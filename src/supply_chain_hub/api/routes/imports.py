from uuid import UUID

from fastapi import APIRouter, status

from supply_chain_hub.api.dependencies import DatabaseSession
from supply_chain_hub.api.headers import IdempotencyKey
from supply_chain_hub.api.schemas import (
    ImportAttemptResponse,
    ImportErrorResponse,
    ImportJobResponse,
)
from supply_chain_hub.application import integration_services
from supply_chain_hub.domain.enums import ImportStatus
from supply_chain_hub.infrastructure.db import models
from supply_chain_hub.worker.queueing import publish_import_job

router = APIRouter(prefix="/api/v1/imports", tags=["imports"])


@router.get("/{import_job_id}", response_model=ImportJobResponse)
def get_one(
    import_job_id: UUID,
    session: DatabaseSession,
) -> ImportJobResponse:
    job = integration_services.get_import_job(session, import_job_id)
    return ImportJobResponse.model_validate(job)


@router.get(
    "/{import_job_id}/errors",
    response_model=list[ImportErrorResponse],
)
def list_errors(
    import_job_id: UUID,
    session: DatabaseSession,
) -> list[ImportErrorResponse]:
    errors = integration_services.list_import_errors(session, import_job_id)
    return [ImportErrorResponse.model_validate(error) for error in errors]


@router.get(
    "/{import_job_id}/attempts",
    response_model=list[ImportAttemptResponse],
)
def list_attempts(
    import_job_id: UUID,
    session: DatabaseSession,
) -> list[ImportAttemptResponse]:
    attempts = integration_services.list_import_attempts(session, import_job_id)
    return [ImportAttemptResponse.model_validate(attempt) for attempt in attempts]


@router.post(
    "/{import_job_id}/retries",
    response_model=ImportJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def replay_failed(
    import_job_id: UUID,
    session: DatabaseSession,
    idempotency_key: IdempotencyKey,
) -> ImportJobResponse:
    job, _ = integration_services.replay_failed_import(
        session,
        import_job_id,
        idempotency_key=idempotency_key,
    )
    _publish_if_queued(session, job)
    return ImportJobResponse.model_validate(job)


def _publish_if_queued(
    session: DatabaseSession,
    job: models.ImportJob,
) -> None:
    if job.status is not ImportStatus.QUEUED:
        return
    if publish_import_job(job.id) is not None:
        integration_services.mark_job_dispatched(session, job.id)
