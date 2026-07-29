import csv
import io
from datetime import UTC
from decimal import Decimal
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, Field, ValidationError

from supply_chain_hub.domain.enums import UnitOfMeasure
from supply_chain_hub.integrations.base import (
    AdapterError,
    CanonicalInventoryRecord,
    InventoryAdapterResult,
)

NonNegativeQuantity = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=3)]
PositiveQuantity = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=3)]

REQUIRED_HEADERS = {
    "snapshot_ref",
    "as_of",
    "partner_sku",
    "depot",
    "case_count",
    "units_per_case",
}


class SupplierBInventoryRow(BaseModel):
    snapshot_ref: str = Field(min_length=1, max_length=100)
    as_of: AwareDatetime
    partner_sku: str = Field(min_length=1, max_length=100)
    depot: str = Field(min_length=1, max_length=100)
    case_count: NonNegativeQuantity
    units_per_case: PositiveQuantity


class SupplierBInventoryAdapter:
    adapter_version = "supplier-b.inventory-csv.v1"

    def adapt(self, content: bytes) -> InventoryAdapterResult:
        result = InventoryAdapterResult()
        try:
            decoded = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            result.errors.append(
                AdapterError(
                    code="invalid_file_encoding",
                    message="Supplier B files must use UTF-8 encoding.",
                )
            )
            return result

        reader = csv.DictReader(io.StringIO(decoded))
        headers = set(reader.fieldnames or [])
        missing_headers = sorted(REQUIRED_HEADERS - headers)
        if missing_headers:
            result.errors.append(
                AdapterError(
                    code="missing_csv_headers",
                    message=(
                        "The CSV is missing required headers: "
                        + ", ".join(missing_headers)
                    ),
                )
            )
            return result

        for source_row, raw_row in enumerate(reader, start=2):
            clean_row = {
                key: value for key, value in raw_row.items() if key is not None
            }
            try:
                row = SupplierBInventoryRow.model_validate(clean_row)
            except ValidationError as error:
                for detail in error.errors():
                    field_name = ".".join(str(part) for part in detail["loc"])
                    result.errors.append(
                        AdapterError(
                            code="invalid_csv_field",
                            message=str(detail["msg"]),
                            source_row=source_row,
                            field_name=field_name,
                            raw_fragment=clean_row,
                        )
                    )
                continue

            observed_at = row.as_of.astimezone(UTC)
            result.records.append(
                CanonicalInventoryRecord(
                    source_reference=row.snapshot_ref,
                    source_row=source_row,
                    external_sku=row.partner_sku,
                    external_location=row.depot,
                    observed_at=observed_at,
                    source_unit=UnitOfMeasure.CASE,
                    on_hand_quantity=row.case_count,
                    reserved_quantity=Decimal("0"),
                    units_per_source_unit=row.units_per_case,
                    raw_fragment=clean_row,
                )
            )
        return result
