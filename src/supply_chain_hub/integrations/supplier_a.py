from datetime import UTC
from decimal import Decimal
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from supply_chain_hub.domain.enums import UnitOfMeasure
from supply_chain_hub.integrations.base import (
    CanonicalInventoryRecord,
    InventoryAdapterResult,
)

NonNegativeQuantity = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=3)]


class SupplierAInventoryItem(BaseModel):
    item_number: str = Field(min_length=1, max_length=100)
    location: str = Field(min_length=1, max_length=100)
    on_hand: NonNegativeQuantity
    allocated: NonNegativeQuantity = Decimal("0")
    unit: UnitOfMeasure


class SupplierAInventoryPayload(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "snapshot_id": "SA-20260729-001",
                "captured_at": "2026-07-29T15:00:00Z",
                "items": [
                    {
                        "item_number": "A-IP16-256-BLK",
                        "location": "A-WEST-01",
                        "on_hand": "120.000",
                        "allocated": "35.000",
                        "unit": "EACH",
                    }
                ],
            }
        }
    )

    snapshot_id: str = Field(min_length=1, max_length=100)
    captured_at: AwareDatetime
    items: list[SupplierAInventoryItem] = Field(min_length=1, max_length=10_000)


class SupplierAInventoryAdapter:
    adapter_version = "supplier-a.inventory.v1"

    def adapt(self, payload: SupplierAInventoryPayload) -> InventoryAdapterResult:
        result = InventoryAdapterResult()
        observed_at = payload.captured_at.astimezone(UTC)
        for source_row, item in enumerate(payload.items, start=1):
            result.records.append(
                CanonicalInventoryRecord(
                    source_reference=payload.snapshot_id,
                    source_row=source_row,
                    external_sku=item.item_number,
                    external_location=item.location,
                    observed_at=observed_at,
                    source_unit=item.unit,
                    on_hand_quantity=item.on_hand,
                    reserved_quantity=item.allocated,
                    units_per_source_unit=None,
                    raw_fragment=item.model_dump(mode="json"),
                )
            )
        return result
