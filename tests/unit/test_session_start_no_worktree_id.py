"""F5.d: start_session signature drops worktree_id; legacy callers fail."""
from pathlib import Path

import pytest

from orchestrator.core.sessions import start_session
from orchestrator.store.database import Database
from tests.unit.test_session_start_atomic import (
    FakeGitOps,
    FakeRuntime,
    _seed_multi_repo_project,
)


async def test_start_session_rejects_worktree_id_kwarg(tmp_path: Path) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/n.db")
    await db.bootstrap()
    async with db.session() as s:
        _, _, task = await _seed_multi_repo_project(s, tmp_path, ["backend"])
        with pytest.raises(TypeError):
            await start_session(
                s, FakeRuntime(), FakeGitOps(),
                task_id=task.id,
                worktree_id="legacy-arg-not-allowed",
            )
