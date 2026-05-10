from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from orchestrator.core.sessions import start_session, stop_session
from orchestrator.core.tasks import create_task
from orchestrator.hooks.tokens import TokenRegistry
from orchestrator.store.database import Database
from orchestrator.store.models import Project, Repository, Worktree
from tests.integration.conftest import FakeSessionRuntime


@pytest.fixture
async def db(tmp_path: Path) -> AsyncIterator[Database]:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    await database.bootstrap()
    try:
        yield database
    finally:
        await database.close()


async def _seed_worktree(database: Database, worktree_path: str) -> tuple[str, str]:
    async with database.session() as s:
        proj = Project(name="p", path=worktree_path + "-proj")
        s.add(proj)
        await s.commit()
        await s.refresh(proj)
        repo = Repository(project_id=proj.id, name="p", sub_path=".")
        s.add(repo)
        await s.commit()
        await s.refresh(repo)
        wt = Worktree(
            repository_id=repo.id, task_id=None, path=worktree_path, branch="main",
        )
        s.add(wt)
        await s.commit()
        await s.refresh(wt)
        return wt.id, proj.id


@pytest.mark.asyncio
async def test_start_session_registers_token_when_registry_provided(db: Database) -> None:
    worktree_path = "/tmp/test-wt-start"
    worktree_id, project_id = await _seed_worktree(db, worktree_path)
    runtime = FakeSessionRuntime()
    registry = TokenRegistry()

    async with db.session() as s:
        t = await create_task(s, project_id=project_id, title="seed")
        row = await start_session(
            s,
            runtime,
            task_id=t.id,
            worktree_id=worktree_id,
            token_registry=registry,
            base_url="http://localhost:8000",
        )

    assert row.hook_token is not None
    assert registry.resolve(row.hook_token) == row.id


@pytest.mark.asyncio
async def test_stop_session_revokes_token_when_registry_provided(db: Database) -> None:
    worktree_path = "/tmp/test-wt-stop"
    worktree_id, project_id = await _seed_worktree(db, worktree_path)
    runtime = FakeSessionRuntime()
    registry = TokenRegistry()

    async with db.session() as s:
        t = await create_task(s, project_id=project_id, title="seed")
        row = await start_session(
            s,
            runtime,
            task_id=t.id,
            worktree_id=worktree_id,
            token_registry=registry,
            base_url="http://localhost:8000",
        )

    token = row.hook_token
    assert token is not None
    assert registry.resolve(token) == row.id

    async with db.session() as s:
        await stop_session(s, runtime, row.id, token_registry=registry)

    assert registry.resolve(token) is None
