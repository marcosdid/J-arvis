from pathlib import Path

from orchestrator.core.projects import create_project
from orchestrator.core.tasks import ensure_task_for_quick_session
from orchestrator.store.models import Worktree


async def _seed(db_session, tmp_path: Path, branch: str | None):
    repo = tmp_path / "r"
    repo.mkdir(exist_ok=True)
    (repo / ".git").mkdir(exist_ok=True)
    p = await create_project(db_session, "p", str(repo))
    w = Worktree(project_id=p.id, path=str(repo), branch=branch)
    db_session.add(w)
    await db_session.commit()
    await db_session.refresh(w)
    return p, w


async def test_ensure_task_for_quick_session_creates_in_progress(db_session, tmp_path):
    p, w = await _seed(db_session, tmp_path, "feature/foo")
    task = await ensure_task_for_quick_session(db_session, worktree_id=w.id)
    assert task.title == "Quick session · feature/foo"
    assert task.state == "in_progress"
    assert task.project_id == p.id


async def test_ensure_task_for_quick_session_detached(db_session, tmp_path):
    _, w = await _seed(db_session, tmp_path, None)
    task = await ensure_task_for_quick_session(db_session, worktree_id=w.id)
    assert task.title == "Quick session · (detached)"
