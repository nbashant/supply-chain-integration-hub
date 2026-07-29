import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from typing import cast
from uuid import UUID, uuid4

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from supply_chain_hub.analytics.benchmark import benchmark_reconciliation
from supply_chain_hub.api.dependencies import DatabaseSession
from supply_chain_hub.api.schemas import (
    AnalyticsRunResponse,
    ImportAttemptResponse,
    ImportErrorResponse,
    ImportJobResponse,
    LearningAnalyticsComparisonRequest,
    LearningComponentStatus,
    LearningDemoResponse,
    LearningImportDetail,
    LearningImportSummary,
    LearningOverview,
    LearningPipelineRun,
    LearningSnapshot,
    OperationEventResponse,
)
from supply_chain_hub.application import integration_services, learning_services
from supply_chain_hub.domain.enums import (
    ImportSourceType,
    ImportStatus,
    UnitOfMeasure,
)
from supply_chain_hub.infrastructure.db import models
from supply_chain_hub.infrastructure.db.base import Base
from supply_chain_hub.infrastructure.object_storage import (
    ObjectStorageError,
    get_object_store,
    object_store_is_available,
)
from supply_chain_hub.infrastructure.observability import current_correlation_id
from supply_chain_hub.infrastructure.redis_client import redis_is_available
from supply_chain_hub.integrations.supplier_a import SupplierAInventoryAdapter
from supply_chain_hub.worker.queueing import publish_import_job

router = APIRouter(prefix="/api/v1/learning", tags=["learning console"])


@router.get("/overview", response_model=LearningOverview)
def get_learning_overview(session: DatabaseSession) -> LearningOverview:
    status_counts = {
        status.value: count
        for status, count in session.execute(
            select(models.ImportJob.status, func.count(models.ImportJob.id)).group_by(
                models.ImportJob.status
            )
        ).all()
    }
    entity_counts = {
        "suppliers": _count(session, models.Supplier),
        "products": _count(session, models.Product),
        "warehouses": _count(session, models.Warehouse),
        "inventory_positions": _count(session, models.InventoryPosition),
        "inventory_snapshots": _count(session, models.InventorySnapshot),
        "analytics_runs": _count(session, models.AnalyticsRun),
        "operation_events": _count(session, models.OperationEvent),
    }
    recent_jobs = session.scalars(
        select(models.ImportJob).order_by(desc(models.ImportJob.created_at)).limit(8)
    ).all()
    recent_events = session.scalars(
        select(models.OperationEvent)
        .order_by(desc(models.OperationEvent.occurred_at))
        .limit(12)
    ).all()
    return LearningOverview(
        components=_component_statuses(),
        import_status_counts=status_counts,
        entity_counts=entity_counts,
        recent_imports=[_import_summary(job) for job in recent_jobs],
        recent_events=[
            OperationEventResponse.model_validate(event) for event in recent_events
        ],
    )


@router.get("/imports", response_model=list[LearningImportSummary])
def list_learning_imports(
    session: DatabaseSession,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[LearningImportSummary]:
    jobs = session.scalars(
        select(models.ImportJob)
        .order_by(desc(models.ImportJob.created_at))
        .limit(limit)
    ).all()
    return [_import_summary(job) for job in jobs]


@router.get("/imports/{import_job_id}", response_model=LearningImportDetail)
def get_learning_import(
    import_job_id: UUID,
    session: DatabaseSession,
) -> LearningImportDetail:
    job = integration_services.get_import_job(session, import_job_id)
    snapshots = session.scalars(
        select(models.InventorySnapshot)
        .where(models.InventorySnapshot.import_job_id == import_job_id)
        .order_by(models.InventorySnapshot.source_row)
    ).all()
    return LearningImportDetail(
        job=ImportJobResponse.model_validate(job),
        supplier_code=job.supplier.code,
        events=[
            OperationEventResponse.model_validate(event)
            for event in learning_services.list_import_events(session, import_job_id)
        ],
        attempts=[
            ImportAttemptResponse.model_validate(attempt)
            for attempt in integration_services.list_import_attempts(
                session,
                import_job_id,
            )
        ],
        errors=[
            ImportErrorResponse.model_validate(error)
            for error in integration_services.list_import_errors(
                session,
                import_job_id,
            )
        ],
        snapshots=[_snapshot_view(snapshot) for snapshot in snapshots],
    )


@router.get("/imports/{import_job_id}/events")
def stream_import_events(
    import_job_id: UUID,
    request: Request,
    session: DatabaseSession,
    follow: bool = True,
) -> StreamingResponse:
    integration_services.get_import_job(session, import_job_id)

    async def event_stream() -> AsyncIterator[str]:
        seen: set[UUID] = set()
        waited_seconds = 0.0
        while True:
            if await request.is_disconnected():
                break
            session.expire_all()
            events = learning_services.list_import_events(session, import_job_id)
            for event in events:
                if event.id in seen:
                    continue
                seen.add(event.id)
                payload = OperationEventResponse.model_validate(event).model_dump_json()
                yield f"id: {event.id}\nevent: operation\ndata: {payload}\n\n"
            job = integration_services.get_import_job(session, import_job_id)
            terminal = job.status in {
                ImportStatus.COMPLETED,
                ImportStatus.COMPLETED_WITH_ERRORS,
                ImportStatus.FAILED,
            }
            if not follow or terminal:
                yield (f'event: complete\ndata: {{"status":"{job.status.value}"}}\n\n')
                break
            await asyncio.sleep(0.6)
            waited_seconds += 0.6
            if waited_seconds >= 120:
                yield 'event: timeout\ndata: {"status":"still_running"}\n\n'
                break

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},
    )


