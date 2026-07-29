from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from supply_chain_hub.api.dependencies import DatabaseSession
from supply_chain_hub.api.schemas import WarehouseCreate, WarehouseResponse
from supply_chain_hub.application import services

router = APIRouter(prefix="/api/v1/warehouses", tags=["warehouses"])


@router.post(
    "",
    response_model=WarehouseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create(
    request: WarehouseCreate,
    session: DatabaseSession,
) -> WarehouseResponse:
    return WarehouseResponse.model_validate(services.create_warehouse(session, request))


@router.get("", response_model=list[WarehouseResponse])
def list_all(
    session: DatabaseSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[WarehouseResponse]:
    return [
        WarehouseResponse.model_validate(warehouse)
        for warehouse in services.list_warehouses(
            session,
            offset=offset,
            limit=limit,
        )
    ]


@router.get("/{warehouse_id}", response_model=WarehouseResponse)
def get_one(
    warehouse_id: UUID,
    session: DatabaseSession,
) -> WarehouseResponse:
    return WarehouseResponse.model_validate(
        services.get_warehouse(session, warehouse_id)
    )
