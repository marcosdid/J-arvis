from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.main import create_app
from orchestrator.store.database import Database
from tests.integration.conftest import (
    FakeSessionRuntime,
    _make_repo,
    _create_project_and_worktree,
)


@pytest.mark.integration
async def test_quick_session_creates_implicit_task(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        _, wid = await _create_project_and_worktree(client, repo)
        r = await client.post("/api/sessions", json={"worktree_id": wid})
        assert r.status_code == 201
        body = r.json()
        assert "task_id" in body and body["task_id"]
        # Implicit task visible in GET /api/tasks
        tasks = (await client.get("/api/tasks")).json()
        titles = [t["title"] for t in tasks]
        assert any(t.startswith("Quick session ·") for t in titles)
        implicit = next(t for t in tasks if t["title"].startswith("Quick session"))
        assert implicit["state"] == "in_progress"


@pytest.mark.integration
async def test_quick_session_with_main_branch_uses_branch_name(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        _, wid = await _create_project_and_worktree(client, repo)
        await client.post("/api/sessions", json={"worktree_id": wid})
        tasks = (await client.get("/api/tasks")).json()
        # _make_repo uses 'main' branch
        assert any(t["title"] == "Quick session · main" for t in tasks)
