"""F5.d: branch clash -> git add fails -> rollback + raise."""
from pathlib import Path

import pytest
from sqlalchemy import select

from orchestrator.core.catalog import Catalog
from orchestrator.core.git import GitWorktreeError
from orchestrator.core.sessions import start_session
from orchestrator.store.database import Database
from orchestrator.store.models import Worktree
from tests.unit.test_session_start_atomic import (
    CollectingBroadcaster,
    FakeGitOps,
    FakeRuntime,
    _seed_multi_repo_project,
)


async def test_branch_clash_at_first_repo_rollbacks_clean(tmp_path: Path, catalog: Catalog) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/c.db")
    await db.bootstrap()
    git = FakeGitOps(fail_at=0)  # 1st add falha imediatamente
    bc = CollectingBroadcaster()

    async with db.session() as s:
        _, _, task = await _seed_multi_repo_project(s, tmp_path, ["backend", "frontend"])
        task_id = task.id

        with pytest.raises(GitWorktreeError):
            await start_session(
                s, FakeRuntime(), git, task_id=task_id, broadcaster=bc, catalog=catalog,
            )

        # No worktrees created
        assert len(git.added) == 0
        # Nothing in DB
        wts = (await s.execute(select(Worktree).where(Worktree.task_id == task_id))).scalars().all()
        assert len(wts) == 0
        # No broadcasts
        assert bc.received == []
