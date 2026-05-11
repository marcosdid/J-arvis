"""F5.d: re-iniciar (2nd start_session for same task) reuses cwd
without calling git.add."""
from pathlib import Path

from orchestrator.core.catalog import Catalog
from orchestrator.core.sessions import start_session, stop_session
from orchestrator.store.database import Database
from tests.unit.test_session_start_atomic import (
    FakeGitOps,
    FakeRuntime,
    _seed_multi_repo_project,
)


async def test_re_iniciar_reuses_cwd_no_git_add(tmp_path: Path, catalog: Catalog) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/r.db")
    await db.bootstrap()
    git = FakeGitOps()
    runtime = FakeRuntime()

    async with db.session() as s:
        _, _, task = await _seed_multi_repo_project(s, tmp_path, ["backend", "frontend"])

        # 1st session: creates worktrees
        first = await start_session(s, runtime, git, task_id=task.id, catalog=catalog)
        assert len(git.added) == 2
        first_cwd = Path(first.cwd)

        # Stop session
        await stop_session(s, runtime, first.id)

        # 2nd session: reuses cwd, no new git.add
        second = await start_session(s, runtime, git, task_id=task.id, catalog=catalog)
        assert len(git.added) == 2  # unchanged
        assert Path(second.cwd) == first_cwd


async def test_re_iniciar_monorepo_reuses_single_worktree_path(
    tmp_path: Path, catalog: Catalog,
) -> None:
    """Monorepo case: 1 worktree -> cwd is the worktree path itself
    (no parent wrapping). Covers _derive_cwd_from_existing(len==1) branch.
    """
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/m.db")
    await db.bootstrap()
    git = FakeGitOps()
    runtime = FakeRuntime()

    async with db.session() as s:
        _, _, task = await _seed_multi_repo_project(s, tmp_path, ["mono"])
        # Only 1 sub-repo -> monorepo behaviour
        first = await start_session(s, runtime, git, task_id=task.id, catalog=catalog)
        first_cwd = Path(first.cwd)
        await stop_session(s, runtime, first.id)

        second = await start_session(s, runtime, git, task_id=task.id, catalog=catalog)
        # cwd is the same - and equal to the (only) worktree's path
        assert Path(second.cwd) == first_cwd
        # No new git.add (re-iniciar reuses existing)
        assert len(git.added) == 1
