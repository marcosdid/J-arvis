"""repositories + worktrees.repository_id/task_id + sessions.cwd + tasks.branch

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-09
"""
import logging
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _detect_repos_inline(base_path: str) -> list[tuple[str, str]]:
    """Inline copy of core/repositories.detect_repos for migration use.
    Returns list of (name, sub_path)."""
    base = Path(base_path)
    if not base.is_dir():
        return []
    if (base / ".git").is_dir():
        return [(base.name, ".")]
    sub = sorted(
        c.name for c in base.iterdir()
        if c.is_dir() and (c / ".git").is_dir()
    )
    return [(s, s) for s in sub]


def upgrade() -> None:
    # 1. Create repositories table
    op.create_table(
        "repositories",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "project_id", sa.String(32),
            sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("sub_path", sa.String(1024), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("project_id", "sub_path", name="uq_repo_project_subpath"),
    )

    # 2. Backfill: pra cada Project, detectar repos + insert
    bind = op.get_bind()
    projects = bind.execute(sa.text("SELECT id, name, path FROM projects")).all()
    now = datetime.now(UTC)
    _mig_log = logging.getLogger("alembic.runtime.migration")
    for proj in projects:
        repos = _detect_repos_inline(proj.path)
        if not repos:
            _mig_log.warning(
                "project '%s' (id=%s) at path '%s' has no .git — fallback to "
                "1 dummy repository row (sub_path='.'). User should reconcile "
                "after migration.",
                proj.name, proj.id, proj.path,
            )
            repos = [(proj.name, ".")]
        for name, sub_path in repos:
            rid = uuid4().hex
            bind.execute(sa.text(
                "INSERT INTO repositories (id, project_id, name, sub_path, created_at) "
                "VALUES (:id, :pid, :name, :sub, :ts)"
            ), {"id": rid, "pid": proj.id, "name": name, "sub": sub_path, "ts": now})

    # 3. ALTER worktrees: add repository_id + task_id (nullable inicialmente)
    with op.batch_alter_table("worktrees") as batch:
        batch.add_column(sa.Column("repository_id", sa.String(32), nullable=True))
        batch.add_column(sa.Column("task_id", sa.String(32), nullable=True))

    # 4. Backfill worktrees.repository_id (F4 schema só tem monorepo: 1 project = 1 repo row)
    bind.execute(sa.text(
        "UPDATE worktrees SET repository_id = ("
        "  SELECT r.id FROM repositories r "
        "  WHERE r.project_id = worktrees.project_id LIMIT 1"
        ")"
    ))

    # 5. ALTER worktrees: NOT NULL + FKs + drop project_id
    with op.batch_alter_table("worktrees") as batch:
        batch.alter_column("repository_id", existing_type=sa.String(32), nullable=False)
        batch.create_foreign_key(
            "fk_wt_repository", "repositories", ["repository_id"], ["id"],
            ondelete="CASCADE",
        )
        batch.create_foreign_key(
            "fk_wt_task", "tasks", ["task_id"], ["id"], ondelete="SET NULL",
        )
        batch.drop_column("project_id")

    # 6. ALTER tasks: add branch
    with op.batch_alter_table("tasks") as batch:
        batch.add_column(sa.Column("branch", sa.String(255), nullable=True))

    # 7. ALTER sessions: add cwd (nullable)
    with op.batch_alter_table("sessions") as batch:
        batch.add_column(sa.Column("cwd", sa.String(1024), nullable=True))

    # 8. Backfill sessions.cwd
    bind.execute(sa.text(
        "UPDATE sessions SET cwd = ("
        "  SELECT path FROM worktrees WHERE worktrees.id = sessions.worktree_id"
        ")"
    ))

    # 9. ALTER sessions: NOT NULL + drop worktree_id
    with op.batch_alter_table("sessions") as batch:
        batch.alter_column("cwd", existing_type=sa.String(1024), nullable=False)
        batch.drop_column("worktree_id")


def downgrade() -> None:
    """Best-effort downgrade. Multi-repo data is lossy:
    sessions of multi-repo tasks (cwd is parent of N worktrees) cannot
    be perfectly mapped to a single worktree_id. Picks any worktree
    of the same task as fallback.
    """
    bind = op.get_bind()

    with op.batch_alter_table("sessions") as batch:
        batch.add_column(sa.Column("worktree_id", sa.String(32), nullable=True))

    bind.execute(sa.text(
        "UPDATE sessions SET worktree_id = ("
        "  SELECT id FROM worktrees WHERE task_id = sessions.task_id LIMIT 1"
        ")"
    ))

    with op.batch_alter_table("sessions") as batch:
        batch.create_foreign_key(
            "fk_sess_wt", "worktrees", ["worktree_id"], ["id"], ondelete="RESTRICT",
        )
        batch.alter_column("worktree_id", nullable=False)
        batch.drop_column("cwd")

    with op.batch_alter_table("tasks") as batch:
        batch.drop_column("branch")

    with op.batch_alter_table("worktrees") as batch:
        batch.add_column(sa.Column("project_id", sa.String(32), nullable=True))

    bind.execute(sa.text(
        "UPDATE worktrees SET project_id = ("
        "  SELECT project_id FROM repositories WHERE repositories.id = worktrees.repository_id"
        ")"
    ))

    with op.batch_alter_table("worktrees") as batch:
        batch.alter_column("project_id", nullable=False)
        batch.drop_constraint("fk_wt_repository", type_="foreignkey")
        batch.drop_constraint("fk_wt_task", type_="foreignkey")
        batch.create_foreign_key(
            "fk_wt_project", "projects", ["project_id"], ["id"], ondelete="RESTRICT",
        )
        batch.drop_column("repository_id")
        batch.drop_column("task_id")

    op.drop_table("repositories")
