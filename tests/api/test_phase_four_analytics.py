from typing import cast

from fastapi.testclient import TestClient


def test_pandas_and_polars_runs_persist_equivalent_results(
    client: TestClient,
) -> None:
    pandas_response = client.post(
        "/api/v1/analytics/reconciliations",
        json={"engine": "pandas", "row_count": 100, "seed": 20260729},
    )
    polars_response = client.post(
        "/api/v1/analytics/reconciliations",
        json={"engine": "polars", "row_count": 100, "seed": 20260729},
    )

    assert pandas_response.status_code == 201
    assert polars_response.status_code == 201
    pandas_run = pandas_response.json()
    polars_run = polars_response.json()
    assert pandas_run["run_type"] == "inventory_reconciliation"
    assert pandas_run["engine"] == "pandas"
    assert polars_run["engine"] == "polars"
    assert pandas_run["summary"]["match_count"] == polars_run["summary"]["match_count"]
    assert (
        pandas_run["summary"]["mismatch_count"]
        == polars_run["summary"]["mismatch_count"]
    )

    pandas_results = client.get(
        "/api/v1/reconciliations/inventory",
        params={
            "run_id": pandas_run["id"],
            "only_mismatches": "true",
            "limit": 1000,
        },
    )
    polars_results = client.get(
        "/api/v1/reconciliations/inventory",
        params={
            "run_id": polars_run["id"],
            "only_mismatches": "true",
            "limit": 1000,
        },
    )

    assert pandas_results.status_code == 200
    assert polars_results.status_code == 200
    pandas_rows = pandas_results.json()
    polars_rows = polars_results.json()
    assert len(pandas_rows) == pandas_run["summary"]["mismatch_count"]
    assert [
        {key: value for key, value in row.items() if key not in {"id", "run_id"}}
        for row in pandas_rows
    ] == [
        {key: value for key, value in row.items() if key not in {"id", "run_id"}}
        for row in polars_rows
    ]
    assert all(row["matches"] is False for row in pandas_rows)


def test_reconciliation_schema_rejects_the_numpy_engine(client: TestClient) -> None:
    response = client.post(
        "/api/v1/analytics/reconciliations",
        json={"engine": "numpy", "row_count": 10, "seed": 1},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_validation_error"


def test_stockout_risk_run_persists_vectorized_results(client: TestClient) -> None:
    response = client.post(
        "/api/v1/analytics/stockout-risks",
        json={"row_count": 100, "seed": 20260729},
    )

    assert response.status_code == 201
    run = response.json()
    summary = cast(dict[str, object], run["summary"])
    severity_counts = cast(dict[str, int], summary["severity_counts"])
    thresholds = cast(dict[str, object], summary["thresholds"])
    forecast_metrics = cast(dict[str, float], summary["forecast_metrics"])
    assert run["run_type"] == "stockout_risk"
    assert run["engine"] == "numpy"
    assert sum(severity_counts.values()) == 100
    assert thresholds["method"] == "positive shortage-ratio p50 and p80"
    assert forecast_metrics["mean_absolute_error"] >= 0

    high_response = client.get(
        "/api/v1/risks/stockouts",
        params={"run_id": run["id"], "severity": "high", "limit": 1000},
    )

    assert high_response.status_code == 200
    high_rows = high_response.json()
    assert len(high_rows) == severity_counts["high"]
    assert all(row["severity"] == "high" for row in high_rows)
    for row in high_rows:
        expected_available = max(
            float(row["on_hand_quantity"]) - float(row["reserved_quantity"]),
            0,
        )
        expected_ending = (
            expected_available
            + float(row["inbound_quantity"])
            - float(row["forecast_quantity"])
        )
        assert float(row["available_quantity"]) == expected_available
        assert float(row["projected_ending_quantity"]) == expected_ending
        assert float(row["projected_shortage_quantity"]) == max(-expected_ending, 0)


def test_result_endpoint_rejects_the_wrong_analytics_run_type(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/analytics/stockout-risks",
        json={"row_count": 10, "seed": 7},
    )
    run_id = response.json()["id"]

    wrong_endpoint = client.get(
        "/api/v1/reconciliations/inventory",
        params={"run_id": run_id},
    )

    assert wrong_endpoint.status_code == 409
