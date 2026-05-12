"""master_session singleton

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-11
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "master_session",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("claude_session_id", sa.String(64), nullable=False),
        sa.Column("pid", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("last_active", sa.DateTime(), nullable=False),
        sa.CheckConstraint("id = 'singleton'", name="ck_master_singleton"),
    )


def downgrade() -> None:
    op.drop_table("master_session")
