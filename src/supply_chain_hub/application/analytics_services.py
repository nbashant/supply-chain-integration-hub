from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal
from time import perf_counter_ns
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from supply_chain_hub.analytics.reconciliation import (
    reconcile_with_pandas,
    reconcile_with_polars,
)
from supply_chain_hub.analytics.risk import calculate_stockout_risks
from supply_chain_hub.analytics.synthetic import (
    generate_reconciliation_inputs,
    generate_risk_inputs,
)
from supply_chain_hub.domain.enums import (
    AnalyticsEngine,
    AnalyticsRunType,
    RiskSeverity,
)
from supply_chain_hub.domain.exceptions import (
    ResourceConflictError,
    ResourceNotFoundError,
)
from supply_chain_hub.infrastructure.db import models

THREE_PLACES = Decimal("0.001")
SIX_PLACES = Decimal("0.000001")


def run_reconciliation(
    session: Session,
    *,
    engine: AnalyticsEngine,
    row_count: int,
    seed: int,
) -> models.AnalyticsRun:
    if engine not in {AnalyticsEngine.PANDAS, AnalyticsEngine.POLARS}:
        raise ResourceConflictError(
            "Inventory reconciliation supports only pandas or polars."
        )
    supplier_rows, hub_rows = generate_reconciliation_inputs(row_count, seed)
    started = perf_counter_ns()
    if engine is AnalyticsEngine.PANDAS:
        execution = reconcile_with_pandas(supplier_rows, hub_rows)
    else:
        execution = reconcile_with_polars(supplier_rows, hub_rows)
    duration_ms = Decimal(perf_counter_ns() - started) / Decimal("1000000")
    mismatch_count = sum(not result.matches for result in execution.results)
    run = models.AnalyticsRun(
        run_type=AnalyticsRunType.INVENTORY_RECONCILIATION,
        engine=engine,
        dataset_seed=seed,
        input_rows=row_count,
        duration_ms=_decimal(duration_ms),
        summary={
            "match_count": row_count - mismatch_count,
            "mismatch_count": mismatch_count,
            "mismatch_rate": mismatch_count / row_count,
            "dataframe_bytes": execution.dataframe_bytes,
        },
        reconciliations=[
            models.InventoryReconciliation(
                record_index=result.record_index,
                supplier_code=result.supplier_code,
                product_sku=result.product_sku,
                warehouse_code=result.warehouse_code,
                reported_quantity=Decimal(result.reported_quantity),
                hub_quantity=Decimal(result.hub_quantity),
                difference_quantity=Decimal(result.difference_quantity),
                matches=result.matches,
            )
            for result in execution.results
        ],
    )
    session.add(run)
    _commit(session, "The reconciliation run could not be persisted.")
    session.refresh(run)
    return run


def run_stockout_risk(
    session: Session,
    *,
    row_count: int,
    seed: int,
) -> models.AnalyticsRun:
    inputs = generate_risk_inputs(row_count, seed)
    started = perf_counter_ns()
    execution = calculate_stockout_risks(inputs)
    duration_ms = Decimal(perf_counter_ns() - started) / Decimal("1000000")
    severity_counts = {
        severity.value: sum(result.severity is severity for result in execution.results)
        for severity in RiskSeverity
    }
    metrics = execution.forecast_metrics
    run = models.AnalyticsRun(
        run_type=AnalyticsRunType.STOCKOUT_RISK,
        engine=AnalyticsEngine.NUMPY,
        dataset_seed=seed,
        input_rows=row_count,
        duration_ms=_decimal(duration_ms),
        summary={
            "severity_counts": severity_counts,
            "thresholds": {
                "low_to_medium": execution.thresholds.low_to_medium,
                "medium_to_high": execution.thresholds.medium_to_high,
                "method": "positive shortage-ratio p50 and p80",
            },
            "forecast_metrics": {
                "mean_absolute_error": metrics.mean_absolute_error,
                "root_mean_squared_error": metrics.root_mean_squared_error,
                "bias": metrics.bias,
                "weighted_absolute_percentage_error": (
                    metrics.weighted_absolute_percentage_error
                ),
            },
        },
        stockout_risks=[
            models.StockoutRisk(
                record_index=result.record_index,
                product_sku=result.product_sku,
                warehouse_code=result.warehouse_code,
                on_hand_quantity=_decimal(result.on_hand_quantity),
                reserved_quantity=_decimal(result.reserved_quantity),
                inbound_quantity=_decimal(result.inbound_quantity),
                forecast_quantity=_decimal(result.forecast_quantity),
                actual_demand_quantity=_decimal(result.actual_demand_quantity),
                available_quantity=_decimal(result.available_quantity),
                projected_ending_quantity=_decimal(result.projected_ending_quantity),
                projected_shortage_quantity=_decimal(
                    result.projected_shortage_quantity
                ),
                shortage_ratio=_decimal(
                    result.shortage_ratio,
                    quantum=SIX_PLACES,
                ),
                severity=result.severity,
            )
            for result in execution.results
        ],
    )
    session.add(run)
    _commit(session, "The stockout-risk run could not be persisted.")
    session.refresh(run)
    return run


def get_analytics_run(session: Session, run_id: UUID) -> models.AnalyticsRun:
    run = session.get(models.AnalyticsRun, run_id)
    if run is None:
        raise ResourceNotFoundError(f"Analytics run '{run_id}' was not found.")
    return run


def list_reconciliations(
    session: Session,
    *,
    run_id: UUID,
    only_mismatches: bool,
    offset: int,
    limit: int,
) -> Sequence[models.InventoryReconciliation]:
    run = get_analytics_run(session, run_id)
    if run.run_type is not AnalyticsRunType.INVENTORY_RECONCILIATION:
        raise ResourceConflictError(
            f"Analytics run '{run_id}' is not a reconciliation run."
        )
    statement = select(models.InventoryReconciliation).where(
        models.InventoryReconciliation.run_id == run_id
    )
    if only_mismatches:
        statement = statement.where(models.InventoryReconciliation.matches.is_(False))
    return session.scalars(
        statement.order_by(models.InventoryReconciliation.record_index)
        .offset(offset)
        .limit(limit)
    ).all()


def list_stockout_risks(
    session: Session,
    *,
    run_id: UUID,
    severity: RiskSeverity | None,
    offset: int,
    limit: int,
) -> Sequence[models.StockoutRisk]:
    run = get_analytics_run(session, run_id)
    if run.run_type is not AnalyticsRunType.STOCKOUT_RISK:
        raise ResourceConflictError(
            f"Analytics run '{run_id}' is not a stockout-risk run."
        )
    statement = select(models.StockoutRisk).where(models.StockoutRisk.run_id == run_id)
    if severity is not None:
        statement = statement.where(models.StockoutRisk.severity == severity)
    return session.scalars(
        statement.order_by(models.StockoutRisk.record_index).offset(offset).limit(limit)
    ).all()


def _decimal(
    value: Decimal | float,
    *,
    quantum: Decimal = THREE_PLACES,
) -> Decimal:
    decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    return decimal_value.quantize(quantum, rounding=ROUND_HALF_UP)


def _commit(session: Session, conflict_message: str) -> None:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ResourceConflictError(conflict_message) from error
