from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.core.tasks import TaskNotFoundError
from orchestrator.main import create_app
from orchestrator.store.database import Database
from tests.integration.conftest import (
    FakeSessionRuntime,
    _make_repo,
)


async def _create_project(client: AsyncClient, repo: Path) -> str:
    p = (await client.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
    return p["id"]


@pytest.mark.integration
async def test_post_task_session_201(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        pid = await _create_project(client, repo)
        task = (await client.post("/api/tasks", json={"project_id": pid, "title": "T"})).json()
        r = await client.post(f"/api/tasks/{task['id']}/sessions", json={})
    assert r.status_code == 201
    body = r.json()
    assert body["task_id"] == task["id"]
    assert body.get("cwd")
    assert body["status"] == "executing"


@pytest.mark.integration
async def test_post_task_session_unknown_task_404(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        r = await client.post("/api/tasks/nope/sessions", json={})
    assert r.status_code == 404


@pytest.mark.integration
async def test_post_task_session_duplicate_409(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        pid = await _create_project(client, repo)
        task = (await client.post("/api/tasks", json={"project_id": pid, "title": "T"})).json()
        first = await client.post(f"/api/tasks/{task['id']}/sessions", json={})
        second = await client.post(f"/api/tasks/{task['id']}/sessions", json={})
    assert first.status_code == 201
    assert second.status_code == 409


@pytest.mark.integration
async def test_post_task_session_task_sets_state_in_progress(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        pid = await _create_project(client, repo)
        task = (await client.post("/api/tasks", json={"project_id": pid, "title": "T"})).json()
        assert task["state"] == "idea"
        await client.post(f"/api/tasks/{task['id']}/sessions", json={})
        updated = (await client.get(f"/api/tasks/{task['id']}")).json()
    assert updated["state"] == "in_progress"


@pytest.mark.integration
async def test_post_task_session_terminal_state_409(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        pid = await _create_project(client, repo)
        task = (await client.post("/api/tasks", json={"project_id": pid, "title": "T"})).json()
        await client.patch(f"/api/tasks/{task['id']}", json={"state": "discarded"})
        r = await client.post(f"/api/tasks/{task['id']}/sessions", json={})
    assert r.status_code == 409


@pytest.mark.integration
async def test_post_task_session_unslugifiable_title_422(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    """Title with only punctuation -> empty slug -> InvalidBranchSlugError -> 422."""
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        pid = await _create_project(client, repo)
        task = (await client.post("/api/tasks", json={"project_id": pid, "title": "!!!"})).json()
        r = await client.post(f"/api/tasks/{task['id']}/sessions", json={})
    assert r.status_code == 422


@pytest.mark.integration
async def test_post_task_session_cwd_clash_422(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    """A pre-existing dir at the derived cwd path -> CwdAlreadyExistsError -> 422."""
    repo = _make_repo(tmp_path)
    # Pre-create the dir start_session would derive
    (repo.parent / f"{repo.name}--clash-title").mkdir()
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        pid = await _create_project(client, repo)
        task = (await client.post("/api/tasks", json={"project_id": pid, "title": "Clash title"})).json()
        r = await client.post(f"/api/tasks/{task['id']}/sessions", json={})
    assert r.status_code == 422


@pytest.mark.integration
async def test_post_task_session_legacy_payload_returns_422(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    """Legacy clients sending {worktree_id: ...} get 422 from Pydantic extra=forbid."""
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        pid = await _create_project(client, repo)
        task = (await client.post("/api/tasks", json={"project_id": pid, "title": "T"})).json()
        r = await client.post(
            f"/api/tasks/{task['id']}/sessions", json={"worktree_id": "anything"},
        )
    assert r.status_code == 422


@pytest.mark.integration
async def test_post_task_session_inner_get_task_race_returns_404(
    db: Database,
    runtime: FakeSessionRuntime,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Race path: ``start_session`` calls ``get_task`` internally; if a
    concurrent delete fired, that raises ``TaskNotFoundError``. The route
    must translate it to 404."""
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        pid = await _create_project(client, repo)
        task = (await client.post("/api/tasks", json={"project_id": pid, "title": "T"})).json()

        async def vanish(_session, _task_id):
            raise TaskNotFoundError("task vanished mid-flight")

        monkeypatch.setattr("orchestrator.core.sessions.get_task", vanish)
        r = await client.post(f"/api/tasks/{task['id']}/sessions", json={})
    assert r.status_code == 404
