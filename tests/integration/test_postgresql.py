from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import Engine, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from supply_chain_hub.api.schemas import ProductMappingUpsert, WarehouseMappingUpsert
from supply_chain_hub.application import analytics_services, integration_services
from supply_chain_hub.domain.enums import (
    AnalyticsEngine,
    AnalyticsRunType,
    ImportSourceType,
    RiskSeverity,
    UnitOfMeasure,
)
from supply_chain_hub.infrastructure.db import models
from supply_chain_hub.integrations.base import (
    CanonicalInventoryRecord,
    InventoryAdapterResult,
)

EXPECTED_TABLES = [
    "analytics_runs",
    "import_attempts",
    "import_errors",
    "import_jobs",
    "inventory_positions",
    "inventory_reconciliations",
    "inventory_snapshots",
    "operation_events",
    "products",
    "purchase_order_lines",
    "purchase_orders",
    "shipment_events",
    "shipments",
    "stockout_risks",
    "suppliers",
    "supplier_product_mappings",
    "supplier_warehouse_mappings",
    "warehouses",
]


@pytest.mark.integration
def test_migration_creates_the_expected_tables(postgres_engine: Engine) -> None:
    actual_tables = set(inspect(postgres_engine).get_table_names())

    assert set(EXPECTED_TABLES).issubset(actual_tables)
    assert "alembic_version" in actual_tables


@pytest.mark.integration
def test_postgresql_enforces_inventory_constraints(
    postgres_session: Session,
) -> None:
    product = models.Product(
        sku="DB-CONSTRAINT-TEST",
        name="Database Constraint Test",
        base_unit=UnitOfMeasure.EACH,
    )
    warehouse = models.Warehouse(
        code="DB-01",
        name="Database Test Warehouse",
        timezone="UTC",
    )
    postgres_session.add_all([product, warehouse])
    postgres_session.flush()

    invalid_position = models.InventoryPosition(
        product_id=product.id,
        warehouse_id=warehouse.id,
        on_hand_quantity=Decimal("-1"),
        reserved_quantity=Decimal("0"),
    )
    postgres_session.add(invalid_position)

    with pytest.raises(IntegrityError):
        postgres_session.commit()


@pytest.mark.integration
def test_postgresql_enforces_supplier_code_uniqueness(
    postgres_session: Session,
) -> None:
    postgres_session.add(models.Supplier(code="UNIQUE", name="First"))
    postgres_session.commit()
    postgres_session.add(models.Supplier(code="UNIQUE", name="Second"))

    with pytest.raises(IntegrityError):
        postgres_session.commit()


@pytest.mark.integration
def test_postgresql_rejects_negative_import_payload_size(
    postgres_session: Session,
) -> None:
    supplier = models.Supplier(code="PAYLOAD-SIZE", name="Payload Size")
    postgres_session.add(supplier)
    postgres_session.flush()
    postgres_session.add(
        models.ImportJob(
            supplier_id=supplier.id,
            source_type=ImportSourceType.SUPPLIER_A_JSON,
            adapter_version="constraint.v1",
            content_sha256="c" * 64,
            payload_object_key="raw/constraint.json",
            payload_size_bytes=-1,
        )
    )

    with pytest.raises(IntegrityError):
        postgres_session.commit()


@pytest.mark.integration
def test_postgresql_round_trip_preserves_decimal_scale(
    postgres_session: Session,
) -> None:
    product = models.Product(
        sku="DECIMAL-TEST",
        name="Decimal Test",
        base_unit=UnitOfMeasure.EACH,
    )
    warehouse = models.Warehouse(
        code="DEC-01",
        name="Decimal Warehouse",
        timezone="UTC",
    )
    postgres_session.add_all([product, warehouse])
    postgres_session.flush()
    position = models.InventoryPosition(
        product_id=product.id,
        warehouse_id=warehouse.id,
        on_hand_quantity=Decimal("10.125"),
        reserved_quantity=Decimal("2.125"),
    )
    postgres_session.add(position)
    postgres_session.commit()

    stored_position = postgres_session.scalar(
        select(models.InventoryPosition).where(
            models.InventoryPosition.id == position.id
        )
    )

    assert stored_position is not None
    assert stored_position.on_hand_quantity == Decimal("10.125")
    assert stored_position.reserved_quantity == Decimal("2.125")


@pytest.mark.integration
def test_postgresql_enforces_nonnegative_stockout_shortage(
    postgres_session: Session,
) -> None:
    run = models.AnalyticsRun(
        run_type=AnalyticsRunType.STOCKOUT_RISK,
        engine=AnalyticsEngine.NUMPY,
        dataset_seed=1,
        input_rows=1,
        duration_ms=Decimal("1.000"),
        summary={},
    )
    run.stockout_risks.append(
        models.StockoutRisk(
            record_index=0,
            product_sku="RISK-CONSTRAINT",
            warehouse_code="DB-01",
            on_hand_quantity=Decimal("1"),
            reserved_quantity=Decimal("0"),
            inbound_quantity=Decimal("0"),
            forecast_quantity=Decimal("2"),
            actual_demand_quantity=Decimal("2"),
            available_quantity=Decimal("1"),
            projected_ending_quantity=Decimal("-1"),
            projected_shortage_quantity=Decimal("-1"),
            shortage_ratio=Decimal("0.5"),
            severity=RiskSeverity.HIGH,
        )
    )
    postgres_session.add(run)

    with pytest.raises(IntegrityError):
        postgres_session.commit()


