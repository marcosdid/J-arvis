import os
import subprocess
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import AsyncClient

from orchestrator.sandbox.runtime import JailHandle
from orchestrator.store.database import Database


@pytest.fixture
async def db(tmp_path: Path) -> AsyncIterator[Database]:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    await database.bootstrap()
    try:
        yield database
    finally:
        await database.close()


class FakeSessionRuntime:
    """In-memory SessionRuntime for tests. Tracks spawned and killed handles."""

    def __init__(self) -> None:
        self.spawned: list[tuple[JailHandle, str | None, str | None]] = []
        self.killed: list[tuple[JailHandle, Path | None]] = []
        self._next_pid = 10000

    async def spawn(
        self,
        worktree: Path,
        *,
        token: str | None = None,
        base_url: str | None = None,
    ) -> JailHandle:
        self._next_pid += 1
        handle = JailHandle(
            id=f"fake-{self._next_pid}",
            pid=self._next_pid,
            started_at=datetime.now(UTC),
        )
        self.spawned.append((handle, token, base_url))
        return handle

    async def kill(self, handle: JailHandle, *, worktree: Path | None = None) -> None:
        self.killed.append((handle, worktree))


@pytest.fixture
def runtime() -> FakeSessionRuntime:
    return FakeSessionRuntime()


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        },
    )


def _make_repo(parent: Path, name: str = "repo") -> Path:
    repo = parent / name
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    (repo / "f").write_text("x", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "-c", "commit.gpgsign=false", "commit", "-m", "init")
    return repo


async def _create_project_and_worktree(
    client: AsyncClient, repo: Path, name: str = "p"
) -> tuple[str, str]:
    project = (await client.post("/api/projects", json={"name": name, "path": str(repo)})).json()
    worktrees = (await client.get(f"/api/projects/{project['id']}/worktrees")).json()
    return project["id"], worktrees[0]["id"]
