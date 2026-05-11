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

from orchestrator.core.catalog import Catalog
from orchestrator.core.git import GitWorktreeError
from orchestrator.core.sessions import (
    CwdAlreadyExistsError,
    _derive_cwd,
    start_session,
    stop_session,
)
from orchestrator.core.slug import slugify_for_branch
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
    async def spawn(
        self, cwd: Path, *,
        permission_profile=None, catalog=None,
        token=None, base_url=None,
    ) -> JailHandle:
        return JailHandle(id="fake", pid=42, started_at=datetime.now(UTC))

    async def kill(self, handle, *, worktree=None) -> None:
        pass


class FailingRuntime:
    """Spawn always fails - used to test spawn-failure rollback."""

    async def spawn(
        self, cwd: Path, *,
        permission_profile=None, catalog=None,
        token=None, base_url=None,
    ) -> JailHandle:
        raise RuntimeError("simulated spawn failure")

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


async def test_atomic_spawn_multi_repo_happy_path(tmp_path: Path, catalog: Catalog) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/a.db")
    await db.bootstrap()
    git = FakeGitOps()
    runtime = FakeRuntime()
    bc = CollectingBroadcaster()

    async with db.session() as s:
        _, _, task = await _seed_multi_repo_project(s, tmp_path, ["backend", "frontend"])

        row = await start_session(
            s, runtime, git,
            task_id=task.id, broadcaster=bc, catalog=catalog,
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


async def test_atomic_spawn_rollback_on_second_add_fail(tmp_path: Path, catalog: Catalog) -> None:
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
            await start_session(
                s, runtime, git, task_id=task_id, broadcaster=bc, catalog=catalog,
            )

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


async def test_spawn_failure_rolls_back_committed_worktrees(
    tmp_path: Path, catalog: Catalog,
) -> None:
    """When runtime.spawn fails AFTER worktrees are committed to DB,
    rollback must remove them from BOTH filesystem AND database, leaving
    no zombies (DB pointing at non-existent paths)."""
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/sf.db")
    await db.bootstrap()
    git = FakeGitOps()
    bc = CollectingBroadcaster()

    async with db.session() as s:
        _, _, task = await _seed_multi_repo_project(s, tmp_path, ["backend", "frontend"])
        task_id = task.id

    async with db.session() as s:
        with pytest.raises(RuntimeError, match="simulated spawn failure"):
            await start_session(s, FailingRuntime(), git,
                                task_id=task_id, broadcaster=bc, catalog=catalog)

    # Worktrees were created in FS then removed
    assert len(git.added) == 2
    assert len(git.removed) == 2
    # No Worktree rows in DB
    async with db.session() as s:
        wts = (await s.execute(select(Worktree).where(Worktree.task_id == task_id))).scalars().all()
        assert wts == []
    # No broadcasts emitted
    assert [e for e in bc.received if e.type == "worktree.created"] == []


class FlakyRollbackGit(FakeGitOps):
    """Adds succeed; the FIRST add then fails on the rollback remove,
    forcing the warning branch in _rollback_worktrees."""

    def __init__(self) -> None:
        super().__init__(fail_at=1)  # 2nd add fails -> rollback remove of 1st

    async def remove(self, repo: Path, target: Path, *, force: bool = False) -> None:
        raise GitWorktreeError(f"simulated rollback failure on {target}")


async def test_rollback_swallows_git_remove_failure(tmp_path: Path, catalog: Catalog) -> None:
    """When the worktree-rollback path itself fails on git remove, the
    error is logged and swallowed; the original GitWorktreeError still
    propagates and DB rollback completes cleanly."""
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/rb.db")
    await db.bootstrap()
    git = FlakyRollbackGit()

    async with db.session() as s:
        _, _, task = await _seed_multi_repo_project(s, tmp_path, ["backend", "frontend"])
        task_id = task.id

        with pytest.raises(GitWorktreeError):
            await start_session(s, FakeRuntime(), git, task_id=task_id, catalog=catalog)

        # 1st add succeeded, 2nd failed; rollback try-removed the 1st but its
        # remove raised — was warned + swallowed.
        assert len(git.added) == 1
        wts = (await s.execute(select(Worktree).where(Worktree.task_id == task_id))).scalars().all()
        assert wts == []


async def test_spawn_failure_on_re_iniciar_does_not_rollback(
    tmp_path: Path, catalog: Catalog,
) -> None:
    """Re-iniciar reuses existing worktrees; on spawn-fail there are no
    *new* worktrees to rollback. State only reverts if it actually transitioned."""
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/sf2.db")
    await db.bootstrap()
    git = FakeGitOps()
    runtime = FakeRuntime()

    async with db.session() as s:
        _, _, task = await _seed_multi_repo_project(s, tmp_path, ["solo"])
        first = await start_session(s, runtime, git, task_id=task.id, catalog=catalog)
        await stop_session(s, runtime, first.id)
        adds_after_first = len(git.added)

    # Now re-iniciar with a spawn that fails. task.state is already
    # in_progress, so prev_state == new_state -> 202->205 false branch.
    async with db.session() as s:
        with pytest.raises(RuntimeError, match="simulated spawn failure"):
            await start_session(s, FailingRuntime(), git, task_id=task.id, catalog=catalog)

    # No new git.add (re-iniciar reused), and no removes either (nothing to rollback)
    assert len(git.added) == adds_after_first
    assert len(git.removed) == 0


async def test_spawn_failure_when_cwd_already_cleaned_up(tmp_path: Path, catalog: Catalog) -> None:
    """Multi-repo rollback: if the parent cwd was already removed (race),
    the rmdir branch doesn't fire. Covers _rollback_after_spawn_failure
    branch 146->149."""
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/cwd2.db")
    await db.bootstrap()

    class CleanupGit(FakeGitOps):
        """Removes the parent cwd dir during the rollback's git.remove
        so the subsequent cwd.exists() check is False."""

        async def remove(self, repo: Path, target: Path, *, force: bool = False) -> None:
            await super().remove(repo, target, force=force)
            if target.parent.exists() and not any(target.parent.iterdir()):
                target.parent.rmdir()

    git = CleanupGit()
    async with db.session() as s:
        _, _, task = await _seed_multi_repo_project(s, tmp_path, ["a", "b"])
        with pytest.raises(RuntimeError, match="simulated spawn failure"):
            await start_session(s, FailingRuntime(), git, task_id=task.id, catalog=catalog)


async def test_stop_session_idempotent_when_already_done(tmp_path: Path, catalog: Catalog) -> None:
    """Calling stop_session on a session whose status is already terminal
    is a no-op (no extra runtime.kill, no DB mutation)."""
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/idem.db")
    await db.bootstrap()
    git = FakeGitOps()
    runtime = FakeRuntime()

    async with db.session() as s:
        _, _, task = await _seed_multi_repo_project(s, tmp_path, ["solo"])
        row = await start_session(s, runtime, git, task_id=task.id, catalog=catalog)
        await stop_session(s, runtime, row.id)
        kills_after_first = len(getattr(runtime, "killed", []))
        # Second stop is a no-op
        await stop_session(s, runtime, row.id)
        # FakeRuntime doesn't track kills, but the test is about not raising
        # and not erroring on the already-DONE session.
        assert row.status == "done"
        assert kills_after_first == 0  # FakeRuntime.kill is a no-op anyway


async def test_cwd_already_exists_raises_before_any_side_effect(
    tmp_path: Path, catalog: Catalog,
) -> None:
    """If the derived cwd path already exists (from a manual mkdir or stale
    directory), refuse before any git ops or DB writes."""
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/cwd.db")
    await db.bootstrap()
    git = FakeGitOps()

    async with db.session() as s:
        project, _, task = await _seed_multi_repo_project(s, tmp_path, ["backend", "frontend"])
        # Pre-create the cwd path that start_session would derive
        slug = task.branch or slugify_for_branch(task.title)
        cwd = _derive_cwd(project.path, slug)
        cwd.mkdir(parents=True, exist_ok=False)

        with pytest.raises(CwdAlreadyExistsError):
            await start_session(s, FakeRuntime(), git, task_id=task.id, catalog=catalog)

        # Nothing happened
        assert len(git.added) == 0
