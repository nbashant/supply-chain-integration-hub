from hashlib import sha256
from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, UploadFile, status

from supply_chain_hub.api.dependencies import DatabaseSession
from supply_chain_hub.api.headers import IdempotencyKey
from supply_chain_hub.api.schemas import ImportJobResponse, ShipmentResponse
from supply_chain_hub.api.security import require_partner_token
from supply_chain_hub.application import integration_services
from supply_chain_hub.domain.enums import ImportSourceType, ImportStatus
from supply_chain_hub.domain.exceptions import DomainValidationError
from supply_chain_hub.infrastructure.db import models
from supply_chain_hub.infrastructure.observability import current_correlation_id
from supply_chain_hub.integrations.carrier_c import (
    CarrierCAdapter,
    CarrierCEvent,
)
from supply_chain_hub.integrations.supplier_a import (
    SupplierAInventoryAdapter,
    SupplierAInventoryPayload,
)
from supply_chain_hub.integrations.supplier_b import SupplierBInventoryAdapter
from supply_chain_hub.worker.queueing import publish_import_job

router = APIRouter(
    prefix="/api/v1",
    tags=["partner integrations"],
    dependencies=[Depends(require_partner_token)],
)

MAX_CSV_BYTES = 10 * 1024 * 1024
CSVUpload = Annotated[UploadFile, File()]


@router.post(
    "/integrations/supplier-a/inventory",
    response_model=ImportJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def import_supplier_a_inventory(
    request: SupplierAInventoryPayload,
    session: DatabaseSession,
    raw_request: Request,
    idempotency_key: IdempotencyKey,
) -> ImportJobResponse:
    adapter = SupplierAInventoryAdapter()
    content = await raw_request.body()
    job, _ = integration_services.submit_inventory_import(
        session,
        supplier_code="SUPPLIER_A",
        source_type=ImportSourceType.SUPPLIER_A_JSON,
        adapter_version=adapter.adapter_version,
        content=content,
        content_sha256=sha256(content).hexdigest(),
        content_type="application/json",
        idempotency_key=idempotency_key,
        correlation_id=current_correlation_id(),
    )
    _publish_if_queued(session, job)
    return ImportJobResponse.model_validate(job)


@router.post(
    "/integrations/supplier-b/inventory-files",
    response_model=ImportJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def import_supplier_b_inventory(
    session: DatabaseSession,
    file: CSVUpload,
    idempotency_key: IdempotencyKey,
) -> ImportJobResponse:
    content = await file.read(MAX_CSV_BYTES + 1)
    if len(content) > MAX_CSV_BYTES:
        raise DomainValidationError("Supplier B CSV files may not exceed 10 MiB.")
    adapter = SupplierBInventoryAdapter()
    job, _ = integration_services.submit_inventory_import(
        session,
        supplier_code="SUPPLIER_B",
        source_type=ImportSourceType.SUPPLIER_B_CSV,
        adapter_version=adapter.adapter_version,
        content=content,
        content_sha256=sha256(content).hexdigest(),
        content_type=file.content_type or "text/csv",
        idempotency_key=idempotency_key,
        original_filename=file.filename,
        correlation_id=current_correlation_id(),
    )
    _publish_if_queued(session, job)
    return ImportJobResponse.model_validate(job)


@router.post(
    "/webhooks/carrier-c",
    response_model=ShipmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def receive_carrier_c_event(
    request: CarrierCEvent,
    session: DatabaseSession,
) -> ShipmentResponse:
    event = CarrierCAdapter().adapt(request)
    shipment = integration_services.process_carrier_event(session, event)
    return ShipmentResponse.model_validate(shipment)


def _publish_if_queued(
    session: DatabaseSession,
    job: models.ImportJob,
) -> None:
    if job.status is not ImportStatus.QUEUED:
        return
    if publish_import_job(job.id) is not None:
        integration_services.mark_job_dispatched(session, job.id)
