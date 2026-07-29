from collections.abc import Callable
from typing import Any, cast

import pandas as pd
import polars as pl

from supply_chain_hub.analytics.types import (
    HubInventoryRow,
    ReconciliationExecution,
    ReconciliationResult,
    SupplierInventoryRow,
)

ReconciliationFunction = Callable[
    [list[SupplierInventoryRow], list[HubInventoryRow]],
    ReconciliationExecution,
]


def reconcile_with_pandas(
    supplier_rows: list[SupplierInventoryRow],
    hub_rows: list[HubInventoryRow],
) -> ReconciliationExecution:
    supplier_frame = pd.DataFrame(
        {
            "record_index": [row.record_index for row in supplier_rows],
            "supplier_code": [row.supplier_code for row in supplier_rows],
            "product_sku": [row.product_sku for row in supplier_rows],
            "warehouse_code": [row.warehouse_code for row in supplier_rows],
            "reported_quantity": [row.reported_quantity for row in supplier_rows],
        }
    )
    hub_frame = pd.DataFrame(
        {
            "record_index": [row.record_index for row in hub_rows],
            "product_sku": [row.product_sku for row in hub_rows],
            "warehouse_code": [row.warehouse_code for row in hub_rows],
            "hub_quantity": [row.hub_quantity for row in hub_rows],
        }
    )
    joined = supplier_frame.merge(
        hub_frame,
        on=["record_index", "product_sku", "warehouse_code"],
        how="inner",
        validate="one_to_one",
    )
    if len(joined) != len(supplier_rows) or len(joined) != len(hub_rows):
        raise ValueError("Reconciliation inputs do not contain matching keys.")
    joined["difference_quantity"] = joined["reported_quantity"] - joined["hub_quantity"]
    joined["matches"] = joined["difference_quantity"] == 0
    joined = joined.sort_values("record_index")
    results = [
        ReconciliationResult(
            record_index=int(cast(Any, row.record_index)),
            supplier_code=str(row.supplier_code),
            product_sku=str(row.product_sku),
            warehouse_code=str(row.warehouse_code),
            reported_quantity=int(cast(Any, row.reported_quantity)),
            hub_quantity=int(cast(Any, row.hub_quantity)),
            difference_quantity=int(cast(Any, row.difference_quantity)),
            matches=bool(row.matches),
        )
        for row in joined.itertuples(index=False)
    ]
    dataframe_bytes = int(
        supplier_frame.memory_usage(index=True, deep=True).sum()
        + hub_frame.memory_usage(index=True, deep=True).sum()
        + joined.memory_usage(index=True, deep=True).sum()
    )
    return ReconciliationExecution(
        results=results,
        dataframe_bytes=dataframe_bytes,
    )


def reconcile_with_polars(
    supplier_rows: list[SupplierInventoryRow],
    hub_rows: list[HubInventoryRow],
) -> ReconciliationExecution:
    supplier_frame = pl.DataFrame(
        {
            "record_index": [row.record_index for row in supplier_rows],
            "supplier_code": [row.supplier_code for row in supplier_rows],
            "product_sku": [row.product_sku for row in supplier_rows],
            "warehouse_code": [row.warehouse_code for row in supplier_rows],
            "reported_quantity": [row.reported_quantity for row in supplier_rows],
        }
    )
    hub_frame = pl.DataFrame(
        {
            "record_index": [row.record_index for row in hub_rows],
            "product_sku": [row.product_sku for row in hub_rows],
            "warehouse_code": [row.warehouse_code for row in hub_rows],
            "hub_quantity": [row.hub_quantity for row in hub_rows],
        }
    )
    joined = (
        supplier_frame.join(
            hub_frame,
            on=["record_index", "product_sku", "warehouse_code"],
            how="inner",
            validate="1:1",
        )
        .with_columns(
            (pl.col("reported_quantity") - pl.col("hub_quantity")).alias(
                "difference_quantity"
            )
        )
        .with_columns((pl.col("difference_quantity") == 0).alias("matches"))
        .sort("record_index")
    )
    if joined.height != len(supplier_rows) or joined.height != len(hub_rows):
        raise ValueError("Reconciliation inputs do not contain matching keys.")
    results = [
        ReconciliationResult(
            record_index=int(row["record_index"]),
            supplier_code=str(row["supplier_code"]),
            product_sku=str(row["product_sku"]),
            warehouse_code=str(row["warehouse_code"]),
            reported_quantity=int(row["reported_quantity"]),
            hub_quantity=int(row["hub_quantity"]),
            difference_quantity=int(row["difference_quantity"]),
            matches=bool(row["matches"]),
        )
        for row in joined.iter_rows(named=True)
    ]
    dataframe_bytes = int(
        supplier_frame.estimated_size()
        + hub_frame.estimated_size()
        + joined.estimated_size()
    )
    return ReconciliationExecution(
        results=results,
        dataframe_bytes=dataframe_bytes,
    )
