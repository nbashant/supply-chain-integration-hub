from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from supply_chain_hub.api.schemas import (
    ProductMappingUpsert,
    ShipmentEventCreate,
    WarehouseMappingUpsert,
)
from supply_chain_hub.application import learning_services, services
from supply_chain_hub.domain.enums import (
    ImportAttemptStatus,
    ImportSourceType,
    ImportStatus,
)
from supply_chain_hub.domain.exceptions import (
    PermanentImportError,
    ResourceConflictError,
    ResourceNotFoundError,
    ResourceUnavailableError,
    TransientImportError,
)
from supply_chain_hub.infrastructure.db import models
from supply_chain_hub.infrastructure.object_storage import (
    ObjectNotFoundError,
    ObjectStorageError,
    get_object_store,
)
from supply_chain_hub.integrations.base import (
    AdapterError,
    CanonicalInventoryRecord,
    CanonicalShipmentEvent,
    InventoryAdapterResult,
)
from supply_chain_hub.integrations.supplier_a import (
    SupplierAInventoryAdapter,
    SupplierAInventoryPayload,
)
from supply_chain_hub.integrations.supplier_b import SupplierBInventoryAdapter
from supply_chain_hub.settings.config import get_settings


@dataclass(frozen=True, slots=True)
class FailureDisposition:
    retry_scheduled: bool
    retry_delay_seconds: int | None
    failure_code: str


def upsert_product_mapping(
    session: Session,
    request: ProductMappingUpsert,
) -> models.SupplierProductMapping:
    services.get_supplier(session, request.supplier_id)
    services.get_product(session, request.product_id)
    mapping = session.scalar(
        select(models.SupplierProductMapping).where(
            models.SupplierProductMapping.supplier_id == request.supplier_id,
            models.SupplierProductMapping.external_sku == request.external_sku,
        )
    )
    if mapping is None:
        mapping = models.SupplierProductMapping(
            supplier_id=request.supplier_id,
            external_sku=request.external_sku,
            product_id=request.product_id,
            source_unit=request.source_unit,
            units_per_source_unit=request.units_per_source_unit,
            active=request.active,
        )
        session.add(mapping)
    else:
        changed = (
            mapping.product_id != request.product_id
            or mapping.source_unit != request.source_unit
            or mapping.units_per_source_unit != request.units_per_source_unit
            or mapping.active != request.active
        )
        if changed:
            mapping.product_id = request.product_id
            mapping.source_unit = request.source_unit
            mapping.units_per_source_unit = request.units_per_source_unit
            mapping.active = request.active
            mapping.version += 1

    _commit(session, "The supplier product mapping could not be saved.")
    session.refresh(mapping)
    return mapping


def upsert_warehouse_mapping(
    session: Session,
    request: WarehouseMappingUpsert,
) -> models.SupplierWarehouseMapping:
    services.get_supplier(session, request.supplier_id)
    services.get_warehouse(session, request.warehouse_id)
    mapping = session.scalar(
        select(models.SupplierWarehouseMapping).where(
            models.SupplierWarehouseMapping.supplier_id == request.supplier_id,
            models.SupplierWarehouseMapping.external_location
            == request.external_location,
        )
    )
    if mapping is None:
        mapping = models.SupplierWarehouseMapping(
            supplier_id=request.supplier_id,
            external_location=request.external_location,
            warehouse_id=request.warehouse_id,
            active=request.active,
        )
        session.add(mapping)
    else:
        changed = (
            mapping.warehouse_id != request.warehouse_id
            or mapping.active != request.active
        )
        if changed:
            mapping.warehouse_id = request.warehouse_id
            mapping.active = request.active
            mapping.version += 1

    _commit(session, "The supplier warehouse mapping could not be saved.")
    session.refresh(mapping)
    return mapping


def get_import_job(session: Session, import_job_id: UUID) -> models.ImportJob:
    job = session.get(models.ImportJob, import_job_id)
    if job is None:
        raise ResourceNotFoundError(f"Import job '{import_job_id}' was not found.")
    return job


def list_import_errors(
    session: Session,
    import_job_id: UUID,
) -> Sequence[models.ImportJobError]:
    get_import_job(session, import_job_id)
    return session.scalars(
        select(models.ImportJobError)
        .where(models.ImportJobError.import_job_id == import_job_id)
        .order_by(models.ImportJobError.source_row, models.ImportJobError.created_at)
    ).all()


