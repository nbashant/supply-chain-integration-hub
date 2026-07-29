from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from supply_chain_hub.api.routes import health


def test_unknown_supplier_uses_the_standard_error_contract(
    client: TestClient,
) -> None:
    response = client.get(f"/api/v1/suppliers/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "resource_not_found"


def test_request_validation_uses_the_standard_error_contract(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/suppliers",
        json={"code": "contains spaces", "name": ""},
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "request_validation_error"
    assert payload["error"]["details"]


def test_invalid_warehouse_timezone_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/warehouses",
        json={
            "code": "TEST-01",
            "name": "Test",
            "timezone": "Mars/Olympus_Mons",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_validation_error"


def test_readiness_reports_redis_outage(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(health, "redis_is_available", lambda: False)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["dependencies"] == {
        "database": "available",
        "redis": "unavailable",
        "object_storage": "available",
    }


def test_readiness_reports_object_storage_outage(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(health, "object_store_is_available", lambda: False)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["dependencies"] == {
        "database": "available",
        "redis": "available",
        "object_storage": "unavailable",
    }
