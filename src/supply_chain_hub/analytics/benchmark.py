import argparse
import json
import platform
import statistics
from collections.abc import Sequence
from pathlib import Path
from time import perf_counter_ns

import numpy as np
import pandas as pd
import polars as pl

from supply_chain_hub.analytics.reconciliation import (
    ReconciliationFunction,
    reconcile_with_pandas,
    reconcile_with_polars,
)
from supply_chain_hub.analytics.synthetic import generate_reconciliation_inputs
from supply_chain_hub.analytics.types import (
    HubInventoryRow,
    ReconciliationResult,
    SupplierInventoryRow,
)


def benchmark_reconciliation(
    *,
    row_count: int,
    seed: int,
    repeats: int,
) -> dict[str, object]:
    if repeats < 2:
        raise ValueError("At least two benchmark repetitions are required.")
    supplier_rows, hub_rows = generate_reconciliation_inputs(row_count, seed)
    pandas_stats, pandas_results = _benchmark_engine(
        reconcile_with_pandas,
        supplier_rows,
        hub_rows,
        repeats,
    )
    polars_stats, polars_results = _benchmark_engine(
        reconcile_with_polars,
        supplier_rows,
        hub_rows,
        repeats,
    )
    if pandas_results != polars_results:
        raise RuntimeError("Pandas and Polars produced different results.")
    mismatch_count = sum(not result.matches for result in pandas_results)
    return {
        "workload": {
            "row_count": row_count,
            "seed": seed,
            "repeats": repeats,
            "measurement": (
                "DataFrame construction, one-to-one join, difference "
                "calculation, sort, and canonical result materialization"
            ),
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "polars": pl.__version__,
        },
        "correctness": {
            "outputs_equal": True,
            "mismatch_count": mismatch_count,
            "match_count": row_count - mismatch_count,
        },
        "engines": {
            "pandas": pandas_stats,
            "polars": polars_stats,
        },
    }


def _benchmark_engine(
    function: ReconciliationFunction,
    supplier_rows: list[SupplierInventoryRow],
    hub_rows: list[HubInventoryRow],
    repeats: int,
) -> tuple[dict[str, object], list[ReconciliationResult]]:
    function(supplier_rows, hub_rows)
    durations_ms: list[float] = []
    final_execution = None
    for _ in range(repeats):
        started = perf_counter_ns()
        final_execution = function(supplier_rows, hub_rows)
        durations_ms.append((perf_counter_ns() - started) / 1_000_000)
    if final_execution is None:
        raise RuntimeError("The benchmark did not execute.")
    return (
        {
            "durations_ms": durations_ms,
            "minimum_ms": min(durations_ms),
            "median_ms": statistics.median(durations_ms),
            "maximum_ms": max(durations_ms),
            "p95_ms": float(np.percentile(durations_ms, 95)),
            "dataframe_bytes": final_execution.dataframe_bytes,
        },
        list(final_execution.results),
    )


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare equivalent Pandas and Polars reconciliation work.",
    )
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=20260729)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/phase4_benchmark.json"),
    )
    options = parser.parse_args(arguments)
    report = benchmark_reconciliation(
        row_count=options.rows,
        seed=options.seed,
        repeats=options.repeats,
    )
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
