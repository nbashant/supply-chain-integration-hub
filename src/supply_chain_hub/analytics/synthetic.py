import numpy as np

from supply_chain_hub.analytics.types import (
    HubInventoryRow,
    RiskInput,
    SupplierInventoryRow,
)


def generate_reconciliation_inputs(
    row_count: int,
    seed: int,
) -> tuple[list[SupplierInventoryRow], list[HubInventoryRow]]:
    if row_count < 1:
        raise ValueError("row_count must be positive.")
    rng = np.random.default_rng(seed)
    hub_quantities = rng.integers(0, 500, size=row_count, dtype=np.int64)
    deltas = rng.choice(
        np.array([-20, -8, -3, 0, 0, 0, 0, 4, 9, 25], dtype=np.int64),
        size=row_count,
    )
    reported_quantities = np.maximum(hub_quantities + deltas, 0)
    suppliers: list[SupplierInventoryRow] = []
    hub: list[HubInventoryRow] = []
    for index in range(row_count):
        product_sku = f"SYN-SKU-{index:07d}"
        warehouse_code = f"SYN-WH-{index % 25:02d}"
        suppliers.append(
            SupplierInventoryRow(
                record_index=index,
                supplier_code=f"SYN-SUPPLIER-{index % 4}",
                product_sku=product_sku,
                warehouse_code=warehouse_code,
                reported_quantity=int(reported_quantities[index]),
            )
        )
        hub.append(
            HubInventoryRow(
                record_index=index,
                product_sku=product_sku,
                warehouse_code=warehouse_code,
                hub_quantity=int(hub_quantities[index]),
            )
        )
    return suppliers, hub


def generate_risk_inputs(row_count: int, seed: int) -> list[RiskInput]:
    if row_count < 1:
        raise ValueError("row_count must be positive.")
    rng = np.random.default_rng(seed)
    on_hand = rng.integers(20, 500, size=row_count)
    reserved = np.floor(on_hand * rng.uniform(0.0, 0.45, size=row_count))
    inbound = rng.integers(0, 180, size=row_count)
    available = on_hand - reserved
    forecast = np.maximum(
        1,
        np.rint((available + inbound) * rng.uniform(0.65, 1.45, size=row_count)),
    )
    actual = np.maximum(
        0,
        np.rint(forecast * rng.normal(1.0, 0.18, size=row_count)),
    )
    return [
        RiskInput(
            record_index=index,
            product_sku=f"SYN-RISK-SKU-{index:07d}",
            warehouse_code=f"SYN-WH-{index % 25:02d}",
            on_hand_quantity=float(on_hand[index]),
            reserved_quantity=float(reserved[index]),
            inbound_quantity=float(inbound[index]),
            forecast_quantity=float(forecast[index]),
            actual_demand_quantity=float(actual[index]),
        )
        for index in range(row_count)
    ]
