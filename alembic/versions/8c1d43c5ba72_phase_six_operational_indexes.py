"""phase six operational indexes

Revision ID: 8c1d43c5ba72
Revises: 473a65ae6903
Create Date: 2026-07-29 12:27:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "8c1d43c5ba72"
down_revision: str | None = "473a65ae6903"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the index used by expired worker-lease recovery."""
    op.create_index(
        "ix_import_jobs_status_lease",
        "import_jobs",
        ["status", "lease_expires_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove the expired worker-lease recovery index."""
    op.drop_index("ix_import_jobs_status_lease", table_name="import_jobs")
