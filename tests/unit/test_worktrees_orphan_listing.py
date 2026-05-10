"""F5.f: list_orphan_worktrees + list_worktrees_for_task."""
from pathlib import Path

from orchestrator.core.worktrees import (
    list_orphan_worktrees,
    list_worktrees_for_task,
)
from orchestrator.store.database import Database
from orchestrator.store.models import Project, Repository, Task, Worktree


async def test_list_orphan_worktrees_filters_task_id_null(tmp_path: Path) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/o.db")
    await db.bootstrap()
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
        s.add(Worktree(
            repository_id=r.id, task_id=t.id,
            path=str(tmp_path / "task-wt"), branch="feature",
        ))
        s.add(Worktree(
            repository_id=r.id, task_id=None,
            path=str(tmp_path / "orphan-wt"), branch="external",
        ))
        await s.commit()

        orphans = await list_orphan_worktrees(s, p.id)
        assert len(orphans) == 1
        assert orphans[0].path == str(tmp_path / "orphan-wt")


async def test_list_worktrees_for_task_returns_only_task_owned(tmp_path: Path) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/t.db")
    await db.bootstrap()
    async with db.session() as s:
        p = Project(name="p", path=str(tmp_path))
        s.add(p)
        await s.flush()
        r = Repository(project_id=p.id, name="p", sub_path=".")
        s.add(r)
        await s.flush()
        t1 = Task(project_id=p.id, title="A", description="", state="in_progress")
        t2 = Task(project_id=p.id, title="B", description="", state="in_progress")
        s.add(t1)
        s.add(t2)
        await s.flush()
        s.add(Worktree(
            repository_id=r.id, task_id=t1.id,
            path=str(tmp_path / "a"), branch="a",
        ))
        s.add(Worktree(
            repository_id=r.id, task_id=t2.id,
            path=str(tmp_path / "b"), branch="b",
        ))
        s.add(Worktree(
            repository_id=r.id, task_id=None,
            path=str(tmp_path / "c"), branch="c",
        ))
        await s.commit()

        wts = await list_worktrees_for_task(s, t1.id)
        assert len(wts) == 1
        assert wts[0].branch == "a"
