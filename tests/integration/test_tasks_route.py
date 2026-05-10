from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.main import create_app
from orchestrator.store.database import Database
from tests.integration.conftest import (
    FakeSessionRuntime,
    _create_project_and_worktree,
    _make_repo,
)


# ---------------------------------------------------------------------------
# Broadcast integration tests (F4.f)
# ---------------------------------------------------------------------------

class _CaptureClient:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def send_json(self, data: dict) -> None:  # type: ignore[override]
        self.events.append(data)


def _wired_app_with_capture(db: Database, runtime: FakeSessionRuntime) -> tuple:
    from orchestrator.events.broadcaster import InMemoryWsBroadcaster
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    bc = InMemoryWsBroadcaster()
    capture = _CaptureClient()
    bc.subscribe(capture)  # type: ignore[arg-type]
    app.state.ws_broadcaster = bc
    return app, capture


@pytest.mark.integration
async def test_post_task_broadcasts_task_created(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    repo = _make_repo(tmp_path)
    app, capture = _wired_app_with_capture(db, runtime)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        pid, _ = await _create_project_and_worktree(client, repo)
        await client.post("/api/tasks", json={"project_id": pid, "title": "X"})

    types = [e["type"] for e in capture.events]
    assert "task.created" in types


@pytest.mark.integration
async def test_patch_state_broadcasts_task_updated(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    repo = _make_repo(tmp_path)
    app, capture = _wired_app_with_capture(db, runtime)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        pid, _ = await _create_project_and_worktree(client, repo)
        t = (await client.post("/api/tasks", json={"project_id": pid, "title": "T"})).json()
        await client.patch(f"/api/tasks/{t['id']}", json={"state": "ready"})

    types = [e["type"] for e in capture.events]
    assert types.count("task.updated") == 1
    updated = next(e for e in capture.events if e["type"] == "task.updated")
    assert updated["payload"]["state"] == "ready"
    assert updated["payload"]["previous_state"] == "idea"


@pytest.mark.integration
async def test_patch_state_idempotent_does_not_broadcast(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    repo = _make_repo(tmp_path)
    app, capture = _wired_app_with_capture(db, runtime)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        pid, _ = await _create_project_and_worktree(client, repo)
        t = (await client.post("/api/tasks", json={"project_id": pid, "title": "T"})).json()
        # Same state — no transition
        await client.patch(f"/api/tasks/{t['id']}", json={"state": "idea"})

    updated = [e for e in capture.events if e["type"] == "task.updated"]
    assert len(updated) == 0


@pytest.mark.integration
async def test_post_task_201(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        pid, _ = await _create_project_and_worktree(client, repo)
        r = await client.post("/api/tasks", json={"project_id": pid, "title": "Adicionar dark mode"})
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "Adicionar dark mode"
    assert body["state"] == "idea"
    assert body["project_id"] == pid
    assert body["active_session_id"] is None


@pytest.mark.integration
async def test_post_task_unknown_project_404(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        r = await client.post("/api/tasks", json={"project_id": "nonexistent", "title": "T"})
    assert r.status_code == 404


@pytest.mark.integration
async def test_post_task_empty_title_422(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        pid, _ = await _create_project_and_worktree(client, repo)
        r = await client.post("/api/tasks", json={"project_id": pid, "title": "   "})
    assert r.status_code == 422


@pytest.mark.integration
async def test_get_tasks_list_empty(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        r = await client.get("/api/tasks")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.integration
async def test_get_tasks_list_returns_created(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        pid, _ = await _create_project_and_worktree(client, repo)
        await client.post("/api/tasks", json={"project_id": pid, "title": "T1"})
        await client.post("/api/tasks", json={"project_id": pid, "title": "T2"})
        r = await client.get("/api/tasks")
    assert r.status_code == 200
    tasks = r.json()
    assert len(tasks) == 2
    titles = {t["title"] for t in tasks}
    assert titles == {"T1", "T2"}


@pytest.mark.integration
async def test_get_task_one_200(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        pid, _ = await _create_project_and_worktree(client, repo)
        created = (await client.post("/api/tasks", json={"project_id": pid, "title": "My task"})).json()
        r = await client.get(f"/api/tasks/{created['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]
    assert r.json()["title"] == "My task"


@pytest.mark.integration
async def test_get_task_one_404(
    db: Database, runtime: FakeSessionRuntime
) -> None:
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        r = await client.get("/api/tasks/nope")
    assert r.status_code == 404


@pytest.mark.integration
async def test_patch_task_title(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        pid, _ = await _create_project_and_worktree(client, repo)
        created = (await client.post("/api/tasks", json={"project_id": pid, "title": "Old"})).json()
        r = await client.patch(f"/api/tasks/{created['id']}", json={"title": "New"})
    assert r.status_code == 200
    assert r.json()["title"] == "New"


@pytest.mark.integration
async def test_patch_task_invalid_transition_422(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        pid, _ = await _create_project_and_worktree(client, repo)
        created = (await client.post("/api/tasks", json={"project_id": pid, "title": "T"})).json()
        r = await client.patch(f"/api/tasks/{created['id']}", json={"state": "done"})
    assert r.status_code == 422


@pytest.mark.integration
async def test_patch_task_not_found_404(
    db: Database, runtime: FakeSessionRuntime
) -> None:
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        r = await client.patch("/api/tasks/nope", json={"title": "New"})
    assert r.status_code == 404


@pytest.mark.integration
async def test_patch_task_empty_title_422(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        pid, _ = await _create_project_and_worktree(client, repo)
        created = (await client.post("/api/tasks", json={"project_id": pid, "title": "T"})).json()
        r = await client.patch(f"/api/tasks/{created['id']}", json={"title": "   "})
    assert r.status_code == 422
