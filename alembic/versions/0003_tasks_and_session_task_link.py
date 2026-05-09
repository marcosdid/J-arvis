"""tasks + session.task_id

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-09
"""
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Pré-clean: remove sessions órfãs ANTES de adicionar task_id.
    # Sessions sem worktree existente não conseguem backfill (precisam
    # de project_id via JOIN com worktrees). DELETE silencioso —
    # justificativa: dados já corrompidos em DEV; em PROD futuro,
    # rever política via migration manual antes de subir.
    op.execute(
        "DELETE FROM sessions "
        "WHERE worktree_id NOT IN (SELECT id FROM worktrees)"
    )

    # Cria tabela tasks
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "project_id", sa.String(32),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("state", sa.String(32), nullable=False, server_default="idea"),
        sa.Column("template", sa.String(64), nullable=True),
        sa.Column("permission_profile", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # Adiciona task_id NULLABLE inicialmente (ainda nullable porque
    # vamos backfill antes de ALTER NOT NULL).
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.add_column(sa.Column("task_id", sa.String(32), nullable=True))
        batch_op.create_foreign_key(
            "fk_sessions_task_id",
            "tasks",
            ["task_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    # Backfill: pra cada session restante, cria task implícita
    conn = op.get_bind()
    sessions = conn.execute(sa.text(
        "SELECT s.id, s.worktree_id, w.project_id, w.branch "
        "FROM sessions s JOIN worktrees w ON s.worktree_id = w.id"
    )).fetchall()
    for sess in sessions:
        task_id = uuid4().hex
        now = datetime.now(UTC)
        conn.execute(sa.text(
            "INSERT INTO tasks "
            "(id, project_id, title, description, state, created_at, updated_at) "
            "VALUES (:id, :pid, :title, '', 'in_progress', :now, :now)"
        ), {
            "id": task_id, "pid": sess.project_id,
            "title": f"Quick session · {sess.branch or '(detached)'}",
            "now": now,
        })
        conn.execute(sa.text(
            "UPDATE sessions SET task_id = :tid WHERE id = :sid"
        ), {"tid": task_id, "sid": sess.id})

    # Final: NOT NULL agora que todas têm task_id
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.alter_column("task_id", nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.drop_column("task_id")
    op.drop_table("tasks")
