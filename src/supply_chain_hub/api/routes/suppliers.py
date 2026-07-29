from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from supply_chain_hub.api.dependencies import DatabaseSession
from supply_chain_hub.api.schemas import SupplierCreate, SupplierResponse
from supply_chain_hub.application import services

router = APIRouter(prefix="/api/v1/suppliers", tags=["suppliers"])


@router.post(
    "",
    response_model=SupplierResponse,
    status_code=status.HTTP_201_CREATED,
)
def create(
    request: SupplierCreate,
    session: DatabaseSession,
) -> SupplierResponse:
    return SupplierResponse.model_validate(services.create_supplier(session, request))


@router.get("", response_model=list[SupplierResponse])
def list_all(
    session: DatabaseSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[SupplierResponse]:
    return [
        SupplierResponse.model_validate(supplier)
        for supplier in services.list_suppliers(
            session,
            offset=offset,
            limit=limit,
        )
    ]


@router.get("/{supplier_id}", response_model=SupplierResponse)
def get_one(
    supplier_id: UUID,
    session: DatabaseSession,
) -> SupplierResponse:
    return SupplierResponse.model_validate(services.get_supplier(session, supplier_id))
