import pytest

from supply_chain_hub.domain.enums import ShipmentEventType, ShipmentStatus
from supply_chain_hub.domain.exceptions import DomainValidationError
from supply_chain_hub.domain.shipments import status_after_event


@pytest.mark.parametrize(
    ("current_status", "event_type", "expected_status"),
    [
        (
            ShipmentStatus.PLANNED,
            ShipmentEventType.PICKED_UP,
            ShipmentStatus.PICKED_UP,
        ),
        (
            ShipmentStatus.PICKED_UP,
            ShipmentEventType.IN_TRANSIT,
            ShipmentStatus.IN_TRANSIT,
        ),
        (
            ShipmentStatus.IN_TRANSIT,
            ShipmentEventType.DELAYED,
            ShipmentStatus.DELAYED,
        ),
        (
            ShipmentStatus.DELAYED,
            ShipmentEventType.IN_TRANSIT,
            ShipmentStatus.IN_TRANSIT,
        ),
        (
            ShipmentStatus.IN_TRANSIT,
            ShipmentEventType.DELIVERED,
            ShipmentStatus.DELIVERED,
        ),
    ],
)
def test_valid_shipment_event_transitions(
    current_status: ShipmentStatus,
    event_type: ShipmentEventType,
    expected_status: ShipmentStatus,
) -> None:
    assert status_after_event(current_status, event_type) is expected_status


@pytest.mark.parametrize(
    ("current_status", "event_type"),
    [
        (ShipmentStatus.PLANNED, ShipmentEventType.DELIVERED),
        (ShipmentStatus.DELIVERED, ShipmentEventType.IN_TRANSIT),
        (ShipmentStatus.CANCELLED, ShipmentEventType.PICKED_UP),
    ],
)
def test_invalid_shipment_event_transitions_are_rejected(
    current_status: ShipmentStatus,
    event_type: ShipmentEventType,
) -> None:
    with pytest.raises(DomainValidationError):
        status_after_event(current_status, event_type)
