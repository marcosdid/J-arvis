"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-08

"""
import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("path", sa.String(1024), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "worktrees",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("path", sa.String(1024), nullable=False, unique=True),
        sa.Column("branch", sa.String(255), nullable=True),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("worktree_id", sa.String(32), sa.ForeignKey("worktrees.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("pid", sa.Integer(), nullable=True),
        sa.Column("jail_id", sa.String(64), nullable=True),
        sa.Column("transcript_path", sa.String(1024), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("sessions")
    op.drop_table("worktrees")
    op.drop_table("projects")
