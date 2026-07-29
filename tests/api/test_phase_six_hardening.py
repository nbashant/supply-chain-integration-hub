from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from supply_chain_hub.settings.config import Settings


def test_request_correlation_security_headers_and_metrics(
    client: TestClient,
) -> None:
    response = client.get(
        "/health/live",
        headers={"X-Correlation-ID": "phase-six-proof"},
    )

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == "phase-six-proof"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Cache-Control"] == "no-store"

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "supply_chain_http_requests_total" in metrics.text
    assert 'route="/health/live"' in metrics.text


def test_unsafe_correlation_id_is_replaced(client: TestClient) -> None:
    response = client.get(
        "/health/live",
        headers={"X-Correlation-ID": "contains spaces and is not safe"},
    )

    UUID(response.headers["X-Correlation-ID"])


def test_partner_routes_require_the_local_api_token(client: TestClient) -> None:
    response = client.post(
        "/api/v1/integrations/supplier-a/inventory",
        headers={
            "Idempotency-Key": "unauthorized-proof",
            "X-Partner-Token": "wrong-token",
        },
        json={},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "A valid partner token is required."


def test_production_rejects_the_local_partner_token_placeholder() -> None:
    with pytest.raises(ValidationError):
        Settings(app_environment="production")

    settings = Settings(
        app_environment="production",
        partner_api_token="a-non-placeholder-production-secret",
    )
    assert settings.app_environment == "production"
