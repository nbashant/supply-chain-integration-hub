from uuid import UUID

from fastapi import APIRouter, status

from supply_chain_hub.api.dependencies import DatabaseSession
from supply_chain_hub.api.schemas import (
    PurchaseOrderCreate,
    PurchaseOrderResponse,
)
from supply_chain_hub.application import services

router = APIRouter(prefix="/api/v1/purchase-orders", tags=["purchase orders"])


@router.post(
    "",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def create(
    request: PurchaseOrderCreate,
    session: DatabaseSession,
) -> PurchaseOrderResponse:
    return PurchaseOrderResponse.model_validate(
        services.create_purchase_order(session, request)
    )


@router.get("/{purchase_order_id}", response_model=PurchaseOrderResponse)
def get_one(
    purchase_order_id: UUID,
    session: DatabaseSession,
) -> PurchaseOrderResponse:
    return PurchaseOrderResponse.model_validate(
        services.get_purchase_order(session, purchase_order_id)
    )
