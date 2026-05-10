"""F5.d: start_session atomic in 3 layers (FS, DB, WS).

Uses FakeGitWorktreeOps to inject controlled failures and asserts
rollback semantics. Uses CollectingBroadcaster (NOT
InMemoryWsBroadcaster.subscribers) to actually verify zero broadcasts
on rollback - subscribers tracks `subscribe()` calls and is independent
of `publish()`. The honest test is: collect every event published.
"""
import shutil
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from orchestrator.core.git import GitWorktreeError
from orchestrator.core.sessions import start_session
from orchestrator.events.envelope import WsEvent
from orchestrator.sandbox.runtime import JailHandle
from orchestrator.store.database import Database
from orchestrator.store.models import (
    Project,
    Repository,
    Task,
    Worktree,
)


class FakeGitOps:
    def __init__(self, fail_at: int | None = None) -> None:
        self.added: list[tuple[Path, Path, str]] = []
        self.removed: list[tuple[Path, Path]] = []
        self._fail_at = fail_at

    async def add(self, repo: Path, target: Path, branch: str) -> None:
        if self._fail_at is not None and len(self.added) == self._fail_at:
            raise GitWorktreeError(f"simulated failure on add #{self._fail_at}")
        self.added.append((repo, target, branch))
        target.mkdir(parents=True, exist_ok=True)
        (target / ".git").write_text("ref")

    async def remove(self, repo: Path, target: Path, *, force: bool = False) -> None:
        self.removed.append((repo, target))
        if target.exists():
            shutil.rmtree(target)

    async def list(self, repo: Path):
        return []


class CollectingBroadcaster:
    """Captures every WsEvent published. Use this - NOT
    InMemoryWsBroadcaster - when the test needs to assert WHAT was
    broadcast, not just track subscribers."""

    def __init__(self) -> None:
        self.received: list[WsEvent] = []

    async def publish(self, event: WsEvent) -> None:
        self.received.append(event)


class FakeRuntime:
    async def spawn(self, cwd: Path, *, token=None, base_url=None) -> JailHandle:
        return JailHandle(id="fake", pid=42, started_at=datetime.now(UTC))

    async def kill(self, handle, *, worktree=None) -> None:
        pass


async def _seed_multi_repo_project(
    session, tmp_path: Path, sub_repos: Iterable[str]
) -> tuple[Project, list[Repository], Task]:
    proj_path = tmp_path / "p"
    proj_path.mkdir()
    project = Project(name="p", path=str(proj_path))
    session.add(project)
    await session.flush()
    repos = []
    for sub in sub_repos:
        r = Repository(project_id=project.id, name=sub, sub_path=sub)
        session.add(r)
        repos.append(r)
    task = Task(project_id=project.id, title="Add OAuth", description="")
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return project, repos, task


async def test_atomic_spawn_multi_repo_happy_path(tmp_path: Path) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/a.db")
    await db.bootstrap()
    git = FakeGitOps()
    runtime = FakeRuntime()
    bc = CollectingBroadcaster()

    async with db.session() as s:
        _, _, task = await _seed_multi_repo_project(s, tmp_path, ["backend", "frontend"])

        row = await start_session(
            s, runtime, git,
            task_id=task.id, broadcaster=bc,
        )

        # 2 worktrees criadas no FS via Fake
        assert len(git.added) == 2
        # cwd parent contém os 2
        cwd = Path(row.cwd)
        assert cwd.exists()
        assert (cwd / "backend").is_dir()
        assert (cwd / "frontend").is_dir()
        # DB rows committed
        wts = (await s.execute(select(Worktree).where(Worktree.task_id == task.id))).scalars().all()
        assert len(wts) == 2
        # WS broadcasted 2 worktree.created events (após commit, não antes)
        worktree_events = [e for e in bc.received if e.type == "worktree.created"]
        assert len(worktree_events) == 2


async def test_atomic_spawn_rollback_on_second_add_fail(tmp_path: Path) -> None:
    """Critical: rollback on partial failure must leave NO traces:
    no FS, no DB rows committed, NO worktree.created broadcasts emitted.
    """
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/r.db")
    await db.bootstrap()
    git = FakeGitOps(fail_at=1)  # 2nd add falha
    runtime = FakeRuntime()
    bc = CollectingBroadcaster()

    async with db.session() as s:
        _, _, task = await _seed_multi_repo_project(s, tmp_path, ["backend", "frontend"])
        task_id = task.id  # capture before rollback expires attributes

        with pytest.raises(GitWorktreeError):
            await start_session(s, runtime, git, task_id=task_id, broadcaster=bc)

        # 1st add foi feito; rollback chamou remove
        assert len(git.added) == 1
        assert len(git.removed) == 1
        # Nada committed
        wts = (await s.execute(select(Worktree).where(Worktree.task_id == task_id))).scalars().all()
        assert len(wts) == 0
        # ZERO broadcasts de worktree.created (deferred até pós-commit; rollback bloqueou)
        worktree_events = [e for e in bc.received if e.type == "worktree.created"]
        assert worktree_events == [], (
            f"expected no worktree.created broadcasts on rollback; got {worktree_events}"
        )
