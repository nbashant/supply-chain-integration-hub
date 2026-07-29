from collections.abc import Sequence
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from supply_chain_hub.api.schemas import (
    InventorySet,
    ProductCreate,
    PurchaseOrderCreate,
    ShipmentCreate,
    ShipmentEventCreate,
    SupplierCreate,
    WarehouseCreate,
)
from supply_chain_hub.domain.enums import ShipmentEventType
from supply_chain_hub.domain.exceptions import (
    ResourceConflictError,
    ResourceNotFoundError,
)
from supply_chain_hub.domain.inventory import calculate_available_quantity
from supply_chain_hub.domain.shipments import status_after_event
from supply_chain_hub.infrastructure.db import models


def _commit(session: Session, conflict_message: str) -> None:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ResourceConflictError(conflict_message) from error


def _list(
    session: Session,
    statement: Select[tuple[models.Supplier]]
    | Select[tuple[models.Product]]
    | Select[tuple[models.Warehouse]]
    | Select[tuple[models.InventoryPosition]],
) -> Sequence[
    models.Supplier | models.Product | models.Warehouse | models.InventoryPosition
]:
    return session.scalars(statement).all()


def create_supplier(session: Session, request: SupplierCreate) -> models.Supplier:
    supplier = models.Supplier(code=request.code, name=request.name)
    session.add(supplier)
    _commit(session, f"Supplier code '{request.code}' already exists.")
    session.refresh(supplier)
    return supplier


def list_suppliers(
    session: Session,
    *,
    offset: int,
    limit: int,
) -> Sequence[models.Supplier]:
    statement = select(models.Supplier).order_by(models.Supplier.code).offset(offset)
    return session.scalars(statement.limit(limit)).all()


def get_supplier(session: Session, supplier_id: UUID) -> models.Supplier:
    supplier = session.get(models.Supplier, supplier_id)
    if supplier is None:
        raise ResourceNotFoundError(f"Supplier '{supplier_id}' was not found.")
    return supplier


def create_product(session: Session, request: ProductCreate) -> models.Product:
    product = models.Product(
        sku=request.sku,
        name=request.name,
        base_unit=request.base_unit,
    )
    session.add(product)
    _commit(session, f"Product SKU '{request.sku}' already exists.")
    session.refresh(product)
    return product


def list_products(
    session: Session,
    *,
    offset: int,
    limit: int,
) -> Sequence[models.Product]:
    statement = select(models.Product).order_by(models.Product.sku).offset(offset)
    return session.scalars(statement.limit(limit)).all()


def get_product(session: Session, product_id: UUID) -> models.Product:
    product = session.get(models.Product, product_id)
    if product is None:
        raise ResourceNotFoundError(f"Product '{product_id}' was not found.")
    return product


def create_warehouse(
    session: Session,
    request: WarehouseCreate,
) -> models.Warehouse:
    warehouse = models.Warehouse(
        code=request.code,
        name=request.name,
        timezone=request.timezone,
    )
    session.add(warehouse)
    _commit(session, f"Warehouse code '{request.code}' already exists.")
    session.refresh(warehouse)
    return warehouse


def list_warehouses(
    session: Session,
    *,
    offset: int,
    limit: int,
) -> Sequence[models.Warehouse]:
    statement = select(models.Warehouse).order_by(models.Warehouse.code).offset(offset)
    return session.scalars(statement.limit(limit)).all()


def get_warehouse(session: Session, warehouse_id: UUID) -> models.Warehouse:
    warehouse = session.get(models.Warehouse, warehouse_id)
    if warehouse is None:
        raise ResourceNotFoundError(f"Warehouse '{warehouse_id}' was not found.")
    return warehouse


def set_inventory(
    session: Session,
    *,
    warehouse_id: UUID,
    product_id: UUID,
    request: InventorySet,
) -> models.InventoryPosition:
    get_warehouse(session, warehouse_id)
    get_product(session, product_id)
    calculate_available_quantity(
        request.on_hand_quantity,
        request.reserved_quantity,
    )

    statement = select(models.InventoryPosition).where(
        models.InventoryPosition.warehouse_id == warehouse_id,
        models.InventoryPosition.product_id == product_id,
    )
    position = session.scalar(statement)
    if position is None:
        position = models.InventoryPosition(
            warehouse_id=warehouse_id,
            product_id=product_id,
            on_hand_quantity=request.on_hand_quantity,
            reserved_quantity=request.reserved_quantity,
        )
        session.add(position)
    else:
        position.on_hand_quantity = request.on_hand_quantity
        position.reserved_quantity = request.reserved_quantity
        position.version += 1

    _commit(session, "The inventory position conflicts with an existing record.")
    session.refresh(position)
    return position


