from supply_chain_hub.domain.enums import ShipmentEventType, ShipmentStatus
from supply_chain_hub.domain.exceptions import DomainValidationError

_ALLOWED_TRANSITIONS: dict[
    ShipmentStatus,
    dict[ShipmentEventType, ShipmentStatus],
] = {
    ShipmentStatus.PLANNED: {
        ShipmentEventType.PICKED_UP: ShipmentStatus.PICKED_UP,
        ShipmentEventType.DELAYED: ShipmentStatus.DELAYED,
        ShipmentEventType.CANCELLED: ShipmentStatus.CANCELLED,
    },
    ShipmentStatus.PICKED_UP: {
        ShipmentEventType.IN_TRANSIT: ShipmentStatus.IN_TRANSIT,
        ShipmentEventType.DELAYED: ShipmentStatus.DELAYED,
        ShipmentEventType.DELIVERED: ShipmentStatus.DELIVERED,
        ShipmentEventType.CANCELLED: ShipmentStatus.CANCELLED,
    },
    ShipmentStatus.IN_TRANSIT: {
        ShipmentEventType.DELAYED: ShipmentStatus.DELAYED,
        ShipmentEventType.DELIVERED: ShipmentStatus.DELIVERED,
        ShipmentEventType.CANCELLED: ShipmentStatus.CANCELLED,
    },
    ShipmentStatus.DELAYED: {
        ShipmentEventType.IN_TRANSIT: ShipmentStatus.IN_TRANSIT,
        ShipmentEventType.DELIVERED: ShipmentStatus.DELIVERED,
        ShipmentEventType.CANCELLED: ShipmentStatus.CANCELLED,
    },
    ShipmentStatus.DELIVERED: {},
    ShipmentStatus.CANCELLED: {},
}


def status_after_event(
    current_status: ShipmentStatus,
    event_type: ShipmentEventType,
) -> ShipmentStatus:
    """Apply an event only when it is valid for the current lifecycle state."""
    next_status = _ALLOWED_TRANSITIONS[current_status].get(event_type)
    if next_status is None:
        raise DomainValidationError(
            f"Event '{event_type}' is invalid when a shipment is '{current_status}'."
        )
    return next_status
