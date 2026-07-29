"""phase seven learning-operation events

Revision ID: b81f2e7c4d93
Revises: 8c1d43c5ba72
Create Date: 2026-07-29 14:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b81f2e7c4d93"
down_revision: str | None = "8c1d43c5ba72"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Store safe, append-only evidence for the learning console."""
    op.add_column(
        "import_jobs",
        sa.Column("correlation_id", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "ix_import_jobs_correlation_id",
        "import_jobs",
        ["correlation_id"],
        unique=False,
    )
    op.create_table(
        "operation_events",
        sa.Column("import_job_id", sa.Uuid(), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=True),
        sa.Column("component", sa.String(length=50), nullable=False),
        sa.Column("stage", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("explanation", sa.String(length=1000), nullable=False),
        sa.Column("evidence_reference", sa.String(length=1000), nullable=True),
        sa.Column(
            "details",
            sa.JSON(),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["import_job_id"],
            ["import_jobs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_operation_events_job_occurred",
        "operation_events",
        ["import_job_id", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_operation_events_component_occurred",
        "operation_events",
        ["component", "occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove the Phase 7 learning evidence."""
    op.drop_index(
        "ix_operation_events_component_occurred",
        table_name="operation_events",
    )
    op.drop_index(
        "ix_operation_events_job_occurred",
        table_name="operation_events",
    )
    op.drop_table("operation_events")
    op.drop_index("ix_import_jobs_correlation_id", table_name="import_jobs")
    op.drop_column("import_jobs", "correlation_id")
