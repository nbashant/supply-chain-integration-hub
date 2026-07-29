from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from supply_chain_hub.api.dependencies import DatabaseSession
from supply_chain_hub.api.schemas import InventoryResponse, InventorySet
from supply_chain_hub.application import services
from supply_chain_hub.infrastructure.db.models import InventoryPosition

router = APIRouter(prefix="/api/v1/inventory", tags=["inventory"])


def _response(position: InventoryPosition) -> InventoryResponse:
    return InventoryResponse(
        id=position.id,
        warehouse_id=position.warehouse_id,
        product_id=position.product_id,
        on_hand_quantity=position.on_hand_quantity,
        reserved_quantity=position.reserved_quantity,
        available_quantity=services.available_quantity(position),
        version=position.version,
        created_at=position.created_at,
        updated_at=position.updated_at,
    )


@router.put(
    "/{warehouse_id}/{product_id}",
    response_model=InventoryResponse,
)
def set_position(
    warehouse_id: UUID,
    product_id: UUID,
    request: InventorySet,
    session: DatabaseSession,
) -> InventoryResponse:
    return _response(
        services.set_inventory(
            session,
            warehouse_id=warehouse_id,
            product_id=product_id,
            request=request,
        )
    )


@router.get("", response_model=list[InventoryResponse])
def list_all(
    session: DatabaseSession,
    warehouse_id: UUID | None = None,
    product_id: UUID | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[InventoryResponse]:
    return [
        _response(position)
        for position in services.list_inventory(
            session,
            warehouse_id=warehouse_id,
            product_id=product_id,
            offset=offset,
            limit=limit,
        )
    ]
