from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any
from uuid import uuid4

import pytest

from supply_chain_hub.infrastructure.object_storage import get_object_store

BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8000")
PARTNER_TOKEN = os.environ.get(
    "PARTNER_API_TOKEN",
    "local-partner-token-change-me",
)


def _request(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, Any]:
    request_headers = {"Accept": "application/json"}
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers=request_headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


@pytest.mark.e2e
def test_live_partner_import_crosses_api_queue_worker_database_and_object_store() -> (
    None
):
    try:
        ready_status, readiness = _request("GET", "/health/ready")
    except (urllib.error.URLError, TimeoutError):
        pytest.skip("The live Docker Compose application is not running.")
    assert ready_status == 200
    assert readiness["object_storage"] == "available"

    supplier_status, suppliers = _request("GET", "/api/v1/suppliers?limit=100")
    assert supplier_status == 200
    supplier = next(
        (item for item in suppliers if item["code"] == "SUPPLIER_A"),
        None,
    )
    if supplier is None:
        created_status, supplier = _request(
            "POST",
            "/api/v1/suppliers",
            {"code": "SUPPLIER_A", "name": "Supplier A"},
        )
        assert created_status == 201

    suffix = uuid4().hex[:10].upper()
    external_sku = f"E2E-{suffix}"
    external_location = f"E2E-WH-{suffix}"
    product_status, product = _request(
        "POST",
        "/api/v1/products",
        {
            "sku": f"E2E-SKU-{suffix}",
            "name": "End-to-end proof product",
            "base_unit": "EACH",
        },
    )
    assert product_status == 201
    warehouse_status, warehouse = _request(
        "POST",
        "/api/v1/warehouses",
        {
            "code": external_location,
            "name": "End-to-end proof warehouse",
            "timezone": "UTC",
        },
    )
    assert warehouse_status == 201
    assert (
        _request(
            "PUT",
            "/api/v1/integration-mappings/products",
            {
                "supplier_id": supplier["id"],
                "external_sku": external_sku,
                "product_id": product["id"],
                "source_unit": "EACH",
                "units_per_source_unit": "1",
            },
        )[0]
        == 200
    )
    assert (
        _request(
            "PUT",
            "/api/v1/integration-mappings/warehouses",
            {
                "supplier_id": supplier["id"],
                "external_location": external_location,
                "warehouse_id": warehouse["id"],
            },
        )[0]
        == 200
    )

    submission_status, job = _request(
        "POST",
        "/api/v1/integrations/supplier-a/inventory",
        {
            "snapshot_id": f"E2E-SNAPSHOT-{suffix}",
            "captured_at": "2026-07-29T19:30:00Z",
            "items": [
                {
                    "item_number": external_sku,
                    "location": external_location,
                    "on_hand": "125",
                    "allocated": "25",
                    "unit": "EACH",
                }
            ],
        },
        {
            "Idempotency-Key": f"e2e-{suffix}",
            "X-Partner-Token": PARTNER_TOKEN,
            "X-Correlation-ID": f"e2e-{suffix}",
        },
    )
    assert submission_status == 202
    assert job["payload_object_key"].startswith("raw/inventory/")
    assert job["payload_size_bytes"] > 0

    deadline = time.monotonic() + 30
    while job["status"] in {"queued", "processing"} and time.monotonic() < deadline:
        time.sleep(0.25)
        job_status, job = _request("GET", f"/api/v1/imports/{job['id']}")
        assert job_status == 200
    assert job["status"] == "completed"
    assert job["accepted_records"] == 1
    assert get_object_store().get(job["payload_object_key"])

    inventory_status, positions = _request(
        "GET",
        (
            "/api/v1/inventory"
            f"?warehouse_id={warehouse['id']}&product_id={product['id']}"
        ),
    )
    assert inventory_status == 200
    assert len(positions) == 1
    assert positions[0]["on_hand_quantity"] == "125.000"
    assert positions[0]["available_quantity"] == "100.000"
