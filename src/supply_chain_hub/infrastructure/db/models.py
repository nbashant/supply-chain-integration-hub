from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
from supply_chain_hub.infrastructure.db.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_class]


class Supplier(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "suppliers"

    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[RecordStatus] = mapped_column(
        Enum(
            RecordStatus,
            native_enum=False,
            create_constraint=True,
            length=20,
            values_callable=enum_values,
        ),
        nullable=False,
        default=RecordStatus.ACTIVE,
        server_default=RecordStatus.ACTIVE.value,
    )

    purchase_orders: Mapped[list[PurchaseOrder]] = relationship(
        back_populates="supplier",
    )
    shipments: Mapped[list[Shipment]] = relationship(back_populates="supplier")
    product_mappings: Mapped[list[SupplierProductMapping]] = relationship(
        back_populates="supplier",
    )
    warehouse_mappings: Mapped[list[SupplierWarehouseMapping]] = relationship(
        back_populates="supplier",
    )
    import_jobs: Mapped[list[ImportJob]] = relationship(back_populates="supplier")
    inventory_snapshots: Mapped[list[InventorySnapshot]] = relationship(
        back_populates="supplier",
    )


class Product(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "products"

    sku: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    base_unit: Mapped[UnitOfMeasure] = mapped_column(
        Enum(
            UnitOfMeasure,
            native_enum=False,
            create_constraint=True,
            length=20,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    status: Mapped[RecordStatus] = mapped_column(
        Enum(
            RecordStatus,
            native_enum=False,
            create_constraint=True,
            length=20,
            values_callable=enum_values,
        ),
        nullable=False,
        default=RecordStatus.ACTIVE,
        server_default=RecordStatus.ACTIVE.value,
    )

    inventory_positions: Mapped[list[InventoryPosition]] = relationship(
        back_populates="product",
    )
    purchase_order_lines: Mapped[list[PurchaseOrderLine]] = relationship(
        back_populates="product",
    )
    supplier_mappings: Mapped[list[SupplierProductMapping]] = relationship(
        back_populates="product",
    )
    inventory_snapshots: Mapped[list[InventorySnapshot]] = relationship(
        back_populates="product",
    )


class Warehouse(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "warehouses"

    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    timezone: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[RecordStatus] = mapped_column(
        Enum(
            RecordStatus,
            native_enum=False,
            create_constraint=True,
            length=20,
            values_callable=enum_values,
        ),
        nullable=False,
        default=RecordStatus.ACTIVE,
        server_default=RecordStatus.ACTIVE.value,
    )

    inventory_positions: Mapped[list[InventoryPosition]] = relationship(
        back_populates="warehouse",
    )
    supplier_mappings: Mapped[list[SupplierWarehouseMapping]] = relationship(
        back_populates="warehouse",
    )
    inventory_snapshots: Mapped[list[InventorySnapshot]] = relationship(
        back_populates="warehouse",
    )


class InventoryPosition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "inventory_positions"
    __table_args__ = (
        UniqueConstraint(
            "warehouse_id",
            "product_id",
            name="uq_inventory_positions_warehouse_product",
        ),
        CheckConstraint(
            "on_hand_quantity >= 0",
            name="on_hand_quantity_nonnegative",
        ),
        CheckConstraint(
            "reserved_quantity >= 0",
            name="reserved_quantity_nonnegative",
        ),
        CheckConstraint("version > 0", name="version_positive"),
        Index("ix_inventory_positions_product_warehouse", "product_id", "warehouse_id"),
    )

    warehouse_id: Mapped[UUID] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    on_hand_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
        default=Decimal("0"),
    )
    reserved_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
        default=Decimal("0"),
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )

    warehouse: Mapped[Warehouse] = relationship(
        back_populates="inventory_positions",
    )
    product: Mapped[Product] = relationship(
        back_populates="inventory_positions",
    )


class PurchaseOrder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        UniqueConstraint(
            "supplier_id",
            "external_reference",
            name="uq_purchase_orders_supplier_external_reference",
        ),
        Index("ix_purchase_orders_supplier_status", "supplier_id", "status"),
    )

    supplier_id: Mapped[UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    external_reference: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[PurchaseOrderStatus] = mapped_column(
        Enum(
            PurchaseOrderStatus,
            native_enum=False,
            create_constraint=True,
            length=30,
            values_callable=enum_values,
        ),
        nullable=False,
        default=PurchaseOrderStatus.SUBMITTED,
        server_default=PurchaseOrderStatus.SUBMITTED.value,
    )
    order_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        server_default=func.current_date(),
    )
    expected_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    supplier: Mapped[Supplier] = relationship(back_populates="purchase_orders")
    lines: Mapped[list[PurchaseOrderLine]] = relationship(
        back_populates="purchase_order",
        cascade="all, delete-orphan",
        order_by="PurchaseOrderLine.line_number",
    )
    shipments: Mapped[list[Shipment]] = relationship(
        back_populates="purchase_order",
    )


class PurchaseOrderLine(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "purchase_order_lines"
    __table_args__ = (
        UniqueConstraint(
            "purchase_order_id",
            "line_number",
            name="uq_purchase_order_lines_order_line_number",
        ),
        UniqueConstraint(
            "purchase_order_id",
            "product_id",
            name="uq_purchase_order_lines_order_product",
        ),
        CheckConstraint(
            "ordered_quantity > 0",
            name="ordered_quantity_positive",
        ),
        CheckConstraint(
            "received_quantity >= 0",
            name="received_quantity_nonnegative",
        ),
    )

    purchase_order_id: Mapped[UUID] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    ordered_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
    )
    received_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )

    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="lines")
    product: Mapped[Product] = relationship(back_populates="purchase_order_lines")