def list_inventory(
    session: Session,
    *,
    warehouse_id: UUID | None,
    product_id: UUID | None,
    offset: int,
    limit: int,
) -> Sequence[models.InventoryPosition]:
    statement = select(models.InventoryPosition)
    if warehouse_id is not None:
        statement = statement.where(
            models.InventoryPosition.warehouse_id == warehouse_id
        )
    if product_id is not None:
        statement = statement.where(models.InventoryPosition.product_id == product_id)
    statement = statement.order_by(
        models.InventoryPosition.warehouse_id,
        models.InventoryPosition.product_id,
    )
    return session.scalars(statement.offset(offset).limit(limit)).all()


def available_quantity(position: models.InventoryPosition) -> Decimal:
    return calculate_available_quantity(
        position.on_hand_quantity,
        position.reserved_quantity,
    )


def create_purchase_order(
    session: Session,
    request: PurchaseOrderCreate,
) -> models.PurchaseOrder:
    get_supplier(session, request.supplier_id)

    product_ids = [line.product_id for line in request.lines]
    if len(product_ids) != len(set(product_ids)):
        raise ResourceConflictError(
            "A product may appear only once in a purchase order."
        )

    products = session.scalars(
        select(models.Product).where(models.Product.id.in_(product_ids))
    ).all()
    found_product_ids = {product.id for product in products}
    missing_product_ids = set(product_ids) - found_product_ids
    if missing_product_ids:
        missing = ", ".join(str(product_id) for product_id in missing_product_ids)
        raise ResourceNotFoundError(f"Products were not found: {missing}.")

    purchase_order = models.PurchaseOrder(
        supplier_id=request.supplier_id,
        external_reference=request.external_reference,
        expected_date=request.expected_date,
        lines=[
            models.PurchaseOrderLine(
                line_number=line_number,
                product_id=line.product_id,
                ordered_quantity=line.ordered_quantity,
            )
            for line_number, line in enumerate(request.lines, start=1)
        ],
    )
    session.add(purchase_order)
    _commit(
        session,
        "This supplier already has a purchase order with external reference "
        f"'{request.external_reference}'.",
    )
    return get_purchase_order(session, purchase_order.id)


def get_purchase_order(
    session: Session,
    purchase_order_id: UUID,
) -> models.PurchaseOrder:
    statement = (
        select(models.PurchaseOrder)
        .options(selectinload(models.PurchaseOrder.lines))
        .where(models.PurchaseOrder.id == purchase_order_id)
    )
    purchase_order = session.scalar(statement)
    if purchase_order is None:
        raise ResourceNotFoundError(
            f"Purchase order '{purchase_order_id}' was not found."
        )
    return purchase_order


def create_shipment(
    session: Session,
    request: ShipmentCreate,
) -> models.Shipment:
    get_supplier(session, request.supplier_id)
    purchase_order = get_purchase_order(session, request.purchase_order_id)
    if purchase_order.supplier_id != request.supplier_id:
        raise ResourceConflictError(
            "The shipment supplier must match the purchase-order supplier."
        )

    shipment = models.Shipment(
        supplier_id=request.supplier_id,
        purchase_order_id=request.purchase_order_id,
        tracking_reference=request.tracking_reference,
        shipped_at=request.shipped_at,
    )
    session.add(shipment)
    _commit(
        session,
        "This supplier already has a shipment with tracking reference "
        f"'{request.tracking_reference}'.",
    )
    return get_shipment(session, shipment.id)


def get_shipment(session: Session, shipment_id: UUID) -> models.Shipment:
    statement = (
        select(models.Shipment)
        .options(selectinload(models.Shipment.events))
        .where(models.Shipment.id == shipment_id)
    )
    shipment = session.scalar(statement)
    if shipment is None:
        raise ResourceNotFoundError(f"Shipment '{shipment_id}' was not found.")
    return shipment


def add_shipment_event(
    session: Session,
    *,
    shipment_id: UUID,
    request: ShipmentEventCreate,
) -> models.Shipment:
    shipment = get_shipment(session, shipment_id)

    duplicate_statement = select(models.ShipmentEvent.id).where(
        models.ShipmentEvent.shipment_id == shipment_id,
        models.ShipmentEvent.external_event_id == request.external_event_id,
    )
    if session.scalar(duplicate_statement) is not None:
        raise ResourceConflictError(
            f"Shipment event '{request.external_event_id}' already exists."
        )

    shipment.status = status_after_event(shipment.status, request.event_type)
    if (
        request.event_type is ShipmentEventType.PICKED_UP
        and shipment.shipped_at is None
    ):
        shipment.shipped_at = request.occurred_at
    if request.event_type is ShipmentEventType.DELIVERED:
        shipment.delivered_at = request.occurred_at

    event = models.ShipmentEvent(
        shipment_id=shipment_id,
        external_event_id=request.external_event_id,
        event_type=request.event_type,
        occurred_at=request.occurred_at,
        reason_code=request.reason_code,
    )
    session.add(event)
    _commit(
        session,
        f"Shipment event '{request.external_event_id}' already exists.",
    )
    session.expire(shipment, ["events"])
    return get_shipment(session, shipment_id)
