from enum import StrEnum


class RecordStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class UnitOfMeasure(StrEnum):
    EACH = "EACH"
    CASE = "CASE"
    PALLET = "PALLET"
    KILOGRAM = "KILOGRAM"


class PurchaseOrderStatus(StrEnum):
    SUBMITTED = "submitted"
    PARTIALLY_RECEIVED = "partially_received"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class ShipmentStatus(StrEnum):
    PLANNED = "planned"
    PICKED_UP = "picked_up"
    IN_TRANSIT = "in_transit"
    DELAYED = "delayed"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class ShipmentEventType(StrEnum):
    PICKED_UP = "picked_up"
    IN_TRANSIT = "in_transit"
    DELAYED = "delayed"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class ImportStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class ImportAttemptStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    RETRY_SCHEDULED = "retry_scheduled"
    FAILED = "failed"
    ABANDONED = "abandoned"


class ImportSourceType(StrEnum):
    SUPPLIER_A_JSON = "supplier_a_json"
    SUPPLIER_B_CSV = "supplier_b_csv"


class AnalyticsEngine(StrEnum):
    PANDAS = "pandas"
    POLARS = "polars"
    NUMPY = "numpy"


class AnalyticsRunType(StrEnum):
    INVENTORY_RECONCILIATION = "inventory_reconciliation"
    STOCKOUT_RISK = "stockout_risk"


class RiskSeverity(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
