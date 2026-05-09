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
async def test_delete_project_with_tasks_returns_409(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        pid, _ = await _create_project_and_worktree(client, repo)
        await client.post("/api/tasks", json={"project_id": pid, "title": "Blocker"})
        r = await client.delete(f"/api/projects/{pid}")
    assert r.status_code == 409