@pytest.mark.integration
def test_postgresql_persists_the_maximum_supported_dataset_seed(
    postgres_session: Session,
) -> None:
    run = analytics_services.run_reconciliation(
        postgres_session,
        engine=AnalyticsEngine.PANDAS,
        row_count=1,
        seed=4_294_967_295,
    )

    assert run.dataset_seed == 4_294_967_295
    assert len(run.reconciliations) == 1


@pytest.mark.integration
def test_operational_queries_have_index_backed_plans(
    postgres_session: Session,
) -> None:
    postgres_session.execute(text("SET LOCAL enable_seqscan = off"))
    expected_indexes = {
        ("ix_import_jobs_status_retry",): """
            SELECT id FROM import_jobs
            WHERE status = 'queued' AND next_retry_at <= now()
            ORDER BY next_retry_at
            LIMIT 100
        """,
        ("ix_import_jobs_status_lease",): """
            SELECT id FROM import_jobs
            WHERE status = 'processing' AND lease_expires_at <= now()
            ORDER BY lease_expires_at
            LIMIT 100
        """,
        (
            "ix_inventory_reconciliations_run_matches",
            "uq_inventory_reconciliations_run_record",
        ): """
            SELECT id FROM inventory_reconciliations
            WHERE run_id = '00000000-0000-0000-0000-000000000001'
              AND matches = false
        """,
        (
            "ix_stockout_risks_run_severity",
            "uq_stockout_risks_run_record",
        ): """
            SELECT id FROM stockout_risks
            WHERE run_id = '00000000-0000-0000-0000-000000000001'
              AND severity = 'high'
        """,
    }

    for index_names, query in expected_indexes.items():
        plan = "\n".join(
            str(row)
            for row in postgres_session.execute(text(f"EXPLAIN {query}")).scalars()
        )
        assert "Index Scan" in plan
        assert any(index_name in plan for index_name in index_names)


@pytest.mark.integration
def test_import_snapshot_preserves_mapping_versions(
    postgres_session: Session,
) -> None:
    supplier = models.Supplier(code="SUPPLIER_A", name="Supplier A")
    product = models.Product(
        sku="VERSION-PROOF",
        name="Version Proof",
        base_unit=UnitOfMeasure.EACH,
    )
    warehouse = models.Warehouse(
        code="VERSION-WH",
        name="Version Warehouse",
        timezone="UTC",
    )
    postgres_session.add_all([supplier, product, warehouse])
    postgres_session.commit()
    product_mapping_request = ProductMappingUpsert(
        supplier_id=supplier.id,
        external_sku="PARTNER-VERSION-PROOF",
        product_id=product.id,
        source_unit=UnitOfMeasure.CASE,
        units_per_source_unit=Decimal("6"),
    )
    integration_services.upsert_product_mapping(
        postgres_session,
        product_mapping_request,
    )
    integration_services.upsert_warehouse_mapping(
        postgres_session,
        WarehouseMappingUpsert(
            supplier_id=supplier.id,
            external_location="PARTNER-WH",
            warehouse_id=warehouse.id,
        ),
    )
    integration_services.process_inventory_import(
        postgres_session,
        supplier_code="SUPPLIER_A",
        source_type=ImportSourceType.SUPPLIER_A_JSON,
        adapter_version="test.v1",
        content_sha256="a" * 64,
        result=_inventory_result("SNAPSHOT-V1"),
    )
    product_mapping_request.units_per_source_unit = Decimal("12")
    integration_services.upsert_product_mapping(
        postgres_session,
        product_mapping_request,
    )
    integration_services.process_inventory_import(
        postgres_session,
        supplier_code="SUPPLIER_A",
        source_type=ImportSourceType.SUPPLIER_A_JSON,
        adapter_version="test.v1",
        content_sha256="b" * 64,
        result=_inventory_result("SNAPSHOT-V2"),
    )

    snapshots = postgres_session.scalars(
        select(models.InventorySnapshot).order_by(
            models.InventorySnapshot.source_reference
        )
    ).all()

    assert [snapshot.product_mapping_version for snapshot in snapshots] == [1, 2]
    assert [snapshot.units_per_source_unit for snapshot in snapshots] == [
        Decimal("6.000"),
        Decimal("12.000"),
    ]
    assert [snapshot.on_hand_quantity for snapshot in snapshots] == [
        Decimal("12.000"),
        Decimal("24.000"),
    ]


def _inventory_result(source_reference: str) -> InventoryAdapterResult:
    return InventoryAdapterResult(
        records=[
            CanonicalInventoryRecord(
                source_reference=source_reference,
                source_row=1,
                external_sku="PARTNER-VERSION-PROOF",
                external_location="PARTNER-WH",
                observed_at=datetime(2026, 7, 29, tzinfo=UTC),
                source_unit=UnitOfMeasure.CASE,
                on_hand_quantity=Decimal("2"),
                reserved_quantity=Decimal("0"),
                units_per_source_unit=None,
                raw_fragment={"source_reference": source_reference},
            )
        ]
    )
