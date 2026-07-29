import numpy as np

from supply_chain_hub.analytics.types import (
    ForecastMetrics,
    RiskExecution,
    RiskInput,
    RiskThresholds,
    StockoutRiskResult,
)
from supply_chain_hub.domain.enums import RiskSeverity


def calculate_stockout_risks(records: list[RiskInput]) -> RiskExecution:
    if not records:
        raise ValueError("At least one risk input is required.")
    on_hand = np.asarray(
        [record.on_hand_quantity for record in records],
        dtype=np.float64,
    )
    reserved = np.asarray(
        [record.reserved_quantity for record in records],
        dtype=np.float64,
    )
    inbound = np.asarray(
        [record.inbound_quantity for record in records],
        dtype=np.float64,
    )
    forecast = np.asarray(
        [record.forecast_quantity for record in records],
        dtype=np.float64,
    )
    actual = np.asarray(
        [record.actual_demand_quantity for record in records],
        dtype=np.float64,
    )
    available = np.maximum(on_hand - reserved, 0.0)
    projected_ending = available + inbound - forecast
    shortage = np.maximum(-projected_ending, 0.0)
    shortage_ratio = np.divide(
        shortage,
        forecast,
        out=np.zeros_like(shortage),
        where=forecast > 0,
    )
    positive_ratios = shortage_ratio[shortage_ratio > 0]
    if positive_ratios.size:
        low_to_medium, medium_to_high = np.quantile(
            positive_ratios,
            [0.5, 0.8],
        )
    else:
        low_to_medium = medium_to_high = 0.0
    severity_values = np.select(
        [
            shortage_ratio == 0,
            shortage_ratio <= low_to_medium,
            shortage_ratio <= medium_to_high,
        ],
        [
            RiskSeverity.NONE.value,
            RiskSeverity.LOW.value,
            RiskSeverity.MEDIUM.value,
        ],
        default=RiskSeverity.HIGH.value,
    )
    results = [
        StockoutRiskResult(
            record_index=record.record_index,
            product_sku=record.product_sku,
            warehouse_code=record.warehouse_code,
            on_hand_quantity=float(on_hand[index]),
            reserved_quantity=float(reserved[index]),
            inbound_quantity=float(inbound[index]),
            forecast_quantity=float(forecast[index]),
            actual_demand_quantity=float(actual[index]),
            available_quantity=float(available[index]),
            projected_ending_quantity=float(projected_ending[index]),
            projected_shortage_quantity=float(shortage[index]),
            shortage_ratio=float(shortage_ratio[index]),
            severity=RiskSeverity(str(severity_values[index])),
        )
        for index, record in enumerate(records)
    ]
    return RiskExecution(
        results=results,
        forecast_metrics=calculate_forecast_metrics(forecast, actual),
        thresholds=RiskThresholds(
            low_to_medium=float(low_to_medium),
            medium_to_high=float(medium_to_high),
        ),
    )


def calculate_forecast_metrics(
    forecast: np.ndarray,
    actual: np.ndarray,
) -> ForecastMetrics:
    if forecast.shape != actual.shape or forecast.size == 0:
        raise ValueError("Forecast and actual arrays must have equal nonzero shape.")
    errors = forecast - actual
    absolute_errors = np.abs(errors)
    actual_total = float(np.abs(actual).sum())
    wape = float(absolute_errors.sum()) / actual_total if actual_total > 0 else 0.0
    return ForecastMetrics(
        mean_absolute_error=float(absolute_errors.mean()),
        root_mean_squared_error=float(np.sqrt(np.mean(np.square(errors)))),
        bias=float(errors.mean()),
        weighted_absolute_percentage_error=wape,
    )
