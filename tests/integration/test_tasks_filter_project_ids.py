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
async def test_filter_project_ids(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    repo_a = _make_repo(tmp_path, name="repo_a")
    repo_b = _make_repo(tmp_path, name="repo_b")
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        pid_a, _ = await _create_project_and_worktree(client, repo_a, name="project_a")
        pid_b, _ = await _create_project_and_worktree(client, repo_b, name="project_b")
        await client.post("/api/tasks", json={"project_id": pid_a, "title": "Task A1"})
        await client.post("/api/tasks", json={"project_id": pid_a, "title": "Task A2"})
        await client.post("/api/tasks", json={"project_id": pid_b, "title": "Task B1"})

        all_tasks = (await client.get("/api/tasks")).json()
        filtered = (await client.get(f"/api/tasks?project_ids={pid_a}")).json()

    assert len(all_tasks) == 3
    assert len(filtered) == 2
    assert all(t["project_id"] == pid_a for t in filtered)
