from __future__ import annotations

import argparse
import csv
import io
from collections.abc import Sequence
from datetime import date, timedelta

import numpy as np
from s3_io import PipelineObjectStore

FIELD_NAMES = [
    "event_date",
    "supplier_code",
    "product_sku",
    "warehouse_code",
    "on_hand_quantity",
    "reserved_quantity",
    "inbound_quantity",
    "forecast_quantity",
    "actual_demand_quantity",
]


def _date_range(start: date, end: date) -> list[date]:
    if end < start:
        raise ValueError("The end date must not precede the start date.")
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def generate_csv(
    partition_date: date,
    *,
    row_count: int,
    inject_invalid: bool,
) -> bytes:
    if row_count < 1:
        raise ValueError("row_count must be positive.")
    rng = np.random.default_rng(int(partition_date.strftime("%Y%m%d")))
    on_hand = rng.integers(20, 900, size=row_count)
    reserved = np.floor(on_hand * rng.uniform(0.0, 0.4, size=row_count)).astype(int)
    inbound = rng.integers(0, 250, size=row_count)
    available = on_hand - reserved
    forecast = np.maximum(
        1,
        np.rint((available + inbound) * rng.uniform(0.7, 1.35, size=row_count)),
    ).astype(int)
    actual = np.maximum(
        0,
        np.rint(forecast * rng.normal(1.0, 0.15, size=row_count)),
    ).astype(int)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=FIELD_NAMES)
    writer.writeheader()
    for index in range(row_count):
        writer.writerow(
            {
                "event_date": partition_date.isoformat(),
                "supplier_code": f"HISTORY-SUPPLIER-{index % 3}",
                "product_sku": f"HISTORY-SKU-{index:08d}",
                "warehouse_code": f"HISTORY-WH-{index % 20:02d}",
                "on_hand_quantity": int(on_hand[index]),
                "reserved_quantity": int(reserved[index]),
                "inbound_quantity": int(inbound[index]),
                "forecast_quantity": int(forecast[index]),
                "actual_demand_quantity": int(actual[index]),
            }
        )
    if inject_invalid:
        writer.writerow(
            {
                "event_date": partition_date.isoformat(),
                "supplier_code": "BROKEN-SUPPLIER",
                "product_sku": "",
                "warehouse_code": "HISTORY-WH-00",
                "on_hand_quantity": -1,
                "reserved_quantity": 0,
                "inbound_quantity": 0,
                "forecast_quantity": 10,
                "actual_demand_quantity": 10,
            }
        )
    return output.getvalue().encode()


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create deterministic historical inventory source partitions."
    )
    parser.add_argument("--start-date", type=date.fromisoformat, required=True)
    parser.add_argument("--end-date", type=date.fromisoformat, required=True)
    parser.add_argument("--rows-per-day", type=int, default=10_000)
    parser.add_argument("--inject-invalid", action="store_true")
    options = parser.parse_args(arguments)
    store = PipelineObjectStore()
    for partition_date in _date_range(options.start_date, options.end_date):
        content = generate_csv(
            partition_date,
            row_count=options.rows_per_day,
            inject_invalid=options.inject_invalid,
        )
        key = (
            "raw/history/inventory/"
            f"event_date={partition_date.isoformat()}/"
            "inventory.csv"
        )
        store.put_bytes(key, content, content_type="text/csv")
        print(f"seeded {key} ({len(content)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
