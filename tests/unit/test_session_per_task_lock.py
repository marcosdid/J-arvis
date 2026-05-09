from pathlib import Path

import pytest

from orchestrator.core.projects import create_project
from orchestrator.core.sessions import (
    TaskAlreadyHasActiveSessionError,
    start_session,
    stop_session,
)
from orchestrator.core.tasks import create_task
from orchestrator.sandbox.null import NullSessionRuntime
from orchestrator.store.models import Worktree


async def _seed_pwt(db_session, tmp_path: Path):
    repo = tmp_path / "r"
    repo.mkdir(exist_ok=True)
    (repo / ".git").mkdir(exist_ok=True)
    p = await create_project(db_session, "p", str(repo))
    w = Worktree(project_id=p.id, path=str(repo), branch="main")
    db_session.add(w)
    await db_session.commit()
    await db_session.refresh(w)
    return p.id, w.id


async def test_second_active_session_raises(db_session, tmp_path: Path):
    pid, wid = await _seed_pwt(db_session, tmp_path)
    t = await create_task(db_session, project_id=pid, title="T")
    runtime = NullSessionRuntime()
    await start_session(db_session, runtime, task_id=t.id, worktree_id=wid)
    with pytest.raises(TaskAlreadyHasActiveSessionError):
        await start_session(db_session, runtime, task_id=t.id, worktree_id=wid)


async def test_after_stop_can_start_again(db_session, tmp_path: Path):
    pid, wid = await _seed_pwt(db_session, tmp_path)
    t = await create_task(db_session, project_id=pid, title="T")
    runtime = NullSessionRuntime()
    s1 = await start_session(db_session, runtime, task_id=t.id, worktree_id=wid)
    await stop_session(db_session, runtime, s1.id)
    await start_session(db_session, runtime, task_id=t.id, worktree_id=wid)