def list_import_attempts(
    session: Session,
    import_job_id: UUID,
) -> Sequence[models.ImportAttempt]:
    get_import_job(session, import_job_id)
    return session.scalars(
        select(models.ImportAttempt)
        .where(models.ImportAttempt.import_job_id == import_job_id)
        .order_by(models.ImportAttempt.attempt_number)
    ).all()


def submit_inventory_import(
    session: Session,
    *,
    supplier_code: str,
    source_type: ImportSourceType,
    adapter_version: str,
    content: bytes,
    content_sha256: str,
    content_type: str,
    idempotency_key: str,
    original_filename: str | None = None,
    replay_of_job_id: UUID | None = None,
    correlation_id: str | None = None,
) -> tuple[models.ImportJob, bool]:
    supplier = _get_supplier_by_code(session, supplier_code)
    existing = session.scalar(
        select(models.ImportJob).where(
            models.ImportJob.supplier_id == supplier.id,
            models.ImportJob.source_type == source_type,
            models.ImportJob.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        if existing.content_sha256 != content_sha256:
            raise ResourceConflictError(
                "This Idempotency-Key was already used with different content."
            )
        return existing, False

    settings = get_settings()
    object_key = build_raw_object_key(
        source_type=source_type,
        content_sha256=content_sha256,
    )
    try:
        stored_object = get_object_store().put(
            object_key,
            content,
            content_type=content_type,
            sha256=content_sha256,
        )
    except ObjectStorageError as error:
        raise ResourceUnavailableError(
            "The raw-data object store is unavailable; the import was not queued."
        ) from error
    job = models.ImportJob(
        id=uuid4(),
        supplier_id=supplier.id,
        source_type=source_type,
        adapter_version=adapter_version,
        original_filename=original_filename,
        content_sha256=content_sha256,
        content_type=content_type,
        payload=None,
        payload_object_key=stored_object.key,
        payload_size_bytes=stored_object.size_bytes,
        idempotency_key=idempotency_key,
        status=ImportStatus.QUEUED,
        max_attempts=settings.import_max_attempts,
        replay_of_job_id=replay_of_job_id,
        correlation_id=correlation_id,
    )
    session.add(job)
    learning_services.record_import_event(
        session,
        job,
        component="FastAPI",
        stage="request.validated",
        status="succeeded",
        title="The message passed its checks",
        explanation=(
            "The hub recognized the supplier, found every required field, "
            "and confirmed this was not an accidental duplicate."
        ),
        evidence_reference=f"import_jobs/{job.id}",
        details={
            "source_type": source_type.value,
            "adapter_version": adapter_version,
            "content_type": content_type,
        },
    )
    learning_services.record_import_event(
        session,
        job,
        component="SeaweedFS",
        stage="payload.stored",
        status="succeeded",
        title="An untouched copy was saved",
        explanation=(
            "The exact message that arrived was saved before anything was "
            "translated, so it can always be checked again."
        ),
        evidence_reference=stored_object.key,
        details={
            "size_bytes": stored_object.size_bytes,
            "sha256_prefix": content_sha256[:12],
        },
    )
    learning_services.record_import_event(
        session,
        job,
        component="PostgreSQL",
        stage="job.queued",
        status="succeeded",
        title="A work ticket was written",
        explanation=(
            "The hub wrote down what needs to happen, where the original copy "
            "lives, and how many times the work may be tried."
        ),
        evidence_reference=f"import_jobs/{job.id}",
        details={"status": ImportStatus.QUEUED.value},
    )
    _commit(session, "The import submission conflicts with an existing request.")
    session.refresh(job)
    return job, True


def mark_job_dispatched(
    session: Session,
    import_job_id: UUID,
    *,
    dispatched_at: datetime | None = None,
) -> models.ImportJob:
    job = get_import_job(session, import_job_id)
    if job.status is ImportStatus.QUEUED:
        job.dispatched_at = dispatched_at or datetime.now(UTC)
        learning_services.record_import_event(
            session,
            job,
            component="Redis",
            stage="job.dispatched",
            status="succeeded",
            title="The ticket number was sent to a worker",
            explanation=(
                "Only the ticket number entered the fast waiting line. The "
                "larger supplier file stayed safely in storage."
            ),
            evidence_reference=f"import_jobs/{job.id}",
            details={"dispatched_at": job.dispatched_at.isoformat()},
        )
        session.commit()
        session.refresh(job)
    return job


def execute_import_job(
    session: Session,
    import_job_id: UUID,
    *,
    worker_id: str,
    celery_task_id: str | None,
) -> models.ImportJob:
    now = datetime.now(UTC)
    job = session.scalar(
        select(models.ImportJob)
        .where(models.ImportJob.id == import_job_id)
        .with_for_update()
    )
    if job is None:
        raise ResourceNotFoundError(f"Import job '{import_job_id}' was not found.")
    if job.status is not ImportStatus.QUEUED:
        return job
    if job.next_retry_at is not None and _as_utc(job.next_retry_at) > now:
        return job
    job.status = ImportStatus.PROCESSING
    job.attempt_count += 1
    job.started_at = job.started_at or now
    job.completed_at = None
    job.next_retry_at = None
    job.lease_expires_at = now + timedelta(seconds=get_settings().import_lease_seconds)
    job.worker_id = worker_id
    job.failure_code = None
    job.failure_message = None
    job.last_error_retryable = None
    attempt = models.ImportAttempt(
        import_job_id=job.id,
        attempt_number=job.attempt_count,
        celery_task_id=celery_task_id,
        worker_id=worker_id,
    )
    session.add(attempt)
    learning_services.record_import_event(
        session,
        job,
        component="Celery",
        stage="worker.claimed",
        status="running",
        title="A worker picked up the ticket",
        explanation=(
            "A background worker took responsibility for this try and recorded "
            "that it had started."
        ),
        evidence_reference=f"import_attempts/{job.id}/{job.attempt_count}",
        details={
            "attempt_number": job.attempt_count,
            "worker_id": worker_id,
            "celery_task_id": celery_task_id,
        },
    )
    session.commit()

    job = get_import_job(session, import_job_id)
    result = _adapt_retained_payload(job)
    learning_services.record_import_event(
        session,
        job,
        component="SeaweedFS",
        stage="payload.verified",
        status="succeeded",
        title="The saved copy still matches",
        explanation=(
            "The worker compared the saved file's fingerprint with the one "
            "recorded at arrival. They match."
        ),
        evidence_reference=job.payload_object_key,
        details={"sha256_prefix": job.content_sha256[:12]},
    )
    learning_services.record_import_event(
        session,
        job,
        component="Adapter",
        stage="payload.transformed",
        status="succeeded",
        title="Supplier names were translated",
        explanation=(
            "The worker used agreed rules to turn the supplier's product, "
            "location, and quantities into the hub's shared language."
        ),
        evidence_reference=f"adapter/{job.adapter_version}",
        details={
            "candidate_records": len(result.records),
            "adapter_errors": len(result.errors),
        },
    )
    _apply_inventory_result(session, job=job, supplier=job.supplier, result=result)
    job.status = (
        ImportStatus.COMPLETED
        if job.rejected_records == 0
        else ImportStatus.COMPLETED_WITH_ERRORS
    )
    job.completed_at = datetime.now(UTC)
    job.lease_expires_at = None
    job.worker_id = None
    attempt = _get_current_attempt(session, job)
    attempt.status = ImportAttemptStatus.SUCCEEDED
    attempt.completed_at = job.completed_at
    learning_services.record_import_event(
        session,
        job,
        component="PostgreSQL",
        stage="inventory.committed",
        status="succeeded",
        title="Inventory was updated",
        explanation=(
            "The translated quantities are now part of the official inventory "
            "record, with a link back to the supplier message."
        ),
        evidence_reference=f"inventory_snapshots?import_job_id={job.id}",
        details={
            "total_records": job.total_records,
            "accepted_records": job.accepted_records,
            "rejected_records": job.rejected_records,
        },
    )
    learning_services.record_import_event(
        session,
        job,
        component="Celery",
        stage="job.completed",
        status="succeeded",
        title="The worker finished",
        explanation=("The worker closed its ticket and recorded the final outcome."),
        evidence_reference=f"import_jobs/{job.id}",
        details={"status": job.status.value},
    )
    session.commit()
    session.refresh(job)
    return job


def record_import_failure(
    session: Session,
    import_job_id: UUID,
    error: Exception,
    *,
    worker_id: str = "unknown-worker",
    celery_task_id: str | None = None,
) -> FailureDisposition:
    session.rollback()
    job = session.scalar(
        select(models.ImportJob)
        .where(models.ImportJob.id == import_job_id)
        .with_for_update()
    )
    if job is None:
        raise ResourceNotFoundError(f"Import job '{import_job_id}' was not found.")
    now = datetime.now(UTC)
    attempt = _find_current_attempt(session, job)
    if attempt is None:
        job.attempt_count += 1
        attempt = models.ImportAttempt(
            import_job_id=job.id,
            attempt_number=job.attempt_count,
            celery_task_id=celery_task_id,
            worker_id=worker_id,
        )
        session.add(attempt)
    retryable, failure_code = classify_import_failure(error)
    retry_scheduled = retryable and job.attempt_count < job.max_attempts
    retry_delay = calculate_retry_delay(job.attempt_count) if retry_scheduled else None
    job.failure_code = failure_code
    job.failure_message = str(error)[:1000]
    job.last_error_retryable = retryable
    job.lease_expires_at = None
    job.worker_id = None
    job.dispatched_at = None
    attempt.error_code = failure_code
    attempt.error_message = str(error)[:1000]
    attempt.retryable = retryable
    attempt.completed_at = now
    if retry_scheduled:
        job.status = ImportStatus.QUEUED
        job.next_retry_at = now + timedelta(seconds=retry_delay or 0)
        attempt.status = ImportAttemptStatus.RETRY_SCHEDULED
        learning_services.record_import_event(
            session,
            job,
            component="Celery",
            stage="job.retry_scheduled",
            status="warning",
            title="Retry scheduled",
            explanation=(
                "The failure looks temporary, so the job returned to the queue "
                "with a controlled backoff instead of losing the request."
            ),
            evidence_reference=f"import_attempts/{job.id}/{job.attempt_count}",
            details={
                "failure_code": failure_code,
                "delay_seconds": retry_delay,
            },
        )
    else:
        job.status = ImportStatus.FAILED
        job.completed_at = now
        job.next_retry_at = None
        attempt.status = ImportAttemptStatus.FAILED
        learning_services.record_import_event(
            session,
            job,
            component="Celery",
            stage="job.failed",
            status="failed",
            title="Import stopped safely",
            explanation=(
                "The job exhausted its retry policy or encountered a permanent "
                "problem. Its evidence remains available for inspection."
            ),
            evidence_reference=f"import_jobs/{job.id}",
            details={"failure_code": failure_code, "retryable": retryable},
        )
    session.commit()
    return FailureDisposition(
        retry_scheduled=retry_scheduled,
        retry_delay_seconds=retry_delay,
        failure_code=failure_code,
    )


def classify_import_failure(error: Exception) -> tuple[bool, str]:
    if isinstance(error, OperationalError):
        return True, "transient_database_error"
    if isinstance(error, TransientImportError):
        return True, "transient_import_error"
    if isinstance(error, TimeoutError):
        return True, "transient_timeout"
    if isinstance(error, ConnectionError):
        return True, "transient_connection_error"
    if isinstance(error, PermanentImportError):
        return False, "permanent_import_error"
    return False, "unexpected_import_error"


def calculate_retry_delay(attempt_count: int) -> int:
    settings = get_settings()
    exponent = max(attempt_count - 1, 0)
    return int(
        min(
            settings.import_retry_base_seconds * (2**exponent),
            settings.import_retry_max_seconds,
        )
    )


def jobs_due_for_dispatch(
    session: Session,
    *,
    limit: int = 100,
) -> Sequence[models.ImportJob]:
    now = datetime.now(UTC)
    redispatch_before = now - timedelta(
        seconds=get_settings().import_redispatch_seconds
    )
    return session.scalars(
        select(models.ImportJob)
        .where(
            models.ImportJob.status == ImportStatus.QUEUED,
            or_(
                models.ImportJob.next_retry_at.is_(None),
                models.ImportJob.next_retry_at <= now,
            ),
            or_(
                models.ImportJob.dispatched_at.is_(None),
                models.ImportJob.dispatched_at <= redispatch_before,
            ),
        )
        .order_by(models.ImportJob.created_at)
        .limit(limit)
    ).all()


def recover_stale_imports(session: Session) -> list[UUID]:
    now = datetime.now(UTC)
    jobs = session.scalars(
        select(models.ImportJob)
        .where(
            models.ImportJob.status == ImportStatus.PROCESSING,
            models.ImportJob.lease_expires_at.is_not(None),
            models.ImportJob.lease_expires_at < now,
        )
        .with_for_update(skip_locked=True)
    ).all()
    recovered: list[UUID] = []
    for job in jobs:
        attempt = _get_current_attempt(session, job)
        attempt.status = ImportAttemptStatus.ABANDONED
        attempt.completed_at = now
        attempt.error_code = "worker_lease_expired"
        attempt.error_message = "The worker lease expired before completion."
        attempt.retryable = True
        job.failure_code = "worker_lease_expired"
        job.failure_message = attempt.error_message
        job.last_error_retryable = True
        job.lease_expires_at = None
        job.worker_id = None
        job.dispatched_at = None
        if job.attempt_count < job.max_attempts:
            job.status = ImportStatus.QUEUED
            job.next_retry_at = now
            recovered.append(job.id)
        else:
            job.status = ImportStatus.FAILED
            job.completed_at = now
    session.commit()
    return recovered


def replay_failed_import(
    session: Session,
    import_job_id: UUID,
    *,
    idempotency_key: str,
) -> tuple[models.ImportJob, bool]:
    original = get_import_job(session, import_job_id)
    if original.status is not ImportStatus.FAILED:
        raise ResourceConflictError("Only failed imports can be replayed.")
    if original.payload is None and original.payload_object_key is None:
        raise ResourceConflictError(
            "This import has no retained payload and cannot be replayed."
        )
    try:
        content = _load_import_payload(original)
    except PermanentImportError as error:
        raise ResourceConflictError(str(error)) from error
    except TransientImportError as error:
        raise ResourceUnavailableError(str(error)) from error
    return submit_inventory_import(
        session,
        supplier_code=original.supplier.code,
        source_type=original.source_type,
        adapter_version=original.adapter_version,
        content=content,
        content_sha256=original.content_sha256,
        content_type=original.content_type,
        idempotency_key=idempotency_key,
        original_filename=original.original_filename,
        replay_of_job_id=original.id,
    )


def process_inventory_import(
    session: Session,
    *,
    supplier_code: str,
    source_type: ImportSourceType,
    adapter_version: str,
    content_sha256: str,
    result: InventoryAdapterResult,
    original_filename: str | None = None,
) -> models.ImportJob:
    supplier = _get_supplier_by_code(session, supplier_code)
    job = models.ImportJob(
        supplier_id=supplier.id,
        source_type=source_type,
        adapter_version=adapter_version,
        original_filename=original_filename,
        content_sha256=content_sha256,
        status=ImportStatus.PROCESSING,
        started_at=datetime.now(UTC),
    )
    session.add(job)
    session.flush()
    _apply_inventory_result(session, job=job, supplier=supplier, result=result)
    job.status = (
        ImportStatus.COMPLETED
        if job.rejected_records == 0
        else ImportStatus.COMPLETED_WITH_ERRORS
    )
    job.completed_at = datetime.now(UTC)
    _commit(session, "The inventory import conflicts with an existing snapshot.")
    session.refresh(job)
    return job


def process_carrier_event(
    session: Session,
    event: CanonicalShipmentEvent,
) -> models.Shipment:
    shipments = session.scalars(
        select(models.Shipment).where(
            models.Shipment.tracking_reference == event.tracking_reference
        )
    ).all()
    if not shipments:
        raise ResourceNotFoundError(
            f"Shipment tracking reference '{event.tracking_reference}' was not found."
        )
    if len(shipments) > 1:
        raise ResourceConflictError(
            "The tracking reference matches multiple suppliers; "
            "the Carrier C event is ambiguous."
        )
    shipment = shipments[0]
    return services.add_shipment_event(
        session,
        shipment_id=shipment.id,
        request=ShipmentEventCreate(
            external_event_id=event.external_event_id,
            event_type=event.event_type,
            occurred_at=event.occurred_at,
            reason_code=event.reason_code,
        ),
    )


def _adapt_retained_payload(job: models.ImportJob) -> InventoryAdapterResult:
    payload_bytes = _load_import_payload(job)
    if job.source_type is ImportSourceType.SUPPLIER_A_JSON:
        payload = SupplierAInventoryPayload.model_validate_json(payload_bytes)
        return SupplierAInventoryAdapter().adapt(payload)
    if job.source_type is ImportSourceType.SUPPLIER_B_CSV:
        return SupplierBInventoryAdapter().adapt(payload_bytes)
    raise PermanentImportError(
        f"No adapter is registered for source type '{job.source_type.value}'."
    )


def build_raw_object_key(
    *,
    source_type: ImportSourceType,
    content_sha256: str,
    observed_at: datetime | None = None,
) -> str:
    date_part = (observed_at or datetime.now(UTC)).date().isoformat()
    extension = "json" if source_type is ImportSourceType.SUPPLIER_A_JSON else "csv"
    return (
        "raw/inventory/"
        f"source={source_type.value}/"
        f"ingest_date={date_part}/"
        f"{content_sha256}.{extension}"
    )


def _load_import_payload(job: models.ImportJob) -> bytes:
    if job.payload_object_key is not None:
        try:
            content = get_object_store().get(job.payload_object_key)
        except ObjectNotFoundError as error:
            raise PermanentImportError(
                f"The retained object '{job.payload_object_key}' was not found."
            ) from error
        except ObjectStorageError as error:
            raise TransientImportError(
                "The raw-data object store is temporarily unavailable."
            ) from error
    elif job.payload is not None:
        content = job.payload
    else:
        raise PermanentImportError("The import payload is not available.")
    if sha256(content).hexdigest() != job.content_sha256:
        raise PermanentImportError(
            "The retained import payload does not match its recorded checksum."
        )
    return content


def _apply_inventory_result(
    session: Session,
    *,
    job: models.ImportJob,
    supplier: models.Supplier,
    result: InventoryAdapterResult,
) -> None:
    for error in result.errors:
        _add_import_error(job, error)

    accepted = 0
    seen_source_records: set[tuple[str, str, str]] = set()
    for record in result.records:
        validation_error = _validate_and_apply_record(
            session,
            job=job,
            supplier=supplier,
            record=record,
            seen_source_records=seen_source_records,
        )
        if validation_error is None:
            accepted += 1
        else:
            _add_import_error(job, validation_error)

    rejected_rows = {
        error.source_row for error in job.errors if error.source_row is not None
    }
    file_rejection = int(any(error.source_row is None for error in job.errors))
    rejected = len(rejected_rows) + file_rejection
    job.total_records = accepted + rejected
    job.accepted_records = accepted
    job.rejected_records = rejected


def _validate_and_apply_record(
    session: Session,
    *,
    job: models.ImportJob,
    supplier: models.Supplier,
    record: CanonicalInventoryRecord,
    seen_source_records: set[tuple[str, str, str]],
) -> AdapterError | None:
    source_key = (
        record.source_reference,
        record.external_sku,
        record.external_location,
    )
    if source_key in seen_source_records or session.scalar(
        select(models.InventorySnapshot.id).where(
            models.InventorySnapshot.supplier_id == supplier.id,
            models.InventorySnapshot.source_reference == record.source_reference,
            models.InventorySnapshot.external_sku == record.external_sku,
            models.InventorySnapshot.external_location == record.external_location,
        )
    ):
        return _record_error(
            record,
            "duplicate_source_record",
            "This partner snapshot record has already been imported.",
        )
    seen_source_records.add(source_key)

    product_mapping = session.scalar(
        select(models.SupplierProductMapping).where(
            models.SupplierProductMapping.supplier_id == supplier.id,
            models.SupplierProductMapping.external_sku == record.external_sku,
            models.SupplierProductMapping.active.is_(True),
        )
    )
    if product_mapping is None:
        return _record_error(
            record,
            "product_mapping_not_found",
            f"No active product mapping exists for '{record.external_sku}'.",
            "external_sku",
        )

    warehouse_mapping = session.scalar(
        select(models.SupplierWarehouseMapping).where(
            models.SupplierWarehouseMapping.supplier_id == supplier.id,
            models.SupplierWarehouseMapping.external_location
            == record.external_location,
            models.SupplierWarehouseMapping.active.is_(True),
        )
    )
    if warehouse_mapping is None:
        return _record_error(
            record,
            "warehouse_mapping_not_found",
            f"No active warehouse mapping exists for '{record.external_location}'.",
            "external_location",
        )

    if product_mapping.source_unit != record.source_unit:
        return _record_error(
            record,
            "source_unit_mismatch",
            f"Expected {product_mapping.source_unit.value}, "
            f"received {record.source_unit.value}.",
            "source_unit",
        )

    conversion_factor = product_mapping.units_per_source_unit
    if (
        record.units_per_source_unit is not None
        and record.units_per_source_unit != conversion_factor
    ):
        return _record_error(
            record,
            "unit_conversion_mismatch",
            f"Configured conversion is {conversion_factor}; "
            f"the partner sent {record.units_per_source_unit}.",
            "units_per_source_unit",
        )

    on_hand = record.on_hand_quantity * conversion_factor
    reserved = record.reserved_quantity * conversion_factor
    position = session.scalar(
        select(models.InventoryPosition).where(
            models.InventoryPosition.warehouse_id == warehouse_mapping.warehouse_id,
            models.InventoryPosition.product_id == product_mapping.product_id,
        )
    )
    if position is None:
        position = models.InventoryPosition(
            warehouse_id=warehouse_mapping.warehouse_id,
            product_id=product_mapping.product_id,
            on_hand_quantity=on_hand,
            reserved_quantity=reserved,
        )
        session.add(position)
    else:
        position.on_hand_quantity = on_hand
        position.reserved_quantity = reserved
        position.version += 1

    session.add(
        models.InventorySnapshot(
            import_job_id=job.id,
            supplier_id=supplier.id,
            product_id=product_mapping.product_id,
            warehouse_id=warehouse_mapping.warehouse_id,
            source_reference=record.source_reference,
            external_sku=record.external_sku,
            external_location=record.external_location,
            observed_at=record.observed_at,
            on_hand_quantity=on_hand,
            reserved_quantity=reserved,
            source_unit=record.source_unit,
            units_per_source_unit=conversion_factor,
            product_mapping_version=product_mapping.version,
            warehouse_mapping_version=warehouse_mapping.version,
            source_row=record.source_row,
            raw_fragment=record.raw_fragment,
        )
    )
    session.flush()
    return None


def _get_supplier_by_code(session: Session, code: str) -> models.Supplier:
    supplier = session.scalar(
        select(models.Supplier).where(models.Supplier.code == code)
    )
    if supplier is None:
        raise ResourceNotFoundError(
            f"Supplier code '{code}' is not configured for this integration."
        )
    return supplier


def _get_current_attempt(
    session: Session,
    job: models.ImportJob,
) -> models.ImportAttempt:
    attempt = _find_current_attempt(session, job)
    if attempt is None:
        raise PermanentImportError(
            f"Import job '{job.id}' has no durable current attempt."
        )
    return attempt


def _find_current_attempt(
    session: Session,
    job: models.ImportJob,
) -> models.ImportAttempt | None:
    return session.scalar(
        select(models.ImportAttempt).where(
            models.ImportAttempt.import_job_id == job.id,
            models.ImportAttempt.attempt_number == job.attempt_count,
        )
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _add_import_error(job: models.ImportJob, error: AdapterError) -> None:
    job.errors.append(
        models.ImportJobError(
            source_row=error.source_row,
            error_code=error.code,
            field_name=error.field_name,
            message=error.message,
            raw_fragment=error.raw_fragment,
        )
    )


def _record_error(
    record: CanonicalInventoryRecord,
    code: str,
    message: str,
    field_name: str | None = None,
) -> AdapterError:
    return AdapterError(
        code=code,
        message=message,
        source_row=record.source_row,
        field_name=field_name,
        raw_fragment=record.raw_fragment,
    )


def _commit(session: Session, conflict_message: str) -> None:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ResourceConflictError(conflict_message) from error
