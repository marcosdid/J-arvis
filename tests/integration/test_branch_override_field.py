"""F5.g: task.branch override via POST/PATCH /tasks.

- POST with valid branch: stored, used by start_session.
- POST with invalid branch: 422.
- PATCH branch before first session: stored.
- PATCH branch after first session (worktrees exist): 422 immutable.
"""
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from orchestrator.main import create_app
from orchestrator.store.database import Database
from tests.integration.conftest import FakeSessionRuntime, _make_repo


async def test_post_task_with_branch_stored(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        proj = (await client.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        r = await client.post("/api/tasks", json={
            "project_id": proj["id"], "title": "T", "branch": "feature/jira-123",
        })
    assert r.status_code == 201
    assert r.json()["branch"] == "feature/jira-123"


async def test_post_task_with_invalid_branch_422(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        proj = (await client.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        r = await client.post("/api/tasks", json={
            "project_id": proj["id"], "title": "T", "branch": "Invalid Branch",
        })
    assert r.status_code == 422


async def test_patch_branch_before_session(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        proj = (await client.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        task = (await client.post("/api/tasks", json={
            "project_id": proj["id"], "title": "T",
        })).json()
        r = await client.patch(f"/api/tasks/{task['id']}", json={"branch": "custom-branch"})
    assert r.status_code == 200
    assert r.json()["branch"] == "custom-branch"


async def test_patch_branch_after_session_422(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        proj = (await client.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        task = (await client.post("/api/tasks", json={
            "project_id": proj["id"], "title": "T",
        })).json()
        await client.post(f"/api/tasks/{task['id']}/sessions", json={})

        r = await client.patch(f"/api/tasks/{task['id']}", json={"branch": "too-late"})
    assert r.status_code == 422
    assert "branch" in r.json()["detail"].lower()


async def test_branch_override_is_used_for_worktree(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        proj = (await client.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        task = (await client.post("/api/tasks", json={
            "project_id": proj["id"],
            "title": "Some long title with many words",
            "branch": "short-name",
        })).json()
        sess = (await client.post(f"/api/tasks/{task['id']}/sessions", json={})).json()
    cwd = Path(sess["cwd"])
    # cwd derived from override, not from slugified title
    assert cwd.name.endswith("--short-name")
