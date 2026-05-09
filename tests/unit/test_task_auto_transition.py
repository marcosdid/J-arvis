from pathlib import Path

import pytest

from orchestrator.core.projects import create_project
from orchestrator.core.sessions import (
    TaskInTerminalStateError,
    start_session,
)
from orchestrator.core.tasks import create_task, update_task
from orchestrator.sandbox.null import NullSessionRuntime
from orchestrator.store.models import Worktree


async def _seed_pwt(db_session, tmp_path: Path, branch: str | None = "main"):
    """Seed Project + Worktree, return (project_id, worktree_id)."""
    repo = tmp_path / "r"
    repo.mkdir(exist_ok=True)
    (repo / ".git").mkdir(exist_ok=True)
    p = await create_project(db_session, "p", str(repo))
    w = Worktree(project_id=p.id, path=str(repo), branch=branch)
    db_session.add(w)
    await db_session.commit()
    await db_session.refresh(w)
    return p.id, w.id


@pytest.fixture
async def setup(db_session, tmp_path: Path):
    pid, wid = await _seed_pwt(db_session, tmp_path)
    runtime = NullSessionRuntime()
    return db_session, runtime, pid, wid


@pytest.mark.parametrize("initial_state", ["idea", "ready", "review"])
async def test_start_session_auto_transitions_to_in_progress(setup, initial_state: str):
    db, runtime, pid, wid = setup
    t = await create_task(db, project_id=pid, title="T")
    if initial_state == "ready":
        await update_task(db, t.id, state="ready")
    elif initial_state == "review":
        await update_task(db, t.id, state="ready")
        await update_task(db, t.id, state="in_progress")
        await update_task(db, t.id, state="review")
    await start_session(db, runtime, task_id=t.id, worktree_id=wid)
    await db.refresh(t)
    assert t.state == "in_progress"


async def test_start_session_in_progress_is_noop(setup):
    db, runtime, pid, wid = setup
    t = await create_task(db, project_id=pid, title="T")
    await update_task(db, t.id, state="ready")
    await update_task(db, t.id, state="in_progress")
    await start_session(db, runtime, task_id=t.id, worktree_id=wid)
    await db.refresh(t)
    assert t.state == "in_progress"


@pytest.mark.parametrize("terminal_state", ["done", "discarded"])
async def test_start_session_in_terminal_state_raises(setup, terminal_state: str):
    db, runtime, pid, wid = setup
    t = await create_task(db, project_id=pid, title="T")
    if terminal_state == "done":
        await update_task(db, t.id, state="ready")
        await update_task(db, t.id, state="in_progress")
        await update_task(db, t.id, state="review")
        await update_task(db, t.id, state="done")
    else:
        await update_task(db, t.id, state="discarded")
    with pytest.raises(TaskInTerminalStateError):
        await start_session(db, runtime, task_id=t.id, worktree_id=wid)
