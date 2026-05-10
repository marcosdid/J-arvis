"""F5.g: PATCH /tasks/{id} state=done dispatches cleanup_task_worktrees,
which removes Worktree rows AND the on-disk worktree dir."""
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from orchestrator.main import create_app
from orchestrator.store.database import Database
from tests.integration.conftest import FakeSessionRuntime, _make_repo


async def test_done_triggers_cleanup_removes_worktree(
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
        cwd = Path(sess["cwd"])
        assert cwd.is_dir()

        # Stop session to release active-session guard
        await client.post(f"/api/sessions/{sess['id']}/stop")

        # Walk transitions to done
        await client.patch(f"/api/tasks/{task['id']}", json={"state": "review"})
        r = await client.patch(f"/api/tasks/{task['id']}", json={"state": "done"})
        assert r.status_code == 200

        wts = (await client.get(f"/api/projects/{proj['id']}/worktrees")).json()

    # No worktrees remain for the task; cwd dir gone
    task_wts = [w for w in wts if w["task_id"] == task["id"]]
    assert task_wts == []
    assert not cwd.exists()
