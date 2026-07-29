from datetime import UTC

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from supply_chain_hub.domain.enums import ShipmentEventType
from supply_chain_hub.integrations.base import CanonicalShipmentEvent


class CarrierCEvent(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_id": "C-EVT-90871",
                "tracking_number": "C-123456",
                "event": "DELAYED",
                "event_time": "2026-07-29T14:32:11Z",
                "reason_code": "WEATHER",
            }
        }
    )

    event_id: str = Field(min_length=1, max_length=100)
    tracking_number: str = Field(min_length=1, max_length=100)
    event: ShipmentEventType
    event_time: AwareDatetime
    reason_code: str | None = Field(default=None, max_length=100)

    @field_validator("event", mode="before")
    @classmethod
    def normalize_event(cls, value: object) -> object:
        return value.lower() if isinstance(value, str) else value


class CarrierCAdapter:
    adapter_version = "carrier-c.shipment-events.v1"

    def adapt(self, payload: CarrierCEvent) -> CanonicalShipmentEvent:
        return CanonicalShipmentEvent(
            external_event_id=payload.event_id,
            tracking_reference=payload.tracking_number,
            event_type=payload.event,
            occurred_at=payload.event_time.astimezone(UTC),
            reason_code=payload.reason_code,
        )
