from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from supply_chain_hub.domain.enums import ShipmentEventType, UnitOfMeasure


@dataclass(frozen=True, slots=True)
class CanonicalInventoryRecord:
    source_reference: str
    source_row: int
    external_sku: str
    external_location: str
    observed_at: datetime
    source_unit: UnitOfMeasure
    on_hand_quantity: Decimal
    reserved_quantity: Decimal
    units_per_source_unit: Decimal | None
    raw_fragment: dict[str, object]


@dataclass(frozen=True, slots=True)
class AdapterError:
    code: str
    message: str
    source_row: int | None = None
    field_name: str | None = None
    raw_fragment: dict[str, object] | None = None


@dataclass(slots=True)
class InventoryAdapterResult:
    records: list[CanonicalInventoryRecord] = field(default_factory=list)
    errors: list[AdapterError] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class CanonicalShipmentEvent:
    external_event_id: str
    tracking_reference: str
    event_type: ShipmentEventType
    occurred_at: datetime
    reason_code: str | None
