import asyncio
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
async def test_two_concurrent_starts_one_wins_one_409(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        pid, wid = await _create_project_and_worktree(client, repo)
        t = (await client.post("/api/tasks", json={"project_id": pid, "title": "T"})).json()
        rs = await asyncio.gather(
            client.post(f"/api/tasks/{t['id']}/sessions", json={"worktree_id": wid}),
            client.post(f"/api/tasks/{t['id']}/sessions", json={"worktree_id": wid}),
        )
        statuses = sorted(r.status_code for r in rs)
        assert statuses == [201, 409]