@router.post(
    "/demos/import",
    response_model=LearningDemoResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def run_import_demo(session: DatabaseSession) -> LearningDemoResponse:
    """Create only clearly labeled synthetic data and run the real import path."""
    suffix = uuid4().hex[:8].upper()
    supplier = session.scalar(
        select(models.Supplier).where(models.Supplier.code == "SUPPLIER_A")
    )
    if supplier is None:
        supplier = models.Supplier(code="SUPPLIER_A", name="Supplier A")
        session.add(supplier)
        session.flush()

    external_sku = f"LEARN-{suffix}"
    external_location = f"SUPPLIER-WEST-{suffix}"
    product = models.Product(
        sku=f"DEMO-{suffix}",
        name=f"Learning Demo Product {suffix}",
        base_unit=UnitOfMeasure.EACH,
    )
    warehouse = models.Warehouse(
        code=f"WEST-{suffix}",
        name=f"West Coast Learning Warehouse {suffix}",
        timezone="America/Los_Angeles",
    )
    session.add_all([product, warehouse])
    session.flush()
    session.add_all(
        [
            models.SupplierProductMapping(
                supplier_id=supplier.id,
                external_sku=external_sku,
                product_id=product.id,
                source_unit=UnitOfMeasure.EACH,
                units_per_source_unit=Decimal("1"),
            ),
            models.SupplierWarehouseMapping(
                supplier_id=supplier.id,
                external_location=external_location,
                warehouse_id=warehouse.id,
            ),
        ]
    )
    captured_at = datetime.now(UTC)
    demo_input: dict[str, object] = {
        "snapshot_id": f"LEARNING-{suffix}",
        "captured_at": captured_at.isoformat(),
        "items": [
            {
                "item_number": external_sku,
                "location": external_location,
                "on_hand": "120.000",
                "allocated": "35.000",
                "unit": "EACH",
            }
        ],
    }
    content = json.dumps(demo_input, separators=(",", ":")).encode()
    adapter = SupplierAInventoryAdapter()
    job, created = integration_services.submit_inventory_import(
        session,
        supplier_code=supplier.code,
        source_type=ImportSourceType.SUPPLIER_A_JSON,
        adapter_version=adapter.adapter_version,
        content=content,
        content_sha256=sha256(content).hexdigest(),
        content_type="application/json",
        idempotency_key=f"learning-demo-{suffix.lower()}",
        original_filename=f"learning-demo-{suffix.lower()}.json",
        correlation_id=current_correlation_id(),
    )
    if publish_import_job(job.id) is not None:
        integration_services.mark_job_dispatched(session, job.id)
    return LearningDemoResponse(
        job=ImportJobResponse.model_validate(job),
        created=created,
        demo_input=demo_input,
    )


@router.get("/analytics", response_model=list[AnalyticsRunResponse])
def list_learning_analytics(
    session: DatabaseSession,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[AnalyticsRunResponse]:
    runs = session.scalars(
        select(models.AnalyticsRun)
        .order_by(desc(models.AnalyticsRun.created_at))
        .limit(limit)
    ).all()
    return [AnalyticsRunResponse.model_validate(run) for run in runs]


@router.post("/analytics/compare", response_model=dict[str, object])
def compare_learning_analytics(
    request: LearningAnalyticsComparisonRequest,
) -> dict[str, object]:
    """Run equivalent work repeatedly so the UI can make an honest comparison."""
    return benchmark_reconciliation(
        row_count=request.row_count,
        seed=request.seed,
        repeats=request.repeats,
    )


@router.get("/pipelines", response_model=list[LearningPipelineRun])
def list_learning_pipelines(
    limit: int = Query(default=20, ge=1, le=100),
) -> list[LearningPipelineRun]:
    store = get_object_store()
    try:
        keys = [
            key
            for key in store.list_keys("manifests/inventory-risk/")
            if key.endswith(".json") and not key.endswith("/latest.json")
        ]
    except ObjectStorageError:
        return []
    runs: list[LearningPipelineRun] = []
    for key in reversed(keys[-limit:]):
        try:
            decoded = json.loads(store.get(key))
        except (ObjectStorageError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(decoded, dict):
            continue
        manifest = cast(dict[str, object], decoded)
        curated = manifest.get("curated_keys")
        summaries = manifest.get("summary_keys")
        runs.append(
            LearningPipelineRun(
                manifest_key=key,
                status=str(manifest.get("status", "unknown")),
                partition_date=_optional_string(manifest.get("partition_date")),
                run_id=_optional_string(manifest.get("run_id")),
                created_at=_optional_string(manifest.get("created_at")),
                input_rows=_optional_int(manifest.get("input_rows")),
                curated_object_count=len(curated) if isinstance(curated, list) else 0,
                summary_object_count=(
                    len(summaries) if isinstance(summaries, list) else 0
                ),
                spark_version=_optional_string(manifest.get("spark_version")),
                manifest=manifest,
            )
        )
    return runs


def _count(session: Session, model: type[Base]) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


def _component_statuses() -> list[LearningComponentStatus]:
    object_status = "available" if object_store_is_available() else "unavailable"
    redis_status = "available" if redis_is_available() else "unavailable"
    return [
        LearningComponentStatus(
            id="fastapi",
            name="FastAPI",
            role=(
                "Opens the front door and checks that each message has "
                "what the hub needs."
            ),
            status="available",
            evidence="This overview request reached the application.",
        ),
        LearningComponentStatus(
            id="postgresql",
            name="PostgreSQL",
            role="Keeps the official record of work, inventory, and what happened.",
            status="available",
            evidence="The overview query completed successfully.",
        ),
        LearningComponentStatus(
            id="seaweedfs",
            name="SeaweedFS",
            role="Keeps untouched copies of supplier messages and daily files.",
            status=object_status,
            evidence=f"Live bucket probe: {object_status}.",
        ),
        LearningComponentStatus(
            id="redis",
            name="Redis",
            role="Passes a small work-ticket number to an available worker.",
            status=redis_status,
            evidence=f"Live ping: {redis_status}.",
        ),
        LearningComponentStatus(
            id="celery",
            name="Celery",
            role="Lets background workers pick up tickets and finish them safely.",
            status="configured",
            evidence="Worker execution is visible through import attempt events.",
        ),
        LearningComponentStatus(
            id="analytics",
            name="Pandas · Polars · NumPy",
            role="Checks inventory agreement and estimates where stock may run out.",
            status="configured",
            evidence="Completed experiments are stored as analytics runs.",
        ),
        LearningComponentStatus(
            id="airflow",
            name="Airflow · Spark",
            role="Turns groups of daily files into checked, analysis-ready data.",
            status="configured",
            evidence="Successful runs publish immutable manifests to object storage.",
        ),
        LearningComponentStatus(
            id="prometheus",
            name="Prometheus",
            role="Keeps simple measurements that show whether the hub is healthy.",
            status="configured",
            evidence="The application exposes a local /metrics endpoint.",
        ),
    ]


def _import_summary(job: models.ImportJob) -> LearningImportSummary:
    return LearningImportSummary(
        id=job.id,
        supplier_code=job.supplier.code,
        source_type=job.source_type,
        status=job.status,
        accepted_records=job.accepted_records,
        rejected_records=job.rejected_records,
        attempt_count=job.attempt_count,
        correlation_id=job.correlation_id,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


def _snapshot_view(snapshot: models.InventorySnapshot) -> LearningSnapshot:
    conversion = snapshot.units_per_source_unit
    return LearningSnapshot(
        id=snapshot.id,
        source_reference=snapshot.source_reference,
        source_row=snapshot.source_row,
        external_sku=snapshot.external_sku,
        canonical_sku=snapshot.product.sku,
        external_location=snapshot.external_location,
        warehouse_code=snapshot.warehouse.code,
        source_unit=snapshot.source_unit,
        units_per_source_unit=conversion,
        source_on_hand=snapshot.on_hand_quantity / conversion,
        canonical_on_hand=snapshot.on_hand_quantity,
        source_reserved=snapshot.reserved_quantity / conversion,
        canonical_reserved=snapshot.reserved_quantity,
        product_mapping_version=snapshot.product_mapping_version,
        warehouse_mapping_version=snapshot.warehouse_mapping_version,
        observed_at=snapshot.observed_at,
    )


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None
