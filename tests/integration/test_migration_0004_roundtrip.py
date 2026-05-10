"""Migration 0004: tabela repositories + worktrees.repository_id/task_id +
sessions.cwd + tasks.branch.

Seed F4 (1 monorepo + 1 multi-repo project sem worktrees ainda) →
upgrade → asserts; downgrade → asserts (best-effort).
"""
from pathlib import Path

from alembic.command import downgrade, upgrade
from alembic.config import Config
from sqlalchemy import create_engine, text

from tests.integration.conftest import _make_multi_repo, _make_repo


def _alembic_cfg(db_url: str) -> Config:
    repo_root = Path(__file__).resolve().parents[2]
    cfg = Config(str(repo_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(repo_root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_upgrade_0003_to_0004_creates_repositories_and_migrates_worktrees(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "f4.db"
    db_url = f"sqlite:///{db_path}"
    cfg = _alembic_cfg(db_url)

    # Seed at F4 (revision 0003)
    upgrade(cfg, "0003")

    monorepo = _make_repo(tmp_path, "mono")
    multirepo_base = _make_multi_repo(tmp_path, ["backend", "frontend"], name="multi")

    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO projects (id, name, path, created_at) VALUES "
            "('p1','mono',:mp,'2026-01-01'),"
            "('p2','multi',:mr,'2026-01-01')"
        ), {"mp": str(monorepo), "mr": str(multirepo_base)})
        # F4 monorepo já tem worktree
        conn.execute(text(
            "INSERT INTO worktrees (id, project_id, path, branch) VALUES "
            "('w1','p1',:wp,'main')"
        ), {"wp": str(monorepo)})
        # Sessions com worktree_id
        conn.execute(text(
            "INSERT INTO tasks (id, project_id, title, description, state, created_at, updated_at) "
            "VALUES ('t1','p1','Mono task','','in_progress','2026-01-01','2026-01-01')"
        ))
        conn.execute(text(
            "INSERT INTO sessions (id, worktree_id, task_id, status, started_at) "
            "VALUES ('s1','w1','t1','executing','2026-01-01')"
        ))

    # Upgrade
    upgrade(cfg, "0004")

    with engine.begin() as conn:
        # repositories created
        repos = conn.execute(text("SELECT project_id, name, sub_path FROM repositories ORDER BY name")).all()
        assert len(repos) == 3  # mono(1) + multi(2)
        # mono → 1 row sub_path="."
        mono_repos = [r for r in repos if r.project_id == "p1"]
        assert len(mono_repos) == 1
        assert mono_repos[0].sub_path == "."
        # multi → 2 rows backend + frontend
        multi_repos = sorted(r.sub_path for r in repos if r.project_id == "p2")
        assert multi_repos == ["backend", "frontend"]

        # worktrees.repository_id populado (compare strings)
        wt_repo = conn.execute(text(
            "SELECT repository_id FROM worktrees WHERE id='w1'"
        )).scalar_one()
        mono_repo_id = conn.execute(text(
            "SELECT id FROM repositories WHERE project_id='p1'"
        )).scalar_one()
        assert wt_repo == mono_repo_id
        # worktree task_id is NULL (orphan no F4)
        wt_task = conn.execute(text("SELECT task_id FROM worktrees WHERE id='w1'")).scalar_one()
        assert wt_task is None
        # worktree.project_id NÃO existe mais
        cols = conn.execute(text("PRAGMA table_info(worktrees)")).all()
        names = {c.name for c in cols}
        assert "project_id" not in names
        assert "repository_id" in names
        assert "task_id" in names

        # sessions.cwd backfilled
        cwd = conn.execute(text("SELECT cwd FROM sessions WHERE id='s1'")).scalar_one()
        assert cwd == str(monorepo)
        # sessions.worktree_id NÃO existe mais
        cols_s = conn.execute(text("PRAGMA table_info(sessions)")).all()
        names_s = {c.name for c in cols_s}
        assert "worktree_id" not in names_s
        assert "cwd" in names_s

        # tasks.branch existe (NULL pra row legacy)
        cols_t = conn.execute(text("PRAGMA table_info(tasks)")).all()
        assert "branch" in {c.name for c in cols_t}


def test_downgrade_0004_to_0003_best_effort(tmp_path: Path) -> None:
    """Downgrade is lossy by design (multi-repo cwd doesn't map back).
    Roundtrip just needs to not crash and restore F4 schema shape."""
    db_path = tmp_path / "round.db"
    db_url = f"sqlite:///{db_path}"
    cfg = _alembic_cfg(db_url)

    upgrade(cfg, "0003")
    monorepo = _make_repo(tmp_path, "mono")
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO projects (id, name, path, created_at) VALUES "
            "('p1','mono',:mp,'2026-01-01')"
        ), {"mp": str(monorepo)})

    upgrade(cfg, "0004")
    downgrade(cfg, "0003")

    with engine.begin() as conn:
        # Schema F4 shape restored
        cols_w = conn.execute(text("PRAGMA table_info(worktrees)")).all()
        names_w = {c.name for c in cols_w}
        assert "project_id" in names_w
        assert "repository_id" not in names_w
        cols_s = conn.execute(text("PRAGMA table_info(sessions)")).all()
        names_s = {c.name for c in cols_s}
        assert "worktree_id" in names_s
        assert "cwd" not in names_s
