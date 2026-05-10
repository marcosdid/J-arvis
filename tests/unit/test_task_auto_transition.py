"""F5: auto-transition of task.state when start_session is called."""
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from orchestrator.core.sessions import (
    TaskInTerminalStateError,
    start_session,
)
from orchestrator.core.tasks import create_task, update_task
from orchestrator.sandbox.runtime import JailHandle
from orchestrator.store.models import Project, Repository


class FakeGitOps:
    async def add(self, repo: Path, target: Path, branch: str) -> None:
        target.mkdir(parents=True, exist_ok=True)
        (target / ".git").write_text("ref")

    async def remove(self, repo: Path, target: Path, *, force: bool = False) -> None:
        if target.exists():
            shutil.rmtree(target)

    async def list(self, repo: Path):
        return []


class FakeRuntime:
    async def spawn(self, cwd: Path, *, token=None, base_url=None) -> JailHandle:
        return JailHandle(id="fake", pid=1, started_at=datetime.now(UTC))

    async def kill(self, handle, *, worktree=None) -> None:
        pass


async def _seed_project(db_session, tmp_path: Path) -> str:
    base = tmp_path / "p"
    base.mkdir()
    p = Project(name="p", path=str(base))
    db_session.add(p)
    await db_session.flush()
    r = Repository(project_id=p.id, name="p", sub_path=".")
    db_session.add(r)
    await db_session.commit()
    return p.id


@pytest.fixture
async def setup(db_session, tmp_path: Path):
    pid = await _seed_project(db_session, tmp_path)
    return db_session, FakeRuntime(), FakeGitOps(), pid


@pytest.mark.parametrize("initial_state", ["idea", "ready", "review"])
async def test_start_session_auto_transitions_to_in_progress(setup, initial_state: str):
    db, runtime, git, pid = setup
    t = await create_task(db, project_id=pid, title="T")
    if initial_state == "ready":
        await update_task(db, t.id, state="ready")
    elif initial_state == "review":
        await update_task(db, t.id, state="ready")
        await update_task(db, t.id, state="in_progress")
        await update_task(db, t.id, state="review")
    await start_session(db, runtime, git, task_id=t.id)
    await db.refresh(t)
    assert t.state == "in_progress"


async def test_start_session_in_progress_is_noop(setup):
    db, runtime, git, pid = setup
    t = await create_task(db, project_id=pid, title="T")
    await update_task(db, t.id, state="ready")
    await update_task(db, t.id, state="in_progress")
    await start_session(db, runtime, git, task_id=t.id)
    await db.refresh(t)
    assert t.state == "in_progress"


@pytest.mark.parametrize("terminal_state", ["done", "discarded"])
async def test_start_session_in_terminal_state_raises(setup, terminal_state: str):
    db, runtime, git, pid = setup
    t = await create_task(db, project_id=pid, title="T")
    if terminal_state == "done":
        await update_task(db, t.id, state="ready")
        await update_task(db, t.id, state="in_progress")
        await update_task(db, t.id, state="review")
        await update_task(db, t.id, state="done")
    else:
        await update_task(db, t.id, state="discarded")
    with pytest.raises(TaskInTerminalStateError):
        await start_session(db, runtime, git, task_id=t.id)
