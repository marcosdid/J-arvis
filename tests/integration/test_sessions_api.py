"""F5.g: GET /api/sessions and POST /api/sessions/{id}/stop.

The legacy POST /api/sessions for "quick session" was DROPPED in F5
(decision #5). Sessions are now only created via POST /api/tasks/{id}/sessions.
"""
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.main import create_app
from orchestrator.store.database import Database
from tests.integration.conftest import FakeSessionRuntime, _make_repo


@pytest.mark.integration
async def test_get_sessions_empty(db: Database, runtime: FakeSessionRuntime) -> None:
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        r = await client.get("/api/sessions")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.integration
async def test_get_sessions_returns_created(
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
        r = await client.get("/api/sessions")
    assert r.status_code == 200
    sessions = r.json()
    assert len(sessions) == 1
    assert sessions[0]["task_id"] == task["id"]
    assert sessions[0]["status"] == "executing"
    assert sessions[0]["cwd"]


@pytest.mark.integration
async def test_stop_session_marks_done(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        proj = (await client.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        task = (await client.post(
            "/api/tasks", json={"project_id": proj["id"], "title": "T"},
        )).json()
        sess = (await client.post(f"/api/tasks/{task['id']}/sessions", json={})).json()
        stop = await client.post(f"/api/sessions/{sess['id']}/stop")

        listing = await client.get("/api/sessions")

    assert stop.status_code == 204
    assert listing.json()[0]["status"] == "done"
    assert listing.json()[0]["ended_at"] is not None
    assert len(runtime.killed) == 1


@pytest.mark.integration
async def test_stop_unknown_session_returns_404(
    db: Database, runtime: FakeSessionRuntime,
) -> None:
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        r = await client.post("/api/sessions/nope/stop")
    assert r.status_code == 404
