from dataclasses import dataclass

from supply_chain_hub.domain.enums import RiskSeverity


@dataclass(frozen=True, slots=True)
class SupplierInventoryRow:
    record_index: int
    supplier_code: str
    product_sku: str
    warehouse_code: str
    reported_quantity: int


@dataclass(frozen=True, slots=True)
class HubInventoryRow:
    record_index: int
    product_sku: str
    warehouse_code: str
    hub_quantity: int


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    record_index: int
    supplier_code: str
    product_sku: str
    warehouse_code: str
    reported_quantity: int
    hub_quantity: int
    difference_quantity: int
    matches: bool


@dataclass(frozen=True, slots=True)
class ReconciliationExecution:
    results: list[ReconciliationResult]
    dataframe_bytes: int


@dataclass(frozen=True, slots=True)
class RiskInput:
    record_index: int
    product_sku: str
    warehouse_code: str
    on_hand_quantity: float
    reserved_quantity: float
    inbound_quantity: float
    forecast_quantity: float
    actual_demand_quantity: float


@dataclass(frozen=True, slots=True)
class StockoutRiskResult:
    record_index: int
    product_sku: str
    warehouse_code: str
    on_hand_quantity: float
    reserved_quantity: float
    inbound_quantity: float
    forecast_quantity: float
    actual_demand_quantity: float
    available_quantity: float
    projected_ending_quantity: float
    projected_shortage_quantity: float
    shortage_ratio: float
    severity: RiskSeverity


@dataclass(frozen=True, slots=True)
class ForecastMetrics:
    mean_absolute_error: float
    root_mean_squared_error: float
    bias: float
    weighted_absolute_percentage_error: float


@dataclass(frozen=True, slots=True)
class RiskThresholds:
    low_to_medium: float
    medium_to_high: float


@dataclass(frozen=True, slots=True)
class RiskExecution:
    results: list[StockoutRiskResult]
    forecast_metrics: ForecastMetrics
    thresholds: RiskThresholds
