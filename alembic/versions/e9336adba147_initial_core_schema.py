"""initial_core_schema

Revision ID: e9336adba147
Revises:
Create Date: 2026-07-29 10:38:58.736580
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e9336adba147"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the schema change."""
    op.create_table(
        "products",
        sa.Column("sku", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "base_unit",
            sa.Enum(
                "EACH",
                "CASE",
                "PALLET",
                "KILOGRAM",
                name="unitofmeasure",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "inactive",
                name="recordstatus",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            server_default="active",
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_products")),
        sa.UniqueConstraint("sku", name=op.f("uq_products_sku")),
    )
    op.create_table(
        "suppliers",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "inactive",
                name="recordstatus",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            server_default="active",
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_suppliers")),
        sa.UniqueConstraint("code", name=op.f("uq_suppliers_code")),
    )
    op.create_table(
        "warehouses",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("timezone", sa.String(length=100), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "inactive",
                name="recordstatus",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            server_default="active",
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_warehouses")),
        sa.UniqueConstraint("code", name=op.f("uq_warehouses_code")),
    )
    op.create_table(
        "inventory_positions",
        sa.Column("warehouse_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column(
            "on_hand_quantity", sa.Numeric(precision=18, scale=3), nullable=False
        ),
        sa.Column(
            "reserved_quantity", sa.Numeric(precision=18, scale=3), nullable=False
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "on_hand_quantity >= 0",
            name=op.f("ck_inventory_positions_on_hand_quantity_nonnegative"),
        ),
        sa.CheckConstraint(
            "reserved_quantity >= 0",
            name=op.f("ck_inventory_positions_reserved_quantity_nonnegative"),
        ),
        sa.CheckConstraint(
            "version > 0", name=op.f("ck_inventory_positions_version_positive")
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_inventory_positions_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
            name=op.f("fk_inventory_positions_warehouse_id_warehouses"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inventory_positions")),
        sa.UniqueConstraint(
            "warehouse_id",
            "product_id",
            name="uq_inventory_positions_warehouse_product",
        ),
    )
    op.create_index(
        "ix_inventory_positions_product_warehouse",
        "inventory_positions",
        ["product_id", "warehouse_id"],
        unique=False,
    )
    op.create_table(
        "purchase_orders",
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("external_reference", sa.String(length=100), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "submitted",
                "partially_received",
                "received",
                "cancelled",
                name="purchaseorderstatus",
                native_enum=False,
                create_constraint=True,
                length=30,
            ),
            server_default="submitted",
            nullable=False,
        ),
        sa.Column(
            "order_date",
            sa.Date(),
            server_default=sa.text("CURRENT_DATE"),
            nullable=False,
        ),
        sa.Column("expected_date", sa.Date(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name=op.f("fk_purchase_orders_supplier_id_suppliers"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_purchase_orders")),
        sa.UniqueConstraint(
            "supplier_id",
            "external_reference",
            name="uq_purchase_orders_supplier_external_reference",
        ),
    )
    op.create_index(
        "ix_purchase_orders_supplier_status",
        "purchase_orders",
        ["supplier_id", "status"],
        unique=False,
    )
    op.create_table(
        "purchase_order_lines",
        sa.Column("purchase_order_id", sa.Uuid(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column(
            "ordered_quantity", sa.Numeric(precision=18, scale=3), nullable=False
        ),
        sa.Column(
            "received_quantity",
            sa.Numeric(precision=18, scale=3),
            server_default="0",
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "ordered_quantity > 0",
            name=op.f("ck_purchase_order_lines_ordered_quantity_positive"),
        ),
        sa.CheckConstraint(
            "received_quantity >= 0",
            name=op.f("ck_purchase_order_lines_received_quantity_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_purchase_order_lines_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["purchase_order_id"],
            ["purchase_orders.id"],
            name=op.f("fk_purchase_order_lines_purchase_order_id_purchase_orders"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_purchase_order_lines")),
        sa.UniqueConstraint(
            "purchase_order_id",
            "line_number",
            name="uq_purchase_order_lines_order_line_number",
        ),
        sa.UniqueConstraint(
            "purchase_order_id",
            "product_id",
            name="uq_purchase_order_lines_order_product",
        ),
    )
    op.create_table(
        "shipments",
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("purchase_order_id", sa.Uuid(), nullable=False),
        sa.Column("tracking_reference", sa.String(length=100), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "planned",
                "picked_up",
                "in_transit",
                "delayed",
                "delivered",
                "cancelled",
                name="shipmentstatus",
                native_enum=False,
                create_constraint=True,
                length=30,
            ),
            server_default="planned",
            nullable=False,
        ),
        sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["purchase_order_id"],
            ["purchase_orders.id"],
            name=op.f("fk_shipments_purchase_order_id_purchase_orders"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name=op.f("fk_shipments_supplier_id_suppliers"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shipments")),
        sa.UniqueConstraint(
            "supplier_id",
            "tracking_reference",
            name="uq_shipments_supplier_tracking_reference",
        ),
    )
    op.create_index(
        "ix_shipments_purchase_order_status",
        "shipments",
        ["purchase_order_id", "status"],
        unique=False,
    )
    op.create_table(
        "shipment_events",
        sa.Column("shipment_id", sa.Uuid(), nullable=False),
        sa.Column("external_event_id", sa.String(length=100), nullable=False),
        sa.Column(
            "event_type",
            sa.Enum(
                "picked_up",
                "in_transit",
                "delayed",
                "delivered",
                "cancelled",
                name="shipmenteventtype",
                native_enum=False,
                create_constraint=True,
                length=30,
            ),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason_code", sa.String(length=100), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["shipment_id"],
            ["shipments.id"],
            name=op.f("fk_shipment_events_shipment_id_shipments"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shipment_events")),
        sa.UniqueConstraint(
            "shipment_id",
            "external_event_id",
            name="uq_shipment_events_shipment_external_event",
        ),
    )
    op.create_index(
        "ix_shipment_events_shipment_occurred",
        "shipment_events",
        ["shipment_id", "occurred_at"],
        unique=False,
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Reverse the schema change."""
    op.drop_index("ix_shipment_events_shipment_occurred", table_name="shipment_events")
    op.drop_table("shipment_events")
    op.drop_index("ix_shipments_purchase_order_status", table_name="shipments")
    op.drop_table("shipments")
    op.drop_table("purchase_order_lines")
    op.drop_index("ix_purchase_orders_supplier_status", table_name="purchase_orders")
    op.drop_table("purchase_orders")
    op.drop_index(
        "ix_inventory_positions_product_warehouse", table_name="inventory_positions"
    )
    op.drop_table("inventory_positions")
    op.drop_table("warehouses")
    op.drop_table("suppliers")
    op.drop_table("products")
    # ### end Alembic commands ###
