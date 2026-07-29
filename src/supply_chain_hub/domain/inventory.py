from decimal import Decimal

from supply_chain_hub.domain.exceptions import DomainValidationError


def calculate_available_quantity(
    on_hand_quantity: Decimal,
    reserved_quantity: Decimal,
) -> Decimal:
    """Return usable inventory without allowing a negative availability."""
    if on_hand_quantity < 0:
        raise DomainValidationError("On-hand quantity cannot be negative.")
    if reserved_quantity < 0:
        raise DomainValidationError("Reserved quantity cannot be negative.")
    return max(on_hand_quantity - reserved_quantity, Decimal("0"))
