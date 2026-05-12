"""F9.1: GET /api/health — system metrics endpoint."""
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.main import create_app
from orchestrator.store.database import Database
from orchestrator.store.models import ClaudeSession, Project, Task
from tests.integration.conftest import FakeSessionRuntime, _make_repo


@pytest.mark.integration
async def test_health_returns_expected_shape(
    db: Database, runtime: FakeSessionRuntime,
) -> None:
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert set(data.keys()) >= {
        "cpu_pct",
        "mem_used_bytes",
        "mem_total_bytes",
        "uptime_seconds",
        "active_alerts_count",
    }
    assert isinstance(data["cpu_pct"], (int, float))
    assert data["cpu_pct"] >= 0
    assert data["mem_total_bytes"] > 0
    assert data["mem_used_bytes"] >= 0
    assert data["uptime_seconds"] >= 0
    assert data["active_alerts_count"] == 0


@pytest.mark.integration
async def test_health_counts_awaiting_response_sessions(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    """active_alerts_count reflects ClaudeSession rows with awaiting_response status."""
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        # Baseline: 0 alerts
        r0 = await c.get("/api/health")
        assert r0.json()["active_alerts_count"] == 0

        # Create a project + task so we can insert a session row
        proj = (await c.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        task = (
            await c.post("/api/tasks", json={"project_id": proj["id"], "title": "T"})
        ).json()

    # Insert a ClaudeSession with status='awaiting_response' directly
    async with db.session() as s:
        row = ClaudeSession(
            task_id=task["id"],
            cwd=str(tmp_path),
            status="awaiting_response",
        )
        s.add(row)
        await s.commit()

    # Re-query — new app instance shares same db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r1 = await c.get("/api/health")
    assert r1.status_code == 200
    assert r1.json()["active_alerts_count"] == 1
