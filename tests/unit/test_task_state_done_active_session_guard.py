"""F5.e guard: PATCH state→done/discarded fails if session is active."""
from pathlib import Path

import pytest

from orchestrator.core.sessions import SessionStatus
from orchestrator.core.tasks import TaskHasActiveSessionError, update_task
from orchestrator.store.database import Database
from orchestrator.store.models import ClaudeSession, Project, Repository, Task


async def test_state_done_with_active_session_raises(tmp_path: Path) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/g.db")
    await db.bootstrap()
    async with db.session() as s:
        p = Project(name="p", path=str(tmp_path))
        s.add(p)
        await s.flush()
        r = Repository(project_id=p.id, name="p", sub_path=".")
        s.add(r)
        await s.flush()
        # Only review->done is a valid transition into 'done'
        t = Task(project_id=p.id, title="T", description="", state="review")
        s.add(t)
        await s.flush()
        cs = ClaudeSession(
            task_id=t.id, cwd=str(tmp_path), status=SessionStatus.EXECUTING,
        )
        s.add(cs)
        await s.commit()

        with pytest.raises(TaskHasActiveSessionError):
            await update_task(s, t.id, state="done")


async def test_state_discarded_with_active_session_raises(tmp_path: Path) -> None:
    """Same guard applies to 'discarded' (terminal state)."""
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/d.db")
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
        cs = ClaudeSession(
            task_id=t.id, cwd=str(tmp_path), status=SessionStatus.EXECUTING,
        )
        s.add(cs)
        await s.commit()

        with pytest.raises(TaskHasActiveSessionError):
            await update_task(s, t.id, state="discarded")


async def test_state_done_without_active_session_ok(tmp_path: Path) -> None:
    """No active session (or all sessions in terminal status) -> state change OK."""
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/o.db")
    await db.bootstrap()
    async with db.session() as s:
        p = Project(name="p", path=str(tmp_path))
        s.add(p)
        await s.flush()
        r = Repository(project_id=p.id, name="p", sub_path=".")
        s.add(r)
        await s.flush()
        # Path A: task with no sessions at all (state idea -> discarded)
        t1 = Task(project_id=p.id, title="A", description="", state="ready")
        s.add(t1)
        # Path B: task with a session that ENDED (status=done)
        t2 = Task(project_id=p.id, title="B", description="", state="in_progress")
        s.add(t2)
        await s.flush()
        cs_done = ClaudeSession(
            task_id=t2.id, cwd=str(tmp_path), status=SessionStatus.DONE,
        )
        s.add(cs_done)
        await s.commit()

        # Path A: ready -> discarded works
        row, prev = await update_task(s, t1.id, state="discarded")
        assert row.state == "discarded"
        assert prev == "ready"

        # Path B: in_progress -> done is not a valid direct transition; we go
        # via review. The guard applies on the final hop. With only DONE
        # sessions the count is 0, so it succeeds.
        await update_task(s, t2.id, state="review")
        row, prev = await update_task(s, t2.id, state="done")
        assert row.state == "done"
        assert prev == "review"


async def test_state_in_progress_does_not_check_active_session(tmp_path: Path) -> None:
    """The guard only fires for terminal states (done/discarded).
    Other transitions (e.g. ready->in_progress) don't check sessions."""
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/n.db")
    await db.bootstrap()
    async with db.session() as s:
        p = Project(name="p", path=str(tmp_path))
        s.add(p)
        await s.flush()
        t = Task(project_id=p.id, title="T", description="", state="ready")
        s.add(t)
        await s.commit()

        # No session at all -> ready -> in_progress works
        row, prev = await update_task(s, t.id, state="in_progress")
        assert row.state == "in_progress"
