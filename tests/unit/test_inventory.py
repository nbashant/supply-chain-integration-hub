from decimal import Decimal

import pytest

from supply_chain_hub.domain.exceptions import DomainValidationError
from supply_chain_hub.domain.inventory import calculate_available_quantity


def test_available_quantity_subtracts_reservations() -> None:
    result = calculate_available_quantity(Decimal("120"), Decimal("35"))

    assert result == Decimal("85")


def test_available_quantity_never_returns_a_negative_value() -> None:
    result = calculate_available_quantity(Decimal("10"), Decimal("15"))

    assert result == Decimal("0")


@pytest.mark.parametrize(
    ("on_hand", "reserved"),
    [
        (Decimal("-1"), Decimal("0")),
        (Decimal("1"), Decimal("-1")),
    ],
)
def test_available_quantity_rejects_negative_inputs(
    on_hand: Decimal,
    reserved: Decimal,
) -> None:
    with pytest.raises(DomainValidationError):
        calculate_available_quantity(on_hand, reserved)
