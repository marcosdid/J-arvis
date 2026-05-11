"""run_instances table for F6 (Run from Panel)

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-11
"""
import sqlalchemy as sa

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "run_instances",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "task_id",
            sa.String(32),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("cwd", sa.String(1024), nullable=False),
        sa.Column("manifest_path", sa.String(1024), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("ports_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("containers_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("network_name", sa.String(255), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    # Partial unique: at most 1 run active per task (ended_at IS NULL).
    op.create_index(
        "ix_run_instances_active_task",
        "run_instances",
        ["task_id"],
        unique=True,
        sqlite_where=sa.text("ended_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_run_instances_active_task", table_name="run_instances")
    op.drop_table("run_instances")
