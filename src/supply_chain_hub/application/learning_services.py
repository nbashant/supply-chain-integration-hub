from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from supply_chain_hub.infrastructure.db import models


def record_import_event(
    session: Session,
    job: models.ImportJob,
    *,
    component: str,
    stage: str,
    status: str,
    title: str,
    explanation: str,
    evidence_reference: str | None = None,
    details: dict[str, Any] | None = None,
) -> models.OperationEvent:
    """Append safe teaching evidence without storing partner payload content."""
    event = models.OperationEvent(
        import_job_id=job.id,
        correlation_id=job.correlation_id,
        component=component,
        stage=stage,
        status=status,
        title=title,
        explanation=explanation,
        evidence_reference=evidence_reference,
        details=details or {},
        occurred_at=datetime.now(UTC),
    )
    session.add(event)
    return event


def list_import_events(
    session: Session,
    import_job_id: UUID,
    *,
    after_id: UUID | None = None,
) -> Sequence[models.OperationEvent]:
    statement = (
        select(models.OperationEvent)
        .where(models.OperationEvent.import_job_id == import_job_id)
        .order_by(models.OperationEvent.occurred_at, models.OperationEvent.id)
    )
    if after_id is not None:
        prior_event = session.get(models.OperationEvent, after_id)
        if prior_event is not None:
            statement = statement.where(
                models.OperationEvent.occurred_at >= prior_event.occurred_at,
                models.OperationEvent.id != prior_event.id,
            )
    return session.scalars(statement).all()
