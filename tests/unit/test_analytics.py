import math

import numpy as np
import pytest

from supply_chain_hub.analytics.benchmark import benchmark_reconciliation
from supply_chain_hub.analytics.reconciliation import (
    reconcile_with_pandas,
    reconcile_with_polars,
)
from supply_chain_hub.analytics.risk import (
    calculate_forecast_metrics,
    calculate_stockout_risks,
)
from supply_chain_hub.analytics.synthetic import (
    generate_reconciliation_inputs,
    generate_risk_inputs,
)
from supply_chain_hub.analytics.types import (
    HubInventoryRow,
    RiskInput,
    SupplierInventoryRow,
)
from supply_chain_hub.domain.enums import RiskSeverity


def test_synthetic_generators_are_reproducible_from_the_seed() -> None:
    first_reconciliation = generate_reconciliation_inputs(25, 42)
    repeated_reconciliation = generate_reconciliation_inputs(25, 42)
    changed_reconciliation = generate_reconciliation_inputs(25, 43)
    first_risks = generate_risk_inputs(25, 42)

    assert first_reconciliation == repeated_reconciliation
    assert first_reconciliation != changed_reconciliation
    assert first_risks == generate_risk_inputs(25, 42)
    assert first_risks != generate_risk_inputs(25, 43)


def test_pandas_and_polars_produce_the_same_canonical_reconciliation() -> None:
    supplier_rows = [
        SupplierInventoryRow(1, "SUP-A", "SKU-2", "WH-1", 17),
        SupplierInventoryRow(0, "SUP-A", "SKU-1", "WH-1", 10),
    ]
    hub_rows = [
        HubInventoryRow(0, "SKU-1", "WH-1", 10),
        HubInventoryRow(1, "SKU-2", "WH-1", 20),
    ]

    pandas_execution = reconcile_with_pandas(supplier_rows, hub_rows)
    polars_execution = reconcile_with_polars(supplier_rows, hub_rows)

    assert pandas_execution.results == polars_execution.results
    assert [result.record_index for result in pandas_execution.results] == [0, 1]
    assert pandas_execution.results[0].matches is True
    assert pandas_execution.results[1].difference_quantity == -3
    assert pandas_execution.results[1].matches is False
    assert pandas_execution.dataframe_bytes > 0
    assert polars_execution.dataframe_bytes > 0


def test_reconciliation_rejects_inputs_with_unmatched_keys() -> None:
    supplier_rows = [SupplierInventoryRow(0, "SUP-A", "SKU-1", "WH-1", 10)]
    hub_rows = [HubInventoryRow(0, "DIFFERENT", "WH-1", 10)]

    with pytest.raises(ValueError, match="matching keys"):
        reconcile_with_pandas(supplier_rows, hub_rows)
    with pytest.raises(ValueError, match="matching keys"):
        reconcile_with_polars(supplier_rows, hub_rows)


def test_numpy_stockout_math_and_forecast_metrics_are_explicit() -> None:
    records = [
        RiskInput(0, "SKU-1", "WH-1", 100, 20, 10, 120, 110),
        RiskInput(1, "SKU-2", "WH-1", 80, 10, 20, 50, 60),
    ]

    execution = calculate_stockout_risks(records)
    shortage = execution.results[0]
    covered = execution.results[1]

    assert shortage.available_quantity == 80
    assert shortage.projected_ending_quantity == -30
    assert shortage.projected_shortage_quantity == 30
    assert shortage.shortage_ratio == 0.25
    assert shortage.severity is RiskSeverity.LOW
    assert covered.projected_ending_quantity == 40
    assert covered.projected_shortage_quantity == 0
    assert covered.shortage_ratio == 0
    assert covered.severity is RiskSeverity.NONE
    assert execution.thresholds.low_to_medium == 0.25
    assert execution.thresholds.medium_to_high == 0.25
    assert execution.forecast_metrics.mean_absolute_error == 10
    assert execution.forecast_metrics.root_mean_squared_error == 10
    assert execution.forecast_metrics.bias == 0
    assert math.isclose(
        execution.forecast_metrics.weighted_absolute_percentage_error,
        20 / 170,
    )


def test_forecast_metrics_require_equal_nonempty_arrays() -> None:
    with pytest.raises(ValueError, match="equal nonzero shape"):
        calculate_forecast_metrics(
            np.asarray([1.0, 2.0]),
            np.asarray([1.0]),
        )
    with pytest.raises(ValueError, match="equal nonzero shape"):
        calculate_forecast_metrics(np.asarray([]), np.asarray([]))


def test_benchmark_compares_equal_outputs_before_reporting_performance() -> None:
    report = benchmark_reconciliation(row_count=200, seed=42, repeats=2)
    correctness = report["correctness"]
    engines = report["engines"]

    assert isinstance(correctness, dict)
    assert correctness["outputs_equal"] is True
    assert correctness["match_count"] + correctness["mismatch_count"] == 200
    assert isinstance(engines, dict)
    assert engines["pandas"]["median_ms"] > 0
    assert engines["polars"]["median_ms"] > 0
    assert len(engines["pandas"]["durations_ms"]) == 2
    assert engines["pandas"]["maximum_ms"] >= engines["pandas"]["minimum_ms"]
