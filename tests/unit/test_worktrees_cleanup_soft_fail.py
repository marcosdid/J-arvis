"""F5.f cleanup: per-worktree git remove failure orphans the row instead
of bubbling up. Pattern mirrors test_session_start_atomic.py: FakeGitOps
+ CollectingBroadcaster for honest verification."""
import shutil
from pathlib import Path

from sqlalchemy import select

from orchestrator.core.git import GitWorktreeError
from orchestrator.core.worktrees import cleanup_task_worktrees, list_project_worktrees
from orchestrator.events.envelope import WsEvent
from orchestrator.store.database import Database
from orchestrator.store.models import (
    Project,
    Repository,
    Task,
    Worktree,
)


class FakeGitOps:
    def __init__(self, fail_on_remove_paths: set[str] | None = None) -> None:
        self.added: list[tuple[Path, Path, str]] = []
        self.removed: list[tuple[Path, Path]] = []
        self._fail_paths = fail_on_remove_paths or set()

    async def add(self, repo: Path, target: Path, branch: str) -> None:
        self.added.append((repo, target, branch))
        target.mkdir(parents=True, exist_ok=True)

    async def remove(self, repo: Path, target: Path, *, force: bool = False) -> None:
        self.removed.append((repo, target))
        if str(target) in self._fail_paths:
            raise GitWorktreeError(f"simulated remove failure for {target}")
        if target.exists():
            shutil.rmtree(target)

    async def list(self, repo: Path):
        return []


class CollectingBroadcaster:
    def __init__(self) -> None:
        self.received: list[WsEvent] = []

    async def publish(self, event: WsEvent) -> None:
        self.received.append(event)


async def _seed_task_with_2_worktrees(
    session, tmp_path: Path, fail_subpath: str | None = None,
) -> tuple[Project, Task, list[Worktree]]:
    """Create a multi-repo project with 1 task and 2 worktrees on disk.
    Returns (project, task, worktrees)."""
    proj_path = tmp_path / "p"
    proj_path.mkdir()
    project = Project(name="p", path=str(proj_path))
    session.add(project)
    await session.flush()
    repos = []
    for sub in ["backend", "frontend"]:
        sub_dir = proj_path / sub
        sub_dir.mkdir()
        r = Repository(project_id=project.id, name=sub, sub_path=sub)
        session.add(r)
        repos.append(r)
    await session.flush()
    task = Task(project_id=project.id, title="T", description="", state="in_progress")
    session.add(task)
    await session.flush()
    wts = []
    parent_cwd = tmp_path / "p--feature"
    parent_cwd.mkdir()
    for sub, repo in zip(["backend", "frontend"], repos, strict=True):
        wt_path = parent_cwd / sub
        wt_path.mkdir()
        wt = Worktree(
            repository_id=repo.id, task_id=task.id,
            path=str(wt_path), branch="feature",
        )
        session.add(wt)
        wts.append(wt)
    await session.commit()
    return project, task, wts


async def test_cleanup_happy_path_removes_all_and_broadcasts(tmp_path: Path) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/h.db")
    await db.bootstrap()
    git = FakeGitOps()
    bc = CollectingBroadcaster()

    async with db.session() as s:
        _, task, _wts = await _seed_task_with_2_worktrees(s, tmp_path)
        task_id = task.id

    async with db.session() as s:
        await cleanup_task_worktrees(s, git, bc, task_id)

    assert len(git.removed) == 2
    async with db.session() as s:
        wts_after = (await s.execute(
            select(Worktree).where(Worktree.task_id == task_id)
        )).scalars().all()
        assert wts_after == []
    removed_evts = [e for e in bc.received if e.type == "worktree.removed"]
    orphaned_evts = [e for e in bc.received if e.type == "worktree.orphaned"]
    assert len(removed_evts) == 2
    assert orphaned_evts == []


