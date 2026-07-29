from uuid import uuid4

import pytest

from supply_chain_hub.application.integration_services import (
    calculate_retry_delay,
    classify_import_failure,
)
from supply_chain_hub.domain.exceptions import PermanentImportError
from supply_chain_hub.worker import queueing, tasks
from supply_chain_hub.worker.celery_app import celery_app


def test_retry_delay_uses_bounded_exponential_backoff() -> None:
    assert [calculate_retry_delay(attempt) for attempt in range(1, 8)] == [
        2,
        4,
        8,
        16,
        32,
        60,
        60,
    ]


def test_unknown_and_permanent_failures_are_not_retried() -> None:
    assert classify_import_failure(ValueError("bug")) == (
        False,
        "unexpected_import_error",
    )
    assert classify_import_failure(PermanentImportError("bad data")) == (
        False,
        "permanent_import_error",
    )


def test_celery_uses_late_acknowledgement_without_a_result_backend() -> None:
    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.task_reject_on_worker_lost is True
    assert celery_app.conf.worker_prefetch_multiplier == 1
    assert celery_app.conf.result_backend is None


def test_queue_message_contains_only_the_durable_job_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = uuid4()
    captured: dict[str, object] = {}

    class Published:
        id = "celery-task-id"

    class FakeTask:
        @staticmethod
        def apply_async(*, args: list[str], countdown: float) -> Published:
            captured["args"] = args
            captured["countdown"] = countdown
            return Published()

    monkeypatch.setattr(tasks, "process_import_job_task", FakeTask())

    task_id = queueing.publish_import_job(job_id)

    assert task_id == "celery-task-id"
    assert captured == {"args": [str(job_id)], "countdown": 0.5}
