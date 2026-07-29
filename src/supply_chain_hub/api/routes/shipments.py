from uuid import UUID

from fastapi import APIRouter, status

from supply_chain_hub.api.dependencies import DatabaseSession
from supply_chain_hub.api.schemas import (
    ShipmentCreate,
    ShipmentEventCreate,
    ShipmentResponse,
)
from supply_chain_hub.application import services

router = APIRouter(prefix="/api/v1/shipments", tags=["shipments"])


@router.post(
    "",
    response_model=ShipmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create(
    request: ShipmentCreate,
    session: DatabaseSession,
) -> ShipmentResponse:
    return ShipmentResponse.model_validate(services.create_shipment(session, request))


@router.post(
    "/{shipment_id}/events",
    response_model=ShipmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_event(
    shipment_id: UUID,
    request: ShipmentEventCreate,
    session: DatabaseSession,
) -> ShipmentResponse:
    return ShipmentResponse.model_validate(
        services.add_shipment_event(
            session,
            shipment_id=shipment_id,
            request=request,
        )
    )


@router.get("/{shipment_id}", response_model=ShipmentResponse)
def get_one(
    shipment_id: UUID,
    session: DatabaseSession,
) -> ShipmentResponse:
    return ShipmentResponse.model_validate(services.get_shipment(session, shipment_id))
