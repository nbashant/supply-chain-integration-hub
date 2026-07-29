"""phase five object storage references

Revision ID: 473a65ae6903
Revises: 17c08719c5fd
Create Date: 2026-07-29 12:07:24.382252
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "473a65ae6903"
down_revision: str | None = "17c08719c5fd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the schema change."""
    op.add_column(
        "import_jobs",
        sa.Column("payload_object_key", sa.String(length=1000), nullable=True),
    )
    op.add_column(
        "import_jobs",
        sa.Column("payload_size_bytes", sa.BigInteger(), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_import_jobs_payload_size_nonnegative"),
        "import_jobs",
        "payload_size_bytes IS NULL OR payload_size_bytes >= 0",
    )
    op.create_index(
        "ix_import_jobs_payload_object_key",
        "import_jobs",
        ["payload_object_key"],
        unique=False,
    )


def downgrade() -> None:
    """Reverse the schema change."""
    op.drop_index("ix_import_jobs_payload_object_key", table_name="import_jobs")
    op.drop_constraint(
        op.f("ck_import_jobs_payload_size_nonnegative"),
        "import_jobs",
        type_="check",
    )
    op.drop_column("import_jobs", "payload_size_bytes")
    op.drop_column("import_jobs", "payload_object_key")
