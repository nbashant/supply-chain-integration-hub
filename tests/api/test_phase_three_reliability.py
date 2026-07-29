import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import cast
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from supply_chain_hub.api.routes import imports as imports_route
from supply_chain_hub.api.routes import integrations as integrations_route
from supply_chain_hub.application import integration_services
from supply_chain_hub.domain.enums import ImportSourceType, ImportStatus
from supply_chain_hub.domain.exceptions import (
    PermanentImportError,
    TransientImportError,
)
from supply_chain_hub.infrastructure.db import models
from tests.api.conftest import MemoryObjectStore


def _create_supplier_a(client: TestClient) -> str:
    response = client.post(
        "/api/v1/suppliers",
        json={"code": "SUPPLIER_A", "name": "Supplier A"},
    )
    assert response.status_code == 201
    return cast(str, response.json()["id"])


def _supplier_a_content(snapshot_id: str) -> bytes:
    return json.dumps(
        {
            "snapshot_id": snapshot_id,
            "captured_at": "2026-07-29T15:00:00Z",
            "items": [
                {
                    "item_number": "RELIABILITY-SKU",
                    "location": "RELIABILITY-WH",
                    "on_hand": "5.000",
                    "allocated": "1.000",
                    "unit": "EACH",
                }
            ],
        },
        separators=(",", ":"),
    ).encode()


def _submit_direct(
    session: Session,
    content: bytes,
    *,
    idempotency_key: str,
) -> UUID:
    job, created = integration_services.submit_inventory_import(
        session,
        supplier_code="SUPPLIER_A",
        source_type=ImportSourceType.SUPPLIER_A_JSON,
        adapter_version="supplier-a.inventory.v1",
        content=content,
        content_sha256=sha256(content).hexdigest(),
        content_type="application/json",
        idempotency_key=idempotency_key,
    )
    assert created is True
    return job.id


