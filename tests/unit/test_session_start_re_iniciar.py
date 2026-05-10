"""F5.d: re-iniciar (2nd start_session for same task) reuses cwd
without calling git.add."""
from pathlib import Path

from orchestrator.core.sessions import start_session, stop_session
from orchestrator.store.database import Database
from tests.unit.test_session_start_atomic import (
    FakeGitOps,
    FakeRuntime,
    _seed_multi_repo_project,
)


async def test_re_iniciar_reuses_cwd_no_git_add(tmp_path: Path) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/r.db")
    await db.bootstrap()
    git = FakeGitOps()
    runtime = FakeRuntime()

    async with db.session() as s:
        _, _, task = await _seed_multi_repo_project(s, tmp_path, ["backend", "frontend"])

        # 1st session: creates worktrees
        first = await start_session(s, runtime, git, task_id=task.id)
        assert len(git.added) == 2
        first_cwd = Path(first.cwd)

        # Stop session
        await stop_session(s, runtime, first.id)

        # 2nd session: reuses cwd, no new git.add
        second = await start_session(s, runtime, git, task_id=task.id)
        assert len(git.added) == 2  # unchanged
        assert Path(second.cwd) == first_cwd
