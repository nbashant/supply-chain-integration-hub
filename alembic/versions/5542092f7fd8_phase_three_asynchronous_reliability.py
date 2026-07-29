"""phase three asynchronous reliability

Revision ID: 5542092f7fd8
Revises: fdf1ef8bdf20
Create Date: 2026-07-29 11:14:01.019465
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "5542092f7fd8"
down_revision: str | None = "fdf1ef8bdf20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the schema change."""
    op.drop_constraint(
        op.f("ck_import_jobs_importstatus"),
        "import_jobs",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_import_jobs_importstatus"),
        "import_jobs",
        "status IN ('queued', 'processing', 'completed', "
        "'completed_with_errors', 'failed')",
    )
    op.alter_column(
        "import_jobs",
        "status",
        existing_type=sa.String(length=40),
        server_default="queued",
        existing_nullable=False,
    )
    op.create_table(
        "import_attempts",
        sa.Column("import_job_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "running",
                "succeeded",
                "retry_scheduled",
                "failed",
                "abandoned",
                name="importattemptstatus",
                native_enum=False,
                create_constraint=True,
                length=40,
            ),
            server_default="running",
            nullable=False,
        ),
        sa.Column("celery_task_id", sa.String(length=255), nullable=True),
        sa.Column("worker_id", sa.String(length=255), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("retryable", sa.Boolean(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "attempt_number > 0",
            name=op.f("ck_import_attempts_attempt_number_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["import_job_id"],
            ["import_jobs.id"],
            name=op.f("fk_import_attempts_import_job_id_import_jobs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_attempts")),
        sa.UniqueConstraint(
            "import_job_id",
            "attempt_number",
            name="uq_import_attempts_job_attempt_number",
        ),
    )
    op.create_index(
        "ix_import_attempts_job_started",
        "import_attempts",
        ["import_job_id", "started_at"],
        unique=False,
    )
    op.add_column(
        "import_jobs",
        sa.Column(
            "content_type",
            sa.String(length=100),
            server_default="application/octet-stream",
            nullable=False,
        ),
    )
    op.add_column("import_jobs", sa.Column("payload", sa.LargeBinary(), nullable=True))
    op.add_column(
        "import_jobs",
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "import_jobs",
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "import_jobs",
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
    )
    op.add_column(
        "import_jobs",
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "import_jobs",
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "import_jobs",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "import_jobs", sa.Column("worker_id", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "import_jobs", sa.Column("failure_code", sa.String(length=100), nullable=True)
    )
    op.add_column(
        "import_jobs",
        sa.Column("failure_message", sa.String(length=1000), nullable=True),
    )
    op.add_column(
        "import_jobs", sa.Column("last_error_retryable", sa.Boolean(), nullable=True)
    )
    op.add_column(
        "import_jobs", sa.Column("replay_of_job_id", sa.Uuid(), nullable=True)
    )
    op.alter_column(
        "import_jobs",
        "started_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        nullable=True,
        server_default=None,
        existing_server_default=sa.text("now()"),
    )
    op.create_index(
        "ix_import_jobs_status_retry",
        "import_jobs",
        ["status", "next_retry_at"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_import_jobs_supplier_source_idempotency",
        "import_jobs",
        ["supplier_id", "source_type", "idempotency_key"],
    )
    op.create_foreign_key(
        op.f("fk_import_jobs_replay_of_job_id_import_jobs"),
        "import_jobs",
        "import_jobs",
        ["replay_of_job_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Reverse the schema change."""
    op.drop_constraint(
        op.f("fk_import_jobs_replay_of_job_id_import_jobs"),
        "import_jobs",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_import_jobs_supplier_source_idempotency", "import_jobs", type_="unique"
    )
    op.drop_index("ix_import_jobs_status_retry", table_name="import_jobs")
    op.execute(
        "UPDATE import_jobs SET started_at = created_at WHERE started_at IS NULL"
    )
    op.alter_column(
        "import_jobs",
        "started_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
        existing_server_default=None,
    )
    op.drop_column("import_jobs", "replay_of_job_id")
    op.drop_column("import_jobs", "last_error_retryable")
    op.drop_column("import_jobs", "failure_message")
    op.drop_column("import_jobs", "failure_code")
    op.drop_column("import_jobs", "worker_id")
    op.drop_column("import_jobs", "lease_expires_at")
    op.drop_column("import_jobs", "next_retry_at")
    op.drop_column("import_jobs", "dispatched_at")
    op.drop_column("import_jobs", "max_attempts")
    op.drop_column("import_jobs", "attempt_count")
    op.drop_column("import_jobs", "idempotency_key")
    op.drop_column("import_jobs", "payload")
    op.drop_column("import_jobs", "content_type")
    op.drop_index("ix_import_attempts_job_started", table_name="import_attempts")
    op.drop_table("import_attempts")
    op.execute("UPDATE import_jobs SET status = 'failed' WHERE status = 'queued'")
    op.drop_constraint(
        op.f("ck_import_jobs_importstatus"),
        "import_jobs",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_import_jobs_importstatus"),
        "import_jobs",
        "status IN ('processing', 'completed', 'completed_with_errors', 'failed')",
    )
    op.alter_column(
        "import_jobs",
        "status",
        existing_type=sa.String(length=40),
        server_default="processing",
        existing_nullable=False,
    )
    # ### end Alembic commands ###
