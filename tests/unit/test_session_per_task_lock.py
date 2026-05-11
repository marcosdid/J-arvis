"""F5: per-task active session guard.

Uses FakeGitOps + FakeRuntime so tests don't shell out to git, exercising
the active-session bookkeeping path of start_session.
"""
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from orchestrator.core.catalog import Catalog
from orchestrator.core.sessions import (
    TaskAlreadyHasActiveSessionError,
    start_session,
    stop_session,
)
from orchestrator.core.tasks import create_task
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


async def _seed(db_session, tmp_path: Path) -> str:
    base = tmp_path / "p"
    base.mkdir()
    p = Project(name="p", path=str(base))
    db_session.add(p)
    await db_session.flush()
    r = Repository(project_id=p.id, name="p", sub_path=".")
    db_session.add(r)
    await db_session.commit()
    await db_session.refresh(p)
    return p.id


async def test_second_active_session_raises(db_session, tmp_path: Path, catalog: Catalog):
    pid = await _seed(db_session, tmp_path)
    t = await create_task(db_session, project_id=pid, title="T", catalog=catalog)
    await start_session(db_session, FakeRuntime(), FakeGitOps(), task_id=t.id)
    with pytest.raises(TaskAlreadyHasActiveSessionError):
        await start_session(db_session, FakeRuntime(), FakeGitOps(), task_id=t.id)


async def test_after_stop_can_start_again(db_session, tmp_path: Path, catalog: Catalog):
    pid = await _seed(db_session, tmp_path)
    t = await create_task(db_session, project_id=pid, title="T2", catalog=catalog)
    runtime = FakeRuntime()
    s1 = await start_session(db_session, runtime, FakeGitOps(), task_id=t.id)
    await stop_session(db_session, runtime, s1.id)
    await start_session(db_session, runtime, FakeGitOps(), task_id=t.id)
