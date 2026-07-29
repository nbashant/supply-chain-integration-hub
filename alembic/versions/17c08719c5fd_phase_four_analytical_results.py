"""phase four analytical results

Revision ID: 17c08719c5fd
Revises: 5542092f7fd8
Create Date: 2026-07-29 11:34:43.767979
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "17c08719c5fd"
down_revision: str | None = "5542092f7fd8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the schema change."""
    op.create_table(
        "analytics_runs",
        sa.Column(
            "run_type",
            sa.Enum(
                "inventory_reconciliation",
                "stockout_risk",
                name="analyticsruntype",
                native_enum=False,
                create_constraint=True,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column(
            "engine",
            sa.Enum(
                "pandas",
                "polars",
                "numpy",
                name="analyticsengine",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("dataset_seed", sa.BigInteger(), nullable=False),
        sa.Column("input_rows", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Numeric(precision=18, scale=3), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "duration_ms >= 0", name=op.f("ck_analytics_runs_duration_ms_nonnegative")
        ),
        sa.CheckConstraint(
            "input_rows > 0", name=op.f("ck_analytics_runs_input_rows_positive")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analytics_runs")),
    )
    op.create_index(
        "ix_analytics_runs_type_created",
        "analytics_runs",
        ["run_type", "created_at"],
        unique=False,
    )
    op.create_table(
        "inventory_reconciliations",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("record_index", sa.Integer(), nullable=False),
        sa.Column("supplier_code", sa.String(length=100), nullable=False),
        sa.Column("product_sku", sa.String(length=100), nullable=False),
        sa.Column("warehouse_code", sa.String(length=100), nullable=False),
        sa.Column(
            "reported_quantity", sa.Numeric(precision=18, scale=3), nullable=False
        ),
        sa.Column("hub_quantity", sa.Numeric(precision=18, scale=3), nullable=False),
        sa.Column(
            "difference_quantity", sa.Numeric(precision=18, scale=3), nullable=False
        ),
        sa.Column("matches", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["analytics_runs.id"],
            name=op.f("fk_inventory_reconciliations_run_id_analytics_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inventory_reconciliations")),
        sa.UniqueConstraint(
            "run_id", "record_index", name="uq_inventory_reconciliations_run_record"
        ),
    )
    op.create_index(
        "ix_inventory_reconciliations_run_matches",
        "inventory_reconciliations",
        ["run_id", "matches"],
        unique=False,
    )
    op.create_table(
        "stockout_risks",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("record_index", sa.Integer(), nullable=False),
        sa.Column("product_sku", sa.String(length=100), nullable=False),
        sa.Column("warehouse_code", sa.String(length=100), nullable=False),
        sa.Column(
            "on_hand_quantity", sa.Numeric(precision=18, scale=3), nullable=False
        ),
        sa.Column(
            "reserved_quantity", sa.Numeric(precision=18, scale=3), nullable=False
        ),
        sa.Column(
            "inbound_quantity", sa.Numeric(precision=18, scale=3), nullable=False
        ),
        sa.Column(
            "forecast_quantity", sa.Numeric(precision=18, scale=3), nullable=False
        ),
        sa.Column(
            "actual_demand_quantity", sa.Numeric(precision=18, scale=3), nullable=False
        ),
        sa.Column(
            "available_quantity", sa.Numeric(precision=18, scale=3), nullable=False
        ),
        sa.Column(
            "projected_ending_quantity",
            sa.Numeric(precision=18, scale=3),
            nullable=False,
        ),
        sa.Column(
            "projected_shortage_quantity",
            sa.Numeric(precision=18, scale=3),
            nullable=False,
        ),
        sa.Column("shortage_ratio", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column(
            "severity",
            sa.Enum(
                "none",
                "low",
                "medium",
                "high",
                name="riskseverity",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "projected_shortage_quantity >= 0",
            name=op.f("ck_stockout_risks_projected_shortage_nonnegative"),
        ),
        sa.CheckConstraint(
            "shortage_ratio >= 0",
            name=op.f("ck_stockout_risks_shortage_ratio_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["analytics_runs.id"],
            name=op.f("fk_stockout_risks_run_id_analytics_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stockout_risks")),
        sa.UniqueConstraint(
            "run_id", "record_index", name="uq_stockout_risks_run_record"
        ),
    )
    op.create_index(
        "ix_stockout_risks_run_severity",
        "stockout_risks",
        ["run_id", "severity"],
        unique=False,
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Reverse the schema change."""
    op.drop_index("ix_stockout_risks_run_severity", table_name="stockout_risks")
    op.drop_table("stockout_risks")
    op.drop_index(
        "ix_inventory_reconciliations_run_matches",
        table_name="inventory_reconciliations",
    )
    op.drop_table("inventory_reconciliations")
    op.drop_index("ix_analytics_runs_type_created", table_name="analytics_runs")
    op.drop_table("analytics_runs")
    # ### end Alembic commands ###
