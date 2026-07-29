from fastapi import APIRouter

from supply_chain_hub.api.dependencies import DatabaseSession
from supply_chain_hub.api.schemas import (
    ProductMappingResponse,
    ProductMappingUpsert,
    WarehouseMappingResponse,
    WarehouseMappingUpsert,
)
from supply_chain_hub.application import integration_services

router = APIRouter(
    prefix="/api/v1/integration-mappings",
    tags=["integration mappings"],
)


@router.put("/products", response_model=ProductMappingResponse)
def upsert_product(
    request: ProductMappingUpsert,
    session: DatabaseSession,
) -> ProductMappingResponse:
    mapping = integration_services.upsert_product_mapping(session, request)
    return ProductMappingResponse.model_validate(mapping)


@router.put("/warehouses", response_model=WarehouseMappingResponse)
def upsert_warehouse(
    request: WarehouseMappingUpsert,
    session: DatabaseSession,
) -> WarehouseMappingResponse:
    mapping = integration_services.upsert_warehouse_mapping(session, request)
    return WarehouseMappingResponse.model_validate(mapping)
