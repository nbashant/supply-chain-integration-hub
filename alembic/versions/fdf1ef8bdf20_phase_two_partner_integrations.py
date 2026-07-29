"""phase two partner integrations

Revision ID: fdf1ef8bdf20
Revises: e9336adba147
Create Date: 2026-07-29 10:58:07.904370
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "fdf1ef8bdf20"
down_revision: str | None = "e9336adba147"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the schema change."""
    op.create_table(
        "import_jobs",
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column(
            "source_type",
            sa.Enum(
                "supplier_a_json",
                "supplier_b_csv",
                name="importsourcetype",
                native_enum=False,
                create_constraint=True,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column("adapter_version", sa.String(length=100), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "processing",
                "completed",
                "completed_with_errors",
                "failed",
                name="importstatus",
                native_enum=False,
                create_constraint=True,
                length=40,
            ),
            server_default="processing",
            nullable=False,
        ),
        sa.Column("total_records", sa.Integer(), nullable=False),
        sa.Column("accepted_records", sa.Integer(), nullable=False),
        sa.Column("rejected_records", sa.Integer(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("fk_import_jobs_supplier_id_suppliers"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_jobs")),
    )
    op.create_index(
        "ix_import_jobs_supplier_created",
        "import_jobs",
        ["supplier_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "supplier_product_mappings",
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("external_sku", sa.String(length=100), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column(
            "source_unit",
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
            "units_per_source_unit",
            sa.Numeric(precision=18, scale=3),
            server_default="1",
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
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
            "units_per_source_unit > 0",
            name=op.f("ck_supplier_product_mappings_units_per_source_unit_positive"),
        ),
        sa.CheckConstraint(
            "version > 0", name=op.f("ck_supplier_product_mappings_version_positive")
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_supplier_product_mappings_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name=op.f("fk_supplier_product_mappings_supplier_id_suppliers"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplier_product_mappings")),
        sa.UniqueConstraint(
            "supplier_id",
            "external_sku",
            name="uq_supplier_product_mappings_supplier_external_sku",
        ),
    )
    op.create_index(
        "ix_supplier_product_mappings_supplier_active",
        "supplier_product_mappings",
        ["supplier_id", "active"],
        unique=False,
    )
    op.create_table(
        "supplier_warehouse_mappings",
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("external_location", sa.String(length=100), nullable=False),
        sa.Column("warehouse_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
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
            "version > 0", name=op.f("ck_supplier_warehouse_mappings_version_positive")
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name=op.f("fk_supplier_warehouse_mappings_supplier_id_suppliers"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
            name=op.f("fk_supplier_warehouse_mappings_warehouse_id_warehouses"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplier_warehouse_mappings")),
        sa.UniqueConstraint(
            "supplier_id",
            "external_location",
            name="uq_supplier_warehouse_mappings_supplier_external_location",
        ),
    )
    op.create_index(
        "ix_supplier_warehouse_mappings_supplier_active",
        "supplier_warehouse_mappings",
        ["supplier_id", "active"],
        unique=False,
    )
    op.create_table(
        "import_errors",
        sa.Column("import_job_id", sa.Uuid(), nullable=False),
        sa.Column("source_row", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=False),
        sa.Column("field_name", sa.String(length=100), nullable=True),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("raw_fragment", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["import_job_id"],
            ["import_jobs.id"],
            name=op.f("fk_import_errors_import_job_id_import_jobs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_errors")),
    )
    op.create_index(
        "ix_import_errors_job_row",
        "import_errors",
        ["import_job_id", "source_row"],
        unique=False,
    )
    op.create_table(
        "inventory_snapshots",
        sa.Column("import_job_id", sa.Uuid(), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("warehouse_id", sa.Uuid(), nullable=False),
        sa.Column("source_reference", sa.String(length=100), nullable=False),
        sa.Column("external_sku", sa.String(length=100), nullable=False),
        sa.Column("external_location", sa.String(length=100), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "on_hand_quantity", sa.Numeric(precision=18, scale=3), nullable=False
        ),
        sa.Column(
            "reserved_quantity", sa.Numeric(precision=18, scale=3), nullable=False
        ),
        sa.Column(
            "source_unit",
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
            "units_per_source_unit", sa.Numeric(precision=18, scale=3), nullable=False
        ),
        sa.Column("product_mapping_version", sa.Integer(), nullable=False),
        sa.Column("warehouse_mapping_version", sa.Integer(), nullable=False),
        sa.Column("source_row", sa.Integer(), nullable=False),
        sa.Column("raw_fragment", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "on_hand_quantity >= 0",
            name=op.f("ck_inventory_snapshots_on_hand_quantity_nonnegative"),
        ),
        sa.CheckConstraint(
            "reserved_quantity >= 0",
            name=op.f("ck_inventory_snapshots_reserved_quantity_nonnegative"),
        ),
        sa.CheckConstraint(
            "units_per_source_unit > 0",
            name=op.f("ck_inventory_snapshots_units_per_source_unit_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["import_job_id"],
            ["import_jobs.id"],
            name=op.f("fk_inventory_snapshots_import_job_id_import_jobs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_inventory_snapshots_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name=op.f("fk_inventory_snapshots_supplier_id_suppliers"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
            name=op.f("fk_inventory_snapshots_warehouse_id_warehouses"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inventory_snapshots")),
        sa.UniqueConstraint(
            "supplier_id",
            "source_reference",
            "external_sku",
            "external_location",
            name="uq_inventory_snapshots_source_record",
        ),
    )
    op.create_index(
        "ix_inventory_snapshots_product_warehouse_observed",
        "inventory_snapshots",
        ["product_id", "warehouse_id", "observed_at"],
        unique=False,
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Reverse the schema change."""
    op.drop_index(
        "ix_inventory_snapshots_product_warehouse_observed",
        table_name="inventory_snapshots",
    )
    op.drop_table("inventory_snapshots")
    op.drop_index("ix_import_errors_job_row", table_name="import_errors")
    op.drop_table("import_errors")
    op.drop_index(
        "ix_supplier_warehouse_mappings_supplier_active",
        table_name="supplier_warehouse_mappings",
    )
    op.drop_table("supplier_warehouse_mappings")
    op.drop_index(
        "ix_supplier_product_mappings_supplier_active",
        table_name="supplier_product_mappings",
    )
    op.drop_table("supplier_product_mappings")
    op.drop_index("ix_import_jobs_supplier_created", table_name="import_jobs")
    op.drop_table("import_jobs")
    # ### end Alembic commands ###