def test_idempotent_submission_returns_the_original_job(
    client: TestClient,
    api_session: Session,
    object_store: MemoryObjectStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_supplier_a(client)
    monkeypatch.setattr(integrations_route, "publish_import_job", lambda _: None)
    content = json.loads(_supplier_a_content("IDEMPOTENT-001"))
    headers = {"Idempotency-Key": "same-logical-request-001"}

    first = client.post(
        "/api/v1/integrations/supplier-a/inventory",
        json=content,
        headers=headers,
    )
    repeated = client.post(
        "/api/v1/integrations/supplier-a/inventory",
        json=content,
        headers=headers,
    )
    changed = client.post(
        "/api/v1/integrations/supplier-a/inventory",
        json={**content, "snapshot_id": "DIFFERENT"},
        headers=headers,
    )

    assert first.status_code == 202
    assert repeated.status_code == 202
    assert first.json()["id"] == repeated.json()["id"]
    assert first.json()["status"] == "queued"
    assert first.json()["payload_object_key"].startswith(
        "raw/inventory/source=supplier_a_json/"
    )
    assert first.json()["payload_size_bytes"] > 0
    assert len(object_store.objects) == 1
    stored_job = api_session.get(models.ImportJob, UUID(first.json()["id"]))
    assert stored_job is not None
    assert stored_job.payload is None
    assert stored_job.payload_object_key in object_store.objects
    assert changed.status_code == 409


def test_idempotency_key_is_required(client: TestClient) -> None:
    _create_supplier_a(client)

    response = client.post(
        "/api/v1/integrations/supplier-a/inventory",
        json=json.loads(_supplier_a_content("NO-KEY")),
    )

    assert response.status_code == 422


def test_transient_failure_schedules_exponential_retry_then_succeeds(
    client: TestClient,
    api_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_supplier_a(client)
    job_id = _submit_direct(
        api_session,
        _supplier_a_content("TRANSIENT-001"),
        idempotency_key="transient-test-001",
    )
    original_adapter = integration_services._adapt_retained_payload

    def fail_transiently(_: object) -> object:
        raise TransientImportError("supplier connection reset")

    monkeypatch.setattr(
        integration_services,
        "_adapt_retained_payload",
        fail_transiently,
    )
    with pytest.raises(TransientImportError):
        integration_services.execute_import_job(
            api_session,
            job_id,
            worker_id="worker-one",
            celery_task_id="task-one",
        )
    disposition = integration_services.record_import_failure(
        api_session,
        job_id,
        TransientImportError("supplier connection reset"),
    )

    assert disposition.retry_scheduled is True
    assert disposition.retry_delay_seconds == 2
    retried_job = integration_services.get_import_job(api_session, job_id)
    assert retried_job.status is ImportStatus.QUEUED
    assert retried_job.attempt_count == 1
    retried_job.next_retry_at = datetime.now(UTC) - timedelta(seconds=1)
    api_session.commit()
    monkeypatch.setattr(
        integration_services,
        "_adapt_retained_payload",
        original_adapter,
    )

    completed = integration_services.execute_import_job(
        api_session,
        job_id,
        worker_id="worker-two",
        celery_task_id="task-two",
    )

    assert completed.status is ImportStatus.COMPLETED_WITH_ERRORS
    assert completed.attempt_count == 2
    attempts = integration_services.list_import_attempts(api_session, job_id)
    assert [attempt.status.value for attempt in attempts] == [
        "retry_scheduled",
        "succeeded",
    ]


def test_preclaim_failure_is_counted_as_a_bounded_attempt(
    client: TestClient,
    api_session: Session,
) -> None:
    _create_supplier_a(client)
    job_id = _submit_direct(
        api_session,
        _supplier_a_content("PRECLAIM-001"),
        idempotency_key="preclaim-test-001",
    )

    disposition = integration_services.record_import_failure(
        api_session,
        job_id,
        TransientImportError("database unavailable before claim"),
    )

    assert disposition.retry_scheduled is True
    job = integration_services.get_import_job(api_session, job_id)
    assert job.status is ImportStatus.QUEUED
    assert job.attempt_count == 1
    attempts = integration_services.list_import_attempts(api_session, job_id)
    assert attempts[0].status.value == "retry_scheduled"


def test_expired_worker_lease_is_recovered(
    client: TestClient,
    api_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_supplier_a(client)
    job_id = _submit_direct(
        api_session,
        _supplier_a_content("LEASE-001"),
        idempotency_key="lease-test-001",
    )

    def stop_after_claim(_: object) -> object:
        raise TransientImportError("worker stopped")

    monkeypatch.setattr(
        integration_services,
        "_adapt_retained_payload",
        stop_after_claim,
    )
    with pytest.raises(TransientImportError):
        integration_services.execute_import_job(
            api_session,
            job_id,
            worker_id="dead-worker",
            celery_task_id="dead-task",
        )
    job = integration_services.get_import_job(api_session, job_id)
    job.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    api_session.commit()

    recovered = integration_services.recover_stale_imports(api_session)

    assert recovered == [job_id]
    job = integration_services.get_import_job(api_session, job_id)
    assert job.status is ImportStatus.QUEUED
    assert job.worker_id is None
    attempts = integration_services.list_import_attempts(api_session, job_id)
    assert attempts[0].status.value == "abandoned"
    assert attempts[0].error_code == "worker_lease_expired"


def test_failed_import_can_be_replayed_as_a_new_linked_job(
    client: TestClient,
    api_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_supplier_a(client)
    job_id = _submit_direct(
        api_session,
        _supplier_a_content("REPLAY-001"),
        idempotency_key="original-failed-001",
    )

    def fail_permanently(_: object) -> object:
        raise PermanentImportError("unsupported partner contract")

    monkeypatch.setattr(
        integration_services,
        "_adapt_retained_payload",
        fail_permanently,
    )
    with pytest.raises(PermanentImportError):
        integration_services.execute_import_job(
            api_session,
            job_id,
            worker_id="worker-one",
            celery_task_id="failed-task",
        )
    disposition = integration_services.record_import_failure(
        api_session,
        job_id,
        PermanentImportError("unsupported partner contract"),
    )
    assert disposition.retry_scheduled is False
    monkeypatch.setattr(imports_route, "publish_import_job", lambda _: None)

    replay = client.post(
        f"/api/v1/imports/{job_id}/retries",
        headers={"Idempotency-Key": "controlled-replay-001"},
    )

    assert replay.status_code == 202
    assert replay.json()["status"] == "queued"
    assert replay.json()["replay_of_job_id"] == str(job_id)
    assert replay.json()["id"] != str(job_id)