class Shipment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "shipments"
    __table_args__ = (
        UniqueConstraint(
            "supplier_id",
            "tracking_reference",
            name="uq_shipments_supplier_tracking_reference",
        ),
        Index("ix_shipments_purchase_order_status", "purchase_order_id", "status"),
    )

    supplier_id: Mapped[UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    purchase_order_id: Mapped[UUID] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="RESTRICT"),
        nullable=False,
    )
    tracking_reference: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[ShipmentStatus] = mapped_column(
        Enum(
            ShipmentStatus,
            native_enum=False,
            create_constraint=True,
            length=30,
            values_callable=enum_values,
        ),
        nullable=False,
        default=ShipmentStatus.PLANNED,
        server_default=ShipmentStatus.PLANNED.value,
    )
    shipped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    supplier: Mapped[Supplier] = relationship(back_populates="shipments")
    purchase_order: Mapped[PurchaseOrder] = relationship(
        back_populates="shipments",
    )
    events: Mapped[list[ShipmentEvent]] = relationship(
        back_populates="shipment",
        cascade="all, delete-orphan",
        order_by="ShipmentEvent.occurred_at",
    )


class ShipmentEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "shipment_events"
    __table_args__ = (
        UniqueConstraint(
            "shipment_id",
            "external_event_id",
            name="uq_shipment_events_shipment_external_event",
        ),
        Index("ix_shipment_events_shipment_occurred", "shipment_id", "occurred_at"),
    )

    shipment_id: Mapped[UUID] = mapped_column(
        ForeignKey("shipments.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_event_id: Mapped[str] = mapped_column(String(100), nullable=False)
    event_type: Mapped[ShipmentEventType] = mapped_column(
        Enum(
            ShipmentEventType,
            native_enum=False,
            create_constraint=True,
            length=30,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    reason_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    shipment: Mapped[Shipment] = relationship(back_populates="events")


class SupplierProductMapping(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "supplier_product_mappings"
    __table_args__ = (
        UniqueConstraint(
            "supplier_id",
            "external_sku",
            name="uq_supplier_product_mappings_supplier_external_sku",
        ),
        CheckConstraint(
            "units_per_source_unit > 0",
            name="units_per_source_unit_positive",
        ),
        CheckConstraint("version > 0", name="version_positive"),
        Index(
            "ix_supplier_product_mappings_supplier_active",
            "supplier_id",
            "active",
        ),
    )

    supplier_id: Mapped[UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_sku: Mapped[str] = mapped_column(String(100), nullable=False)
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_unit: Mapped[UnitOfMeasure] = mapped_column(
        Enum(
            UnitOfMeasure,
            native_enum=False,
            create_constraint=True,
            length=20,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    units_per_source_unit: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
        default=Decimal("1"),
        server_default="1",
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    supplier: Mapped[Supplier] = relationship(back_populates="product_mappings")
    product: Mapped[Product] = relationship(back_populates="supplier_mappings")


class SupplierWarehouseMapping(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "supplier_warehouse_mappings"
    __table_args__ = (
        UniqueConstraint(
            "supplier_id",
            "external_location",
            name="uq_supplier_warehouse_mappings_supplier_external_location",
        ),
        CheckConstraint("version > 0", name="version_positive"),
        Index(
            "ix_supplier_warehouse_mappings_supplier_active",
            "supplier_id",
            "active",
        ),
    )

    supplier_id: Mapped[UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_location: Mapped[str] = mapped_column(String(100), nullable=False)
    warehouse_id: Mapped[UUID] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    supplier: Mapped[Supplier] = relationship(back_populates="warehouse_mappings")
    warehouse: Mapped[Warehouse] = relationship(back_populates="supplier_mappings")


class ImportJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "import_jobs"
    __table_args__ = (
        UniqueConstraint(
            "supplier_id",
            "source_type",
            "idempotency_key",
            name="uq_import_jobs_supplier_source_idempotency",
        ),
        CheckConstraint("attempt_count >= 0", name="attempt_count_nonnegative"),
        CheckConstraint("max_attempts > 0", name="max_attempts_positive"),
        CheckConstraint(
            "payload_size_bytes IS NULL OR payload_size_bytes >= 0",
            name="payload_size_nonnegative",
        ),
        Index("ix_import_jobs_supplier_created", "supplier_id", "created_at"),
        Index("ix_import_jobs_status_retry", "status", "next_retry_at"),
        Index("ix_import_jobs_status_lease", "status", "lease_expires_at"),
        Index("ix_import_jobs_payload_object_key", "payload_object_key"),
        Index("ix_import_jobs_correlation_id", "correlation_id"),
    )

    supplier_id: Mapped[UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_type: Mapped[ImportSourceType] = mapped_column(
        Enum(
            ImportSourceType,
            native_enum=False,
            create_constraint=True,
            length=40,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    adapter_version: Mapped[str] = mapped_column(String(100), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="application/octet-stream",
        server_default="application/octet-stream",
    )
    payload: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    payload_object_key: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )
    payload_size_bytes: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[ImportStatus] = mapped_column(
        Enum(
            ImportStatus,
            native_enum=False,
            create_constraint=True,
            length=40,
            values_callable=enum_values,
        ),
        nullable=False,
        default=ImportStatus.QUEUED,
        server_default=ImportStatus.QUEUED.value,
    )
    total_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accepted_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        server_default="3",
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    worker_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    last_error_retryable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    replay_of_job_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("import_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )

    supplier: Mapped[Supplier] = relationship(back_populates="import_jobs")
    errors: Mapped[list[ImportJobError]] = relationship(
        back_populates="import_job",
        cascade="all, delete-orphan",
        order_by="ImportJobError.source_row",
    )
    snapshots: Mapped[list[InventorySnapshot]] = relationship(
        back_populates="import_job",
        cascade="all, delete-orphan",
    )
    attempts: Mapped[list[ImportAttempt]] = relationship(
        back_populates="import_job",
        cascade="all, delete-orphan",
        order_by="ImportAttempt.attempt_number",
    )
    operation_events: Mapped[list[OperationEvent]] = relationship(
        back_populates="import_job",
        cascade="all, delete-orphan",
        order_by="OperationEvent.occurred_at",
    )
    replay_of: Mapped[ImportJob | None] = relationship(
        remote_side="ImportJob.id",
        back_populates="replays",
    )
    replays: Mapped[list[ImportJob]] = relationship(back_populates="replay_of")


class ImportAttempt(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "import_attempts"
    __table_args__ = (
        UniqueConstraint(
            "import_job_id",
            "attempt_number",
            name="uq_import_attempts_job_attempt_number",
        ),
        CheckConstraint("attempt_number > 0", name="attempt_number_positive"),
        Index("ix_import_attempts_job_started", "import_job_id", "started_at"),
    )

    import_job_id: Mapped[UUID] = mapped_column(
        ForeignKey("import_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ImportAttemptStatus] = mapped_column(
        Enum(
            ImportAttemptStatus,
            native_enum=False,
            create_constraint=True,
            length=40,
            values_callable=enum_values,
        ),
        nullable=False,
        default=ImportAttemptStatus.RUNNING,
        server_default=ImportAttemptStatus.RUNNING.value,
    )
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    worker_id: Mapped[str] = mapped_column(String(255), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    retryable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    import_job: Mapped[ImportJob] = relationship(back_populates="attempts")


class OperationEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "operation_events"
    __table_args__ = (
        Index(
            "ix_operation_events_job_occurred",
            "import_job_id",
            "occurred_at",
        ),
        Index(
            "ix_operation_events_component_occurred",
            "component",
            "occurred_at",
        ),
    )

    import_job_id: Mapped[UUID] = mapped_column(
        ForeignKey("import_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    component: Mapped[str] = mapped_column(String(50), nullable=False)
    stage: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    explanation: Mapped[str] = mapped_column(String(1000), nullable=False)
    evidence_reference: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )
    details: Mapped[dict[str, object]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    import_job: Mapped[ImportJob] = relationship(
        back_populates="operation_events",
    )


class ImportJobError(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "import_errors"
    __table_args__ = (Index("ix_import_errors_job_row", "import_job_id", "source_row"),)

    import_job_id: Mapped[UUID] = mapped_column(
        ForeignKey("import_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_row: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str] = mapped_column(String(100), nullable=False)
    field_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    raw_fragment: Mapped[dict[str, object] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    import_job: Mapped[ImportJob] = relationship(back_populates="errors")


class InventorySnapshot(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "inventory_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "supplier_id",
            "source_reference",
            "external_sku",
            "external_location",
            name="uq_inventory_snapshots_source_record",
        ),
        CheckConstraint(
            "on_hand_quantity >= 0",
            name="on_hand_quantity_nonnegative",
        ),
        CheckConstraint(
            "reserved_quantity >= 0",
            name="reserved_quantity_nonnegative",
        ),
        CheckConstraint(
            "units_per_source_unit > 0",
            name="units_per_source_unit_positive",
        ),
        Index(
            "ix_inventory_snapshots_product_warehouse_observed",
            "product_id",
            "warehouse_id",
            "observed_at",
        ),
    )

    import_job_id: Mapped[UUID] = mapped_column(
        ForeignKey("import_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    supplier_id: Mapped[UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    warehouse_id: Mapped[UUID] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_reference: Mapped[str] = mapped_column(String(100), nullable=False)
    external_sku: Mapped[str] = mapped_column(String(100), nullable=False)
    external_location: Mapped[str] = mapped_column(String(100), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    on_hand_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    reserved_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    source_unit: Mapped[UnitOfMeasure] = mapped_column(
        Enum(
            UnitOfMeasure,
            native_enum=False,
            create_constraint=True,
            length=20,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    units_per_source_unit: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
    )
    product_mapping_version: Mapped[int] = mapped_column(Integer, nullable=False)
    warehouse_mapping_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_fragment: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    import_job: Mapped[ImportJob] = relationship(back_populates="snapshots")
    supplier: Mapped[Supplier] = relationship(back_populates="inventory_snapshots")
    product: Mapped[Product] = relationship(back_populates="inventory_snapshots")
    warehouse: Mapped[Warehouse] = relationship(back_populates="inventory_snapshots")


class AnalyticsRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "analytics_runs"
    __table_args__ = (
        CheckConstraint("input_rows > 0", name="input_rows_positive"),
        CheckConstraint("duration_ms >= 0", name="duration_ms_nonnegative"),
        Index("ix_analytics_runs_type_created", "run_type", "created_at"),
    )

    run_type: Mapped[AnalyticsRunType] = mapped_column(
        Enum(
            AnalyticsRunType,
            native_enum=False,
            create_constraint=True,
            length=40,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    engine: Mapped[AnalyticsEngine] = mapped_column(
        Enum(
            AnalyticsEngine,
            native_enum=False,
            create_constraint=True,
            length=20,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    dataset_seed: Mapped[int] = mapped_column(BigInteger, nullable=False)
    input_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    summary: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    reconciliations: Mapped[list[InventoryReconciliation]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )
    stockout_risks: Mapped[list[StockoutRisk]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )


class InventoryReconciliation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "inventory_reconciliations"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "record_index",
            name="uq_inventory_reconciliations_run_record",
        ),
        Index(
            "ix_inventory_reconciliations_run_matches",
            "run_id",
            "matches",
        ),
    )

    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("analytics_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    record_index: Mapped[int] = mapped_column(Integer, nullable=False)
    supplier_code: Mapped[str] = mapped_column(String(100), nullable=False)
    product_sku: Mapped[str] = mapped_column(String(100), nullable=False)
    warehouse_code: Mapped[str] = mapped_column(String(100), nullable=False)
    reported_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
    )
    hub_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    difference_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
    )
    matches: Mapped[bool] = mapped_column(Boolean, nullable=False)

    run: Mapped[AnalyticsRun] = relationship(back_populates="reconciliations")


class StockoutRisk(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stockout_risks"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "record_index",
            name="uq_stockout_risks_run_record",
        ),
        CheckConstraint(
            "projected_shortage_quantity >= 0",
            name="projected_shortage_nonnegative",
        ),
        CheckConstraint("shortage_ratio >= 0", name="shortage_ratio_nonnegative"),
        Index("ix_stockout_risks_run_severity", "run_id", "severity"),
    )

    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("analytics_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    record_index: Mapped[int] = mapped_column(Integer, nullable=False)
    product_sku: Mapped[str] = mapped_column(String(100), nullable=False)
    warehouse_code: Mapped[str] = mapped_column(String(100), nullable=False)
    on_hand_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    reserved_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
    )
    inbound_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    forecast_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
    )
    actual_demand_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
    )
    available_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
    )
    projected_ending_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
    )
    projected_shortage_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
    )
    shortage_ratio: Mapped[Decimal] = mapped_column(
        Numeric(18, 6),
        nullable=False,
    )
    severity: Mapped[RiskSeverity] = mapped_column(
        Enum(
            RiskSeverity,
            native_enum=False,
            create_constraint=True,
            length=20,
            values_callable=enum_values,
        ),
        nullable=False,
    )

    run: Mapped[AnalyticsRun] = relationship(back_populates="stockout_risks")
