from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from supply_chain_hub.api.dependencies import DatabaseSession
from supply_chain_hub.api.schemas import (
    AnalyticsRunResponse,
    InventoryReconciliationResponse,
    ReconciliationRunCreate,
    StockoutRiskResponse,
    StockoutRiskRunCreate,
)
from supply_chain_hub.application import analytics_services
from supply_chain_hub.domain.enums import RiskSeverity

router = APIRouter(prefix="/api/v1", tags=["analytics"])

Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=1000)]


@router.post(
    "/analytics/reconciliations",
    response_model=AnalyticsRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_reconciliation_run(
    request: ReconciliationRunCreate,
    session: DatabaseSession,
) -> AnalyticsRunResponse:
    run = analytics_services.run_reconciliation(
        session,
        engine=request.engine,
        row_count=request.row_count,
        seed=request.seed,
    )
    return AnalyticsRunResponse.model_validate(run)


@router.get(
    "/reconciliations/inventory",
    response_model=list[InventoryReconciliationResponse],
)
def get_reconciliations(
    run_id: UUID,
    session: DatabaseSession,
    only_mismatches: bool = False,
    offset: Offset = 0,
    limit: Limit = 100,
) -> list[InventoryReconciliationResponse]:
    results = analytics_services.list_reconciliations(
        session,
        run_id=run_id,
        only_mismatches=only_mismatches,
        offset=offset,
        limit=limit,
    )
    return [
        InventoryReconciliationResponse.model_validate(result) for result in results
    ]


@router.post(
    "/analytics/stockout-risks",
    response_model=AnalyticsRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_stockout_risk_run(
    request: StockoutRiskRunCreate,
    session: DatabaseSession,
) -> AnalyticsRunResponse:
    run = analytics_services.run_stockout_risk(
        session,
        row_count=request.row_count,
        seed=request.seed,
    )
    return AnalyticsRunResponse.model_validate(run)


@router.get(
    "/risks/stockouts",
    response_model=list[StockoutRiskResponse],
)
def get_stockout_risks(
    run_id: UUID,
    session: DatabaseSession,
    severity: RiskSeverity | None = None,
    offset: Offset = 0,
    limit: Limit = 100,
) -> list[StockoutRiskResponse]:
    results = analytics_services.list_stockout_risks(
        session,
        run_id=run_id,
        severity=severity,
        offset=offset,
        limit=limit,
    )
    return [StockoutRiskResponse.model_validate(result) for result in results]
