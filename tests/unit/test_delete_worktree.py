"""F5.f: delete_worktree only removes orphans; refuses task-owned ones."""
from pathlib import Path

import pytest

from orchestrator.core.worktrees import (
    WorktreeNotFoundError,
    WorktreeNotOrphanError,
    delete_worktree,
)
from orchestrator.store.database import Database
from orchestrator.store.models import Project, Repository, Task, Worktree


class FakeGitOps:
    def __init__(self) -> None:
        self.removed: list[tuple[Path, Path]] = []

    async def add(self, repo, target, branch):
        pass

    async def list(self, repo):
        return []

    async def remove(self, repo: Path, target: Path, *, force: bool = False) -> None:
        self.removed.append((repo, target))


async def test_delete_orphan_worktree_removes_fs_and_db(tmp_path: Path) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/d.db")
    await db.bootstrap()
    git = FakeGitOps()

    async with db.session() as s:
        p = Project(name="p", path=str(tmp_path))
        s.add(p)
        await s.flush()
        r = Repository(project_id=p.id, name="p", sub_path=".")
        s.add(r)
        await s.flush()
        wt = Worktree(
            repository_id=r.id, task_id=None,
            path=str(tmp_path / "orphan"), branch="external",
        )
        s.add(wt)
        await s.commit()
        wt_id = wt.id

    async with db.session() as s:
        await delete_worktree(s, git, wt_id)

    assert len(git.removed) == 1

    async with db.session() as s:
        result = await s.get(Worktree, wt_id)
        assert result is None


async def test_delete_worktree_task_owned_raises_not_orphan(tmp_path: Path) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/no.db")
    await db.bootstrap()
    git = FakeGitOps()

    async with db.session() as s:
        p = Project(name="p", path=str(tmp_path))
        s.add(p)
        await s.flush()
        r = Repository(project_id=p.id, name="p", sub_path=".")
        s.add(r)
        await s.flush()
        t = Task(project_id=p.id, title="T", description="", state="in_progress")
        s.add(t)
        await s.flush()
        wt = Worktree(
            repository_id=r.id, task_id=t.id,
            path=str(tmp_path / "owned"), branch="owned",
        )
        s.add(wt)
        await s.commit()
        wt_id = wt.id

    async with db.session() as s:
        with pytest.raises(WorktreeNotOrphanError):
            await delete_worktree(s, git, wt_id)
    assert git.removed == []


async def test_delete_worktree_unknown_id_raises_not_found(tmp_path: Path) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/nf.db")
    await db.bootstrap()
    git = FakeGitOps()

    async with db.session() as s:
        with pytest.raises(WorktreeNotFoundError):
            await delete_worktree(s, git, "does-not-exist")
