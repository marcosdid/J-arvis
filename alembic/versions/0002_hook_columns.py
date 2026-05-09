"""hook columns

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-09

"""
import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sessions") as batch:
        batch.add_column(sa.Column("hook_token", sa.String(32), nullable=True))
        batch.add_column(sa.Column("last_hook_at", sa.DateTime(), nullable=True))
        batch.create_index(
            "ix_sessions_hook_token",
            ["hook_token"],
            unique=True,
            sqlite_where=sa.text("hook_token IS NOT NULL"),
        )


def downgrade() -> None:
    with op.batch_alter_table("sessions") as batch:
        batch.drop_index("ix_sessions_hook_token")
        batch.drop_column("last_hook_at")
        batch.drop_column("hook_token")
