from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from supply_chain_hub.api.dependencies import DatabaseSession
from supply_chain_hub.api.schemas import ProductCreate, ProductResponse
from supply_chain_hub.application import services

router = APIRouter(prefix="/api/v1/products", tags=["products"])


@router.post(
    "",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
)
def create(
    request: ProductCreate,
    session: DatabaseSession,
) -> ProductResponse:
    return ProductResponse.model_validate(services.create_product(session, request))


@router.get("", response_model=list[ProductResponse])
def list_all(
    session: DatabaseSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[ProductResponse]:
    return [
        ProductResponse.model_validate(product)
        for product in services.list_products(
            session,
            offset=offset,
            limit=limit,
        )
    ]


@router.get("/{product_id}", response_model=ProductResponse)
def get_one(
    product_id: UUID,
    session: DatabaseSession,
) -> ProductResponse:
    return ProductResponse.model_validate(services.get_product(session, product_id))
