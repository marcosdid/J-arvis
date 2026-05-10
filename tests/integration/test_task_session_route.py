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


@pytest.mark.integration
async def test_post_task_session_201(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        pid, wid = await _create_project_and_worktree(client, repo)
        task = (await client.post("/api/tasks", json={"project_id": pid, "title": "T"})).json()
        r = await client.post(f"/api/tasks/{task['id']}/sessions", json={"worktree_id": wid})
    assert r.status_code == 201
    body = r.json()
    assert body["task_id"] == task["id"]
    assert body["worktree_id"] == wid
    assert body["status"] == "executing"


@pytest.mark.integration
async def test_post_task_session_unknown_task_404(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        pid, wid = await _create_project_and_worktree(client, repo)
        r = await client.post("/api/tasks/nope/sessions", json={"worktree_id": wid})
    assert r.status_code == 404


@pytest.mark.integration
async def test_post_task_session_unknown_worktree_404(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        pid, _ = await _create_project_and_worktree(client, repo)
        task = (await client.post("/api/tasks", json={"project_id": pid, "title": "T"})).json()
        r = await client.post(f"/api/tasks/{task['id']}/sessions", json={"worktree_id": "nope"})
    assert r.status_code == 404


@pytest.mark.integration
async def test_post_task_session_duplicate_409(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        pid, wid = await _create_project_and_worktree(client, repo)
        task = (await client.post("/api/tasks", json={"project_id": pid, "title": "T"})).json()
        first = await client.post(f"/api/tasks/{task['id']}/sessions", json={"worktree_id": wid})
        second = await client.post(f"/api/tasks/{task['id']}/sessions", json={"worktree_id": wid})
    assert first.status_code == 201
    assert second.status_code == 409


@pytest.mark.integration
async def test_post_task_session_task_sets_state_in_progress(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        pid, wid = await _create_project_and_worktree(client, repo)
        task = (await client.post("/api/tasks", json={"project_id": pid, "title": "T"})).json()
        assert task["state"] == "idea"
        await client.post(f"/api/tasks/{task['id']}/sessions", json={"worktree_id": wid})
        updated = (await client.get(f"/api/tasks/{task['id']}")).json()
    assert updated["state"] == "in_progress"


@pytest.mark.integration
async def test_post_task_session_terminal_state_409(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        pid, wid = await _create_project_and_worktree(client, repo)
        task = (await client.post("/api/tasks", json={"project_id": pid, "title": "T"})).json()
        # Move task to discarded (terminal state)
        await client.patch(f"/api/tasks/{task['id']}", json={"state": "discarded"})
        r = await client.post(f"/api/tasks/{task['id']}/sessions", json={"worktree_id": wid})
    assert r.status_code == 409


@pytest.mark.integration
async def test_post_task_session_publishes_task_updated_on_state_change(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    """When ``start_session`` transitions ``task.state`` (e.g. idea →
    in_progress), the route broadcasts ``task.updated``."""
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)

    received: list[dict[str, object]] = []

    class CollectingBroadcaster:
        async def publish(self, event):  # noqa: ANN001
            received.append(event.to_dict())

    app.state.ws_broadcaster = CollectingBroadcaster()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        pid, wid = await _create_project_and_worktree(client, repo)
        task = (await client.post("/api/tasks", json={"project_id": pid, "title": "T"})).json()
        r = await client.post(f"/api/tasks/{task['id']}/sessions", json={"worktree_id": wid})

    assert r.status_code == 201
    updated = [e for e in received if e["type"] == "task.updated"]
    assert len(updated) == 1
    payload = updated[0]["payload"]
    assert payload["state"] == "in_progress"
    assert payload["previous_state"] == "idea"


@pytest.mark.integration
async def test_post_task_session_inner_get_task_race_returns_404(
    db: Database,
    runtime: FakeSessionRuntime,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Race path: the outer ``get_task`` succeeds but the inner one inside
    ``start_session`` raises ``TaskNotFoundError`` (e.g. concurrent delete).
    The route's inner handler must translate that to 404."""
    from orchestrator.core.tasks import TaskNotFoundError

    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        pid, wid = await _create_project_and_worktree(client, repo)
        task = (await client.post("/api/tasks", json={"project_id": pid, "title": "T"})).json()

        async def vanish(_session, _task_id):  # noqa: ANN202
            raise TaskNotFoundError("task vanished mid-flight")

        monkeypatch.setattr("orchestrator.core.sessions.get_task", vanish)
        r = await client.post(f"/api/tasks/{task['id']}/sessions", json={"worktree_id": wid})
    assert r.status_code == 404
