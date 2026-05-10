"""F5.g: re-iniciar — 2nd session on the same task reuses existing
worktrees instead of creating new ones."""
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from orchestrator.main import create_app
from orchestrator.store.database import Database
from tests.integration.conftest import FakeSessionRuntime, _make_repo


async def test_second_session_reuses_existing_cwd(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        proj = (await client.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        task = (await client.post(
            "/api/tasks", json={"project_id": proj["id"], "title": "Fix bug"},
        )).json()
        first = (await client.post(f"/api/tasks/{task['id']}/sessions", json={})).json()
        # Stop the first session to free the active-session slot
        stop_resp = await client.post(f"/api/sessions/{first['id']}/stop")
        assert stop_resp.status_code == 204

        second = (await client.post(f"/api/tasks/{task['id']}/sessions", json={})).json()

        # Both sessions point to the same cwd
        assert second["cwd"] == first["cwd"]
        # Worktree count unchanged after second start
        wts = (await client.get(f"/api/projects/{proj['id']}/worktrees")).json()
        task_wts = [w for w in wts if w["task_id"] == task["id"]]
        assert len(task_wts) == 1

    # Both sessions have the same cwd path on disk
    assert Path(second["cwd"]).is_dir()
