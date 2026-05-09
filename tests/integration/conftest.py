from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

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
        self.spawned: list[JailHandle] = []
        self.killed: list[JailHandle] = []
        self._next_pid = 10000

    async def spawn(self, worktree: Path) -> JailHandle:
        self._next_pid += 1
        handle = JailHandle(
            id=f"fake-{self._next_pid}",
            pid=self._next_pid,
            started_at=datetime.now(UTC),
        )
        self.spawned.append(handle)
        return handle

    async def kill(self, handle: JailHandle) -> None:
        self.killed.append(handle)


@pytest.fixture
def runtime() -> FakeSessionRuntime:
    return FakeSessionRuntime()
