import json
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from supply_chain_hub.api.routes import learning
from supply_chain_hub.application import integration_services


def test_learning_demo_runs_real_import_and_explains_each_stage(
    client: TestClient,
    api_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(learning, "publish_import_job", lambda _: None)

    response = client.post(
        "/api/v1/learning/demos/import",
        headers={"X-Correlation-ID": "learning-test-trace"},
    )

    assert response.status_code == 202
    queued = response.json()
    job_id = UUID(queued["job"]["id"])
    assert queued["job"]["status"] == "queued"
    assert queued["job"]["correlation_id"] == "learning-test-trace"
    integration_services.execute_import_job(
        api_session,
        job_id,
        worker_id="learning-test-worker",
        celery_task_id="learning-test-task",
    )

    detail = client.get(f"/api/v1/learning/imports/{job_id}")

    assert detail.status_code == 200
    body = detail.json()
    assert body["job"]["status"] == "completed"
    assert body["snapshots"][0]["canonical_on_hand"] == "120.000"
    assert Decimal(body["snapshots"][0]["source_on_hand"]) == Decimal("120")
    assert [event["stage"] for event in body["events"]] == [
        "request.validated",
        "payload.stored",
        "job.queued",
        "worker.claimed",
        "payload.verified",
        "payload.transformed",
        "inventory.committed",
        "job.completed",
    ]
    assert all("items" not in event["details"] for event in body["events"])

    stream = client.get(f"/api/v1/learning/imports/{job_id}/events?follow=false")
    assert stream.status_code == 200
    assert "event: operation" in stream.text
    assert 'event: complete\ndata: {"status":"completed"}' in stream.text


def test_learning_overview_reports_counts_and_live_dependencies(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(learning, "object_store_is_available", lambda: True)
    monkeypatch.setattr(learning, "redis_is_available", lambda: True)

    response = client.get("/api/v1/learning/overview")

    assert response.status_code == 200
    body = response.json()
    assert body["entity_counts"]["operation_events"] == 0
    component_statuses = {
        component["id"]: component["status"] for component in body["components"]
    }
    assert component_statuses["postgresql"] == "available"
    assert component_statuses["seaweedfs"] == "available"
    assert component_statuses["redis"] == "available"


def test_bundled_learning_console_is_served_without_login(
    client: TestClient,
) -> None:
    response = client.get("/hub")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Supply Chain Hub" in response.text
    assert "/hub/assets/" in response.text


def test_learning_pipeline_catalog_reads_immutable_manifests(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    object_store: Any,
) -> None:
    manifest: dict[str, object] = {
        "status": "succeeded",
        "partition_date": "2026-07-29",
        "run_id": "learning-run",
        "created_at": "2026-07-29T20:00:00+00:00",
        "input_rows": 25,
        "curated_keys": ["curated/result.parquet"],
        "summary_keys": ["summary/result.parquet"],
        "spark_version": "4.2.0",
    }
    key = "manifests/inventory-risk/event_date=2026-07-29/run_id=learning-run.json"
    content = json.dumps(manifest).encode()
    object_store.put(
        key,
        content,
        content_type="application/json",
        sha256="not-used-by-memory-store",
    )
    monkeypatch.setattr(learning, "get_object_store", lambda: object_store)

    response = client.get("/api/v1/learning/pipelines")

    assert response.status_code == 200
    assert response.json()[0]["manifest_key"] == key
    assert response.json()[0]["curated_object_count"] == 1
    assert response.json()[0]["summary_object_count"] == 1


def test_learning_analytics_comparison_uses_repeated_equal_work(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/learning/analytics/compare",
        json={"row_count": 100, "repeats": 3, "seed": 42},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["correctness"]["outputs_equal"] is True
    assert len(body["engines"]["pandas"]["durations_ms"]) == 3
    assert len(body["engines"]["polars"]["durations_ms"]) == 3
    assert (
        body["engines"]["pandas"]["maximum_ms"]
        >= (body["engines"]["pandas"]["minimum_ms"])
    )
