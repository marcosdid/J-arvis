"""F5: token registration / revocation lifecycle around start_session/stop_session."""
import shutil
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from orchestrator.core.sessions import start_session, stop_session
from orchestrator.core.tasks import create_task
from orchestrator.hooks.tokens import TokenRegistry
from orchestrator.sandbox.runtime import JailHandle
from orchestrator.store.database import Database
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


@pytest.fixture
async def db(tmp_path: Path) -> AsyncIterator[Database]:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    await database.bootstrap()
    try:
        yield database
    finally:
        await database.close()


async def _seed_project(db: Database, tmp_path: Path) -> str:
    base = tmp_path / "p"
    base.mkdir()
    async with db.session() as s:
        p = Project(name="p", path=str(base))
        s.add(p)
        await s.flush()
        r = Repository(project_id=p.id, name="p", sub_path=".")
        s.add(r)
        await s.commit()
        return p.id


@pytest.mark.asyncio
async def test_start_session_registers_token_when_registry_provided(
    db: Database, tmp_path: Path,
) -> None:
    pid = await _seed_project(db, tmp_path)
    registry = TokenRegistry()

    async with db.session() as s:
        t = await create_task(s, project_id=pid, title="seed")
        row = await start_session(
            s, FakeRuntime(), FakeGitOps(),
            task_id=t.id,
            token_registry=registry,
            base_url="http://localhost:8000",
        )

    assert row.hook_token is not None
    assert registry.resolve(row.hook_token) == row.id


@pytest.mark.asyncio
async def test_stop_session_revokes_token_when_registry_provided(
    db: Database, tmp_path: Path,
) -> None:
    pid = await _seed_project(db, tmp_path)
    registry = TokenRegistry()
    runtime = FakeRuntime()

    async with db.session() as s:
        t = await create_task(s, project_id=pid, title="seed")
        row = await start_session(
            s, runtime, FakeGitOps(),
            task_id=t.id,
            token_registry=registry,
            base_url="http://localhost:8000",
        )

    token = row.hook_token
    assert token is not None
    assert registry.resolve(token) == row.id

    async with db.session() as s:
        await stop_session(s, runtime, row.id, token_registry=registry)

    assert registry.resolve(token) is None
