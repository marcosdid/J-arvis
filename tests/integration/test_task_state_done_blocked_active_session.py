"""F5.g: PATCH /tasks/{id} state=done with an active session is rejected
with HTTP 422 (TaskHasActiveSessionError) — must stop the session first."""
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from orchestrator.main import create_app
from orchestrator.store.database import Database
from tests.integration.conftest import FakeSessionRuntime, _make_repo


async def test_done_blocked_when_active_session(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        proj = (await client.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        task = (await client.post(
            "/api/tasks", json={"project_id": proj["id"], "title": "T"},
        )).json()
        await client.post(f"/api/tasks/{task['id']}/sessions", json={})

        await client.patch(f"/api/tasks/{task['id']}", json={"state": "review"})
        r = await client.patch(f"/api/tasks/{task['id']}", json={"state": "done"})

    assert r.status_code == 422
    detail = r.json()["detail"].lower()
    assert "active session" in detail
