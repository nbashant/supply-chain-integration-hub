import json
from datetime import UTC, datetime
from pathlib import Path

from supply_chain_hub.domain.enums import ShipmentEventType, UnitOfMeasure
from supply_chain_hub.integrations.carrier_c import CarrierCAdapter, CarrierCEvent
from supply_chain_hub.integrations.supplier_a import (
    SupplierAInventoryAdapter,
    SupplierAInventoryPayload,
)
from supply_chain_hub.integrations.supplier_b import SupplierBInventoryAdapter

FIXTURES = Path(__file__).parents[1] / "fixtures" / "contracts"


def test_supplier_a_contract_normalizes_to_canonical_inventory() -> None:
    payload = SupplierAInventoryPayload.model_validate_json(
        (FIXTURES / "supplier_a_inventory.json").read_text()
    )

    result = SupplierAInventoryAdapter().adapt(payload)

    assert result.errors == []
    assert len(result.records) == 1
    record = result.records[0]
    assert record.external_sku == "A-IP16-256-BLK"
    assert record.source_unit is UnitOfMeasure.EACH
    assert record.observed_at == datetime(2026, 7, 29, 15, tzinfo=UTC)


def test_supplier_b_contract_normalizes_cases_and_timezone() -> None:
    content = (FIXTURES / "supplier_b_inventory.csv").read_bytes()

    result = SupplierBInventoryAdapter().adapt(content)

    assert result.errors == []
    assert len(result.records) == 1
    record = result.records[0]
    assert record.source_row == 2
    assert record.source_unit is UnitOfMeasure.CASE
    assert str(record.on_hand_quantity) == "10.000"
    assert str(record.units_per_source_unit) == "12.000"
    assert record.observed_at == datetime(2026, 7, 29, 15, tzinfo=UTC)


def test_supplier_b_reports_structured_row_errors() -> None:
    content = (
        b"snapshot_ref,as_of,partner_sku,depot,case_count,units_per_case\n"
        b"SB-BAD,not-a-time,B-SKU,B-WH,-2,0\n"
    )

    result = SupplierBInventoryAdapter().adapt(content)

    assert result.records == []
    assert {error.field_name for error in result.errors} == {
        "as_of",
        "case_count",
        "units_per_case",
    }
    assert all(error.code == "invalid_csv_field" for error in result.errors)
    assert all(error.source_row == 2 for error in result.errors)


def test_carrier_c_contract_normalizes_event_and_timezone() -> None:
    payload = CarrierCEvent.model_validate(
        json.loads((FIXTURES / "carrier_c_event.json").read_text())
    )

    event = CarrierCAdapter().adapt(payload)

    assert event.event_type is ShipmentEventType.PICKED_UP
    assert event.tracking_reference == "C-123456"
    assert event.occurred_at == datetime(2026, 7, 29, 20, tzinfo=UTC)
