"""F5.g: monorepo flow — POST /tasks/{id}/sessions creates 1 worktree
in <project_parent>/<name>--<slug>, populates Worktree row, sets cwd."""
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from orchestrator.main import create_app
from orchestrator.store.database import Database
from tests.integration.conftest import FakeSessionRuntime, _make_repo


async def test_monorepo_session_creates_single_worktree(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        proj = (await client.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        task = (await client.post(
            "/api/tasks", json={"project_id": proj["id"], "title": "Add OAuth"},
        )).json()
        sess = (await client.post(f"/api/tasks/{task['id']}/sessions", json={})).json()

        wts = (await client.get(f"/api/projects/{proj['id']}/worktrees")).json()

    cwd = Path(sess["cwd"])
    assert cwd.is_dir()
    assert cwd.name == f"{repo.name}--add-oauth"
    assert cwd.parent == repo.parent

    # Single worktree row, branch derived from slug, attached to task.
    task_wts = [w for w in wts if w["task_id"] == task["id"]]
    assert len(task_wts) == 1
    assert task_wts[0]["path"] == str(cwd)
    assert task_wts[0]["branch"] == "add-oauth"
    assert task_wts[0]["is_orphan"] is False
