from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    StringConstraints,
    field_validator,
)

from supply_chain_hub.domain.enums import (
    AnalyticsEngine,
    AnalyticsRunType,
    ImportAttemptStatus,
    ImportSourceType,
    ImportStatus,
    PurchaseOrderStatus,
    RecordStatus,
    RiskSeverity,
    ShipmentEventType,
    ShipmentStatus,
    UnitOfMeasure,
)

Code = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_upper=True,
        min_length=2,
        max_length=100,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$",
    ),
]
Name = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
ExternalReference = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]
Quantity = Annotated[
    Decimal,
    Field(ge=0, max_digits=18, decimal_places=3),
]
PositiveQuantity = Annotated[
    Decimal,
    Field(gt=0, max_digits=18, decimal_places=3),
]


def serialize_utc_datetime(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


UTCDateTime = Annotated[
    datetime,
    PlainSerializer(serialize_utc_datetime, return_type=str, when_used="json"),
]


class ORMResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SupplierCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": "SUPPLIER_A",
                "name": "Supplier A",
            }
        }
    )

    code: Code
    name: Name


class SupplierResponse(ORMResponse):
    id: UUID
    code: str
    name: str
    status: RecordStatus
    created_at: UTCDateTime
    updated_at: UTCDateTime


class ProductCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sku": "IP16-256-BLK",
                "name": "Example Phone 256 GB - Black",
                "base_unit": "EACH",
            }
        }
    )

    sku: Code
    name: Name
    base_unit: UnitOfMeasure


class ProductResponse(ORMResponse):
    id: UUID
    sku: str
    name: str
    base_unit: UnitOfMeasure
    status: RecordStatus
    created_at: UTCDateTime
    updated_at: UTCDateTime


class WarehouseCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": "LAX-01",
                "name": "Los Angeles Distribution Center",
                "timezone": "America/Los_Angeles",
            }
        }
    )

    code: Code
    name: Name
    timezone: str = Field(min_length=1, max_length=100)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError("Timezone must be a valid IANA timezone.") from error
        return value


class WarehouseResponse(ORMResponse):
    id: UUID
    code: str
    name: str
    timezone: str
    status: RecordStatus
    created_at: UTCDateTime
    updated_at: UTCDateTime


class InventorySet(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "on_hand_quantity": "120.000",
                "reserved_quantity": "35.000",
            }
        }
    )

    on_hand_quantity: Quantity
    reserved_quantity: Quantity = Decimal("0")


class InventoryResponse(ORMResponse):
    id: UUID
    warehouse_id: UUID
    product_id: UUID
    on_hand_quantity: Decimal
    reserved_quantity: Decimal
    available_quantity: Decimal
    version: int
    created_at: UTCDateTime
    updated_at: UTCDateTime


class PurchaseOrderLineCreate(BaseModel):
    product_id: UUID
    ordered_quantity: PositiveQuantity


class PurchaseOrderCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "supplier_id": "2f8ad5f8-0ff8-4dda-b60b-88df438ca17d",
                "external_reference": "PO-2026-0001",
                "expected_date": "2026-08-15",
                "lines": [
                    {
                        "product_id": "4f55f7f4-f01e-44bf-88bb-b5882699274f",
                        "ordered_quantity": "250.000",
                    }
                ],
            }
        }
    )

    supplier_id: UUID
    external_reference: ExternalReference
    expected_date: date | None = None
    lines: list[PurchaseOrderLineCreate] = Field(min_length=1, max_length=100)


class PurchaseOrderLineResponse(ORMResponse):
    id: UUID
    line_number: int
    product_id: UUID
    ordered_quantity: Decimal
    received_quantity: Decimal


class PurchaseOrderResponse(ORMResponse):
    id: UUID
    supplier_id: UUID
    external_reference: str
    status: PurchaseOrderStatus
    order_date: date
    expected_date: date | None
    lines: list[PurchaseOrderLineResponse]
    created_at: UTCDateTime
    updated_at: UTCDateTime


class ShipmentCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "supplier_id": "2f8ad5f8-0ff8-4dda-b60b-88df438ca17d",
                "purchase_order_id": "306cdda5-8234-49c2-8101-dd2a5cb5c399",
                "tracking_reference": "TRACK-0001",
            }
        }
    )

    supplier_id: UUID
    purchase_order_id: UUID
    tracking_reference: ExternalReference
    shipped_at: datetime | None = None


class ShipmentEventCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "external_event_id": "C-EVT-0001",
                "event_type": "picked_up",
                "occurred_at": "2026-07-29T20:00:00Z",
                "reason_code": None,
            }
        }
    )

    external_event_id: ExternalReference
    event_type: ShipmentEventType
    occurred_at: UTCDateTime
    reason_code: str | None = Field(default=None, max_length=100)

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone offset.")
        return value


class ShipmentEventResponse(ORMResponse):
    id: UUID
    external_event_id: str
    event_type: ShipmentEventType
    occurred_at: UTCDateTime
    reason_code: str | None
    received_at: UTCDateTime


class ShipmentResponse(ORMResponse):
    id: UUID
    supplier_id: UUID
    purchase_order_id: UUID
    tracking_reference: str
    status: ShipmentStatus
    shipped_at: UTCDateTime | None
    delivered_at: UTCDateTime | None
    events: list[ShipmentEventResponse]
    created_at: UTCDateTime
    updated_at: UTCDateTime


class ProductMappingUpsert(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "supplier_id": "2f8ad5f8-0ff8-4dda-b60b-88df438ca17d",
                "external_sku": "A-IP16-256-BLK",
                "product_id": "4f55f7f4-f01e-44bf-88bb-b5882699274f",
                "source_unit": "EACH",
                "units_per_source_unit": "1.000",
                "active": True,
            }
        }
    )

    supplier_id: UUID
    external_sku: ExternalReference
    product_id: UUID
    source_unit: UnitOfMeasure
    units_per_source_unit: PositiveQuantity = Decimal("1")
    active: bool = True


class ProductMappingResponse(ORMResponse):
    id: UUID
    supplier_id: UUID
    external_sku: str
    product_id: UUID
    source_unit: UnitOfMeasure
    units_per_source_unit: Decimal
    version: int
    active: bool
    created_at: UTCDateTime
    updated_at: UTCDateTime


class WarehouseMappingUpsert(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "supplier_id": "2f8ad5f8-0ff8-4dda-b60b-88df438ca17d",
                "external_location": "A-WEST-01",
                "warehouse_id": "6c249ee7-2308-484e-a2c1-bc2f20efbb18",
                "active": True,
            }
        }
    )

    supplier_id: UUID
    external_location: ExternalReference
    warehouse_id: UUID
    active: bool = True


class WarehouseMappingResponse(ORMResponse):
    id: UUID
    supplier_id: UUID
    external_location: str
    warehouse_id: UUID
    version: int
    active: bool
    created_at: UTCDateTime
    updated_at: UTCDateTime


class ImportJobResponse(ORMResponse):
    id: UUID
    supplier_id: UUID
    source_type: ImportSourceType
    adapter_version: str
    original_filename: str | None
    content_sha256: str
    payload_object_key: str | None
    payload_size_bytes: int | None
    idempotency_key: str | None
    correlation_id: str | None
    status: ImportStatus
    total_records: int
    accepted_records: int
    rejected_records: int
    attempt_count: int
    max_attempts: int
    dispatched_at: UTCDateTime | None
    started_at: UTCDateTime | None
    completed_at: UTCDateTime | None
    next_retry_at: UTCDateTime | None
    lease_expires_at: UTCDateTime | None
    worker_id: str | None
    failure_code: str | None
    failure_message: str | None
    last_error_retryable: bool | None
    replay_of_job_id: UUID | None
    created_at: UTCDateTime
    updated_at: UTCDateTime


class ImportErrorResponse(ORMResponse):
    id: UUID
    import_job_id: UUID
    source_row: int | None
    error_code: str
    field_name: str | None
    message: str
    raw_fragment: dict[str, object] | None
    created_at: UTCDateTime


class ImportAttemptResponse(ORMResponse):
    id: UUID
    import_job_id: UUID
    attempt_number: int
    status: ImportAttemptStatus
    celery_task_id: str | None
    worker_id: str
    started_at: UTCDateTime
    completed_at: UTCDateTime | None
    error_code: str | None
    error_message: str | None
    retryable: bool | None