async def test_cleanup_soft_fail_orphans_failed_worktree(tmp_path: Path) -> None:
    """When git remove fails for one of N worktrees, that row is orphaned
    (task_id=NULL) and the others succeed. State transition is not blocked."""
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/sf.db")
    await db.bootstrap()
    bc = CollectingBroadcaster()

    async with db.session() as s:
        _, task, wts = await _seed_task_with_2_worktrees(s, tmp_path)
        task_id = task.id
        frontend_path = next(w.path for w in wts if w.path.endswith("frontend"))

    git = FakeGitOps(fail_on_remove_paths={frontend_path})

    async with db.session() as s:
        await cleanup_task_worktrees(s, git, bc, task_id)

    async with db.session() as s:
        all_wts = (await s.execute(select(Worktree))).scalars().all()
        assert len(all_wts) == 1
        assert all_wts[0].task_id is None
        assert all_wts[0].path == frontend_path

    removed_evts = [e for e in bc.received if e.type == "worktree.removed"]
    orphaned_evts = [e for e in bc.received if e.type == "worktree.orphaned"]
    assert len(removed_evts) == 1
    assert len(orphaned_evts) == 1


class FlakyListGit(FakeGitOps):
    """git.list raises GitWorktreeError; sync should swallow + log + skip."""

    async def list(self, repo: Path):
        raise GitWorktreeError(f"simulated list failure on {repo}")


async def test_list_project_worktrees_skips_repos_whose_list_fails(
    tmp_path: Path,
) -> None:
    """When ``git worktree list`` fails for one repo, the sync logs a
    warning and skips that repo without raising."""
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/lf.db")
    await db.bootstrap()
    async with db.session() as s:
        proj_path = tmp_path / "p"
        proj_path.mkdir()
        p = Project(name="p", path=str(proj_path))
        s.add(p)
        await s.flush()
        r = Repository(project_id=p.id, name="p", sub_path=".")
        s.add(r)
        await s.commit()
        project_id = p.id

    git = FlakyListGit()
    async with db.session() as s:
        result = await list_project_worktrees(s, git, project_id)
    assert list(result) == []  # nothing in DB, nothing discovered (skipped)


async def test_cleanup_skips_rmdir_when_oserror(
    tmp_path: Path, monkeypatch,
) -> None:
    """When the parent dir rmdir fails (e.g. residual file appears between
    iterdir() and rmdir()), the OSError is swallowed; cleanup completes."""
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/oe.db")
    await db.bootstrap()
    git = FakeGitOps()
    bc = CollectingBroadcaster()

    async with db.session() as s:
        _, task, _ = await _seed_task_with_2_worktrees(s, tmp_path)
        task_id = task.id

    # Patch Path.rmdir to raise OSError unconditionally
    original = Path.rmdir

    def boom(self):
        raise OSError("simulated rmdir failure")

    monkeypatch.setattr(Path, "rmdir", boom)

    async with db.session() as s:
        await cleanup_task_worktrees(s, git, bc, task_id)

    # Cleanup still removed worktrees + broadcasted, despite the rmdir failure
    monkeypatch.setattr(Path, "rmdir", original)
    removed_evts = [e for e in bc.received if e.type == "worktree.removed"]
    assert len(removed_evts) == 2


async def test_cleanup_no_worktrees_is_noop(tmp_path: Path) -> None:
    """If task has no worktrees, cleanup is a no-op (no commit needed)."""
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/n.db")
    await db.bootstrap()
    git = FakeGitOps()
    bc = CollectingBroadcaster()

    async with db.session() as s:
        p = Project(name="p", path=str(tmp_path))
        s.add(p)
        await s.flush()
        t = Task(project_id=p.id, title="T", description="", state="ready")
        s.add(t)
        await s.commit()
        task_id = t.id

    async with db.session() as s:
        await cleanup_task_worktrees(s, git, bc, task_id)

    assert git.removed == []
    assert bc.received == []
