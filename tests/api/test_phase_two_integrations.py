import json
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from supply_chain_hub.api.routes import integrations as integrations_route
from supply_chain_hub.application import integration_services

FIXTURES = Path(__file__).parents[1] / "fixtures" / "contracts"


def _create_supplier(
    client: TestClient,
    *,
    code: str,
    name: str,
) -> str:
    response = client.post("/api/v1/suppliers", json={"code": code, "name": name})
    assert response.status_code == 201
    return cast(str, response.json()["id"])


def _create_product_and_warehouse(client: TestClient) -> tuple[str, str]:
    product = client.post(
        "/api/v1/products",
        json={
            "sku": "P2-IP16-256-BLK",
            "name": "Phase 2 Example Phone",
            "base_unit": "EACH",
        },
    )
    warehouse = client.post(
        "/api/v1/warehouses",
        json={
            "code": "P2-LAX-01",
            "name": "Phase 2 Los Angeles DC",
            "timezone": "America/Los_Angeles",
        },
    )
    assert product.status_code == 201
    assert warehouse.status_code == 201
    return product.json()["id"], warehouse.json()["id"]


def _map_partner_keys(
    client: TestClient,
    *,
    supplier_id: str,
    product_id: str,
    warehouse_id: str,
    external_sku: str,
    external_location: str,
    source_unit: str,
    conversion: str,
) -> None:
    product_mapping = client.put(
        "/api/v1/integration-mappings/products",
        json={
            "supplier_id": supplier_id,
            "external_sku": external_sku,
            "product_id": product_id,
            "source_unit": source_unit,
            "units_per_source_unit": conversion,
        },
    )
    warehouse_mapping = client.put(
        "/api/v1/integration-mappings/warehouses",
        json={
            "supplier_id": supplier_id,
            "external_location": external_location,
            "warehouse_id": warehouse_id,
        },
    )
    assert product_mapping.status_code == 200
    assert warehouse_mapping.status_code == 200


def test_supplier_a_json_import_updates_inventory(
    client: TestClient,
    api_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        integrations_route,
        "publish_import_job",
        lambda _: None,
    )
    supplier_id = _create_supplier(
        client,
        code="SUPPLIER_A",
        name="Supplier A",
    )
    product_id, warehouse_id = _create_product_and_warehouse(client)
    _map_partner_keys(
        client,
        supplier_id=supplier_id,
        product_id=product_id,
        warehouse_id=warehouse_id,
        external_sku="A-IP16-256-BLK",
        external_location="A-WEST-01",
        source_unit="EACH",
        conversion="1.000",
    )
    payload = json.loads((FIXTURES / "supplier_a_inventory.json").read_text())

    response = client.post(
        "/api/v1/integrations/supplier-a/inventory",
        json=payload,
        headers={"Idempotency-Key": "supplier-a-test-001"},
    )

    assert response.status_code == 202
    job = response.json()
    assert job["status"] == "queued"
    integration_services.execute_import_job(
        api_session,
        UUID(job["id"]),
        worker_id="test-worker",
        celery_task_id="test-task-a",
    )
    job = client.get(f"/api/v1/imports/{job['id']}").json()
    assert job["status"] == "completed"
    assert job["accepted_records"] == 1
    assert job["rejected_records"] == 0
    inventory = client.get(
        f"/api/v1/inventory?warehouse_id={warehouse_id}&product_id={product_id}"
    ).json()
    assert inventory[0]["on_hand_quantity"] == "120.000"
    assert inventory[0]["available_quantity"] == "85.000"
    attempts = client.get(f"/api/v1/imports/{job['id']}/attempts").json()
    assert attempts[0]["status"] == "succeeded"


