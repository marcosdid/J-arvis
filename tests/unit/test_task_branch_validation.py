"""F5.e: tasks.branch field validation + immutability after 1st session."""
from pathlib import Path

import pytest

from orchestrator.core.tasks import (
    BranchImmutableAfterFirstSessionError,
    InvalidBranchOverrideError,
    update_task,
)
from orchestrator.store.database import Database
from orchestrator.store.models import Project, Repository, Task, Worktree


async def test_branch_accepts_valid_kebab_with_slash(tmp_path: Path) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/v.db")
    await db.bootstrap()
    async with db.session() as s:
        p = Project(name="p", path=str(tmp_path))
        s.add(p)
        await s.flush()
        t = Task(project_id=p.id, title="T", description="", state="idea")
        s.add(t)
        await s.commit()

        row, _ = await update_task(s, t.id, branch="feature/jira-123")
        assert row.branch == "feature/jira-123"


async def test_branch_accepts_underscore_and_dot_and_dash(tmp_path: Path) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/u.db")
    await db.bootstrap()
    async with db.session() as s:
        p = Project(name="p", path=str(tmp_path))
        s.add(p)
        await s.flush()
        t = Task(project_id=p.id, title="T", description="", state="idea")
        s.add(t)
        await s.commit()

        row, _ = await update_task(s, t.id, branch="release-1.2.0_rc")
        assert row.branch == "release-1.2.0_rc"


async def test_branch_rejects_uppercase(tmp_path: Path) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/uc.db")
    await db.bootstrap()
    async with db.session() as s:
        p = Project(name="p", path=str(tmp_path))
        s.add(p)
        await s.flush()
        t = Task(project_id=p.id, title="T", description="", state="idea")
        s.add(t)
        await s.commit()

        with pytest.raises(InvalidBranchOverrideError):
            await update_task(s, t.id, branch="Feature/X")


async def test_branch_rejects_starts_with_dash(tmp_path: Path) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/d.db")
    await db.bootstrap()
    async with db.session() as s:
        p = Project(name="p", path=str(tmp_path))
        s.add(p)
        await s.flush()
        t = Task(project_id=p.id, title="T", description="", state="idea")
        s.add(t)
        await s.commit()

        with pytest.raises(InvalidBranchOverrideError):
            await update_task(s, t.id, branch="-leading-dash")


async def test_branch_rejects_too_long(tmp_path: Path) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/l.db")
    await db.bootstrap()
    async with db.session() as s:
        p = Project(name="p", path=str(tmp_path))
        s.add(p)
        await s.flush()
        t = Task(project_id=p.id, title="T", description="", state="idea")
        s.add(t)
        await s.commit()

        too_long = "a" + "b" * 201  # 202 chars
        with pytest.raises(InvalidBranchOverrideError):
            await update_task(s, t.id, branch=too_long)


async def test_branch_immutable_after_first_session_creates_worktrees(
    tmp_path: Path,
) -> None:
    """Once worktrees exist for a task, branch cannot be changed."""
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/i.db")
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
        # Simulate the worktree created by start_session
        wt = Worktree(
            repository_id=r.id, task_id=t.id,
            path=str(tmp_path / "wt"), branch="initial",
        )
        s.add(wt)
        await s.commit()

        with pytest.raises(BranchImmutableAfterFirstSessionError):
            await update_task(s, t.id, branch="new-branch")


async def test_branch_changeable_before_first_session(tmp_path: Path) -> None:
    """While task has no worktrees, branch can be set freely."""
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/c.db")
    await db.bootstrap()
    async with db.session() as s:
        p = Project(name="p", path=str(tmp_path))
        s.add(p)
        await s.flush()
        t = Task(project_id=p.id, title="T", description="", state="idea")
        s.add(t)
        await s.commit()

        row, _ = await update_task(s, t.id, branch="first")
        assert row.branch == "first"
        row, _ = await update_task(s, t.id, branch="second")
        assert row.branch == "second"