class OperationEventResponse(ORMResponse):
    id: UUID
    import_job_id: UUID
    correlation_id: str | None
    component: str
    stage: str
    status: str
    title: str
    explanation: str
    evidence_reference: str | None
    details: dict[str, object]
    occurred_at: UTCDateTime


class LearningImportSummary(BaseModel):
    id: UUID
    supplier_code: str
    source_type: ImportSourceType
    status: ImportStatus
    accepted_records: int
    rejected_records: int
    attempt_count: int
    correlation_id: str | None
    created_at: UTCDateTime
    completed_at: UTCDateTime | None


class LearningSnapshot(BaseModel):
    id: UUID
    source_reference: str
    source_row: int
    external_sku: str
    canonical_sku: str
    external_location: str
    warehouse_code: str
    source_unit: UnitOfMeasure
    units_per_source_unit: Decimal
    source_on_hand: Decimal
    canonical_on_hand: Decimal
    source_reserved: Decimal
    canonical_reserved: Decimal
    product_mapping_version: int
    warehouse_mapping_version: int
    observed_at: UTCDateTime


class LearningImportDetail(BaseModel):
    job: ImportJobResponse
    supplier_code: str
    events: list[OperationEventResponse]
    attempts: list[ImportAttemptResponse]
    errors: list[ImportErrorResponse]
    snapshots: list[LearningSnapshot]


class LearningComponentStatus(BaseModel):
    id: str
    name: str
    role: str
    status: Literal["available", "unavailable", "configured"]
    evidence: str


class LearningOverview(BaseModel):
    components: list[LearningComponentStatus]
    import_status_counts: dict[str, int]
    entity_counts: dict[str, int]
    recent_imports: list[LearningImportSummary]
    recent_events: list[OperationEventResponse]


class LearningDemoResponse(BaseModel):
    job: ImportJobResponse
    created: bool
    demo_input: dict[str, object]


class LearningPipelineRun(BaseModel):
    manifest_key: str
    status: str
    partition_date: str | None
    run_id: str | None
    created_at: str | None
    input_rows: int | None
    curated_object_count: int
    summary_object_count: int
    spark_version: str | None
    manifest: dict[str, object]


class LearningAnalyticsComparisonRequest(BaseModel):
    row_count: int = Field(default=5000, ge=100, le=25_000)
    repeats: int = Field(default=5, ge=3, le=10)
    seed: int = Field(default=20260729, ge=0, le=4_294_967_295)


class ReconciliationRunCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "engine": "pandas",
                "row_count": 1000,
                "seed": 20260729,
            }
        }
    )

    engine: Literal[AnalyticsEngine.PANDAS, AnalyticsEngine.POLARS]
    row_count: int = Field(default=1000, ge=1, le=10_000)
    seed: int = Field(default=20260729, ge=0, le=4_294_967_295)


class StockoutRiskRunCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "row_count": 1000,
                "seed": 20260729,
            }
        }
    )

    row_count: int = Field(default=1000, ge=1, le=10_000)
    seed: int = Field(default=20260729, ge=0, le=4_294_967_295)


class AnalyticsRunResponse(ORMResponse):
    id: UUID
    run_type: AnalyticsRunType
    engine: AnalyticsEngine
    dataset_seed: int
    input_rows: int
    duration_ms: Decimal
    summary: dict[str, object]
    created_at: UTCDateTime
    completed_at: UTCDateTime


class InventoryReconciliationResponse(ORMResponse):
    id: UUID
    run_id: UUID
    record_index: int
    supplier_code: str
    product_sku: str
    warehouse_code: str
    reported_quantity: Decimal
    hub_quantity: Decimal
    difference_quantity: Decimal
    matches: bool


class StockoutRiskResponse(ORMResponse):
    id: UUID
    run_id: UUID
    record_index: int
    product_sku: str
    warehouse_code: str
    on_hand_quantity: Decimal
    reserved_quantity: Decimal
    inbound_quantity: Decimal
    forecast_quantity: Decimal
    actual_demand_quantity: Decimal
    available_quantity: Decimal
    projected_ending_quantity: Decimal
    projected_shortage_quantity: Decimal
    shortage_ratio: Decimal
    severity: RiskSeverity


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: list[dict[str, object]] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