def test_supplier_b_csv_converts_cases_and_keeps_rejections(
    client: TestClient,
    api_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        integrations_route,
        "publish_import_job",
        lambda _: None,
    )
    supplier_id = _create_supplier(
        client,
        code="SUPPLIER_B",
        name="Supplier B",
    )
    product_id, warehouse_id = _create_product_and_warehouse(client)
    _map_partner_keys(
        client,
        supplier_id=supplier_id,
        product_id=product_id,
        warehouse_id=warehouse_id,
        external_sku="B-IP16-256-BLK",
        external_location="B-LAX-01",
        source_unit="CASE",
        conversion="12.000",
    )
    content = (FIXTURES / "supplier_b_inventory.csv").read_bytes()
    content += (
        b"SB-20260729-002,2026-07-29T15:00:00Z,UNMAPPED-SKU,B-LAX-01,3.000,12.000\n"
    )

    response = client.post(
        "/api/v1/integrations/supplier-b/inventory-files",
        files={"file": ("inventory.csv", content, "text/csv")},
        headers={"Idempotency-Key": "supplier-b-test-001"},
    )

    assert response.status_code == 202
    job = response.json()
    assert job["status"] == "queued"
    integration_services.execute_import_job(
        api_session,
        UUID(job["id"]),
        worker_id="test-worker",
        celery_task_id="test-task-b",
    )
    job = client.get(f"/api/v1/imports/{job['id']}").json()
    assert job["status"] == "completed_with_errors"
    assert job["total_records"] == 2
    assert job["accepted_records"] == 1
    assert job["rejected_records"] == 1
    errors = client.get(f"/api/v1/imports/{job['id']}/errors").json()
    assert len(errors) == 1
    assert errors[0]["error_code"] == "product_mapping_not_found"
    assert errors[0]["source_row"] == 3
    inventory = client.get(
        f"/api/v1/inventory?warehouse_id={warehouse_id}&product_id={product_id}"
    ).json()
    assert inventory[0]["on_hand_quantity"] == "120.000"


def test_mapping_versions_increment_only_when_configuration_changes(
    client: TestClient,
) -> None:
    supplier_id = _create_supplier(
        client,
        code="SUPPLIER_A",
        name="Supplier A",
    )
    product_id, _ = _create_product_and_warehouse(client)
    request = {
        "supplier_id": supplier_id,
        "external_sku": "VERSIONED-SKU",
        "product_id": product_id,
        "source_unit": "CASE",
        "units_per_source_unit": "6.000",
    }

    first = client.put("/api/v1/integration-mappings/products", json=request)
    unchanged = client.put("/api/v1/integration-mappings/products", json=request)
    changed = client.put(
        "/api/v1/integration-mappings/products",
        json={**request, "units_per_source_unit": "12.000"},
    )

    assert first.json()["version"] == 1
    assert unchanged.json()["version"] == 1
    assert changed.json()["version"] == 2


def test_carrier_c_webhook_advances_the_matching_shipment(
    client: TestClient,
) -> None:
    supplier_id = _create_supplier(
        client,
        code="CARRIER_TEST_SUPPLIER",
        name="Carrier Test Supplier",
    )
    product_id, _ = _create_product_and_warehouse(client)
    purchase_order = client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "external_reference": "P2-CARRIER-PO",
            "lines": [
                {"product_id": product_id, "ordered_quantity": "1.000"},
            ],
        },
    ).json()
    shipment = client.post(
        "/api/v1/shipments",
        json={
            "supplier_id": supplier_id,
            "purchase_order_id": purchase_order["id"],
            "tracking_reference": "C-123456",
        },
    )
    assert shipment.status_code == 201
    payload = json.loads((FIXTURES / "carrier_c_event.json").read_text())

    response = client.post("/api/v1/webhooks/carrier-c", json=payload)

    assert response.status_code == 201
    assert response.json()["status"] == "picked_up"
    assert response.json()["shipped_at"] == "2026-07-29T20:00:00Z"
    assert len(response.json()["events"]) == 1
    duplicate = client.post("/api/v1/webhooks/carrier-c", json=payload)
    assert duplicate.status_code == 409
