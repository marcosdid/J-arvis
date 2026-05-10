import asyncio
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.main import create_app
from orchestrator.store.database import Database
from tests.integration.conftest import (
    FakeSessionRuntime,
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
        proj = (await client.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        t = (await client.post("/api/tasks", json={"project_id": proj["id"], "title": "T"})).json()
        rs = await asyncio.gather(
            client.post(f"/api/tasks/{t['id']}/sessions", json={}),
            client.post(f"/api/tasks/{t['id']}/sessions", json={}),
        )
    statuses = sorted(r.status_code for r in rs)
    assert statuses == [201, 409]
