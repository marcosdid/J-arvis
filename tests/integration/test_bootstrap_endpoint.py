"""F6.h: POST /api/tasks/{task_id}/bootstrap-manifest."""
import asyncio
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.events.broadcaster import InMemoryWsBroadcaster
from orchestrator.events.envelope import WsEvent
from orchestrator.main import create_app
from orchestrator.store.database import Database
from tests.integration.conftest import FakeSessionRuntime, _make_repo


class CollectingBroadcaster:
    def __init__(self) -> None:
        self.events: list[WsEvent] = []

    async def publish(self, event: WsEvent) -> None:
        self.events.append(event)


@pytest.mark.integration
async def test_bootstrap_404_for_unknown_task(
    db: Database, runtime: FakeSessionRuntime,
) -> None:
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    app.state.ws_broadcaster = InMemoryWsBroadcaster()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/tasks/ghost/bootstrap-manifest")
    assert r.status_code == 404


@pytest.mark.integration
async def test_bootstrap_spawns_session_and_creates_orchestrator_dir(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    app.state.ws_broadcaster = InMemoryWsBroadcaster()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        proj = (await c.post(
            "/api/projects", json={"name": "p", "path": str(repo)},
        )).json()
        task = (await c.post(
            "/api/tasks", json={"project_id": proj["id"], "title": "T"},
        )).json()
        r = await c.post(f"/api/tasks/{task['id']}/bootstrap-manifest")
    assert r.status_code == 202
    body = r.json()
    assert body["cwd"] == str(repo)
    assert len(body["session_id"]) == 32
    # .orchestrator/ criado se não existia
    assert (repo / ".orchestrator").is_dir()
    # Runtime.spawn chamado em project.path (não worktree)
    assert len(runtime.spawned) == 1
    assert runtime.spawned[0][1] is None  # token=None (bootstrap)
    assert runtime.spawned[0][2] is None  # base_url=None


@pytest.mark.integration
async def test_bootstrap_watcher_broadcasts_when_manifest_appears(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    """Endpoint spawna watcher em background. Quando file aparece, evento
    `bootstrap.proposed` é broadcasted. Aqui esperamos brevemente + criamos
    o arquivo + verificamos o evento."""
    repo = _make_repo(tmp_path)
    bc = CollectingBroadcaster()
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    app.state.ws_broadcaster = bc
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        proj = (await c.post(
            "/api/projects", json={"name": "p", "path": str(repo)},
        )).json()
        task = (await c.post(
            "/api/tasks", json={"project_id": proj["id"], "title": "T"},
        )).json()
        r = await c.post(f"/api/tasks/{task['id']}/bootstrap-manifest")
        assert r.status_code == 202

        # Cria o manifesto após pequeno delay pro watcher pollar
        await asyncio.sleep(0.05)
        (repo / ".orchestrator" / "run.yml").write_text(
            "version: '1'\nservices: {a: {image: x}}",
        )

        # Espera o watcher detectar (default interval = 2s — muito lento
        # pra teste). O endpoint produção usa default 2s, mas como esse
        # é E2E-style, vamos forçar com timeout maior.
        deadline = asyncio.get_event_loop().time() + 5.0
        while not any(
            e.type == "bootstrap.proposed" for e in bc.events
        ) and asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(0.1)

    proposed = [e for e in bc.events if e.type == "bootstrap.proposed"]
    assert len(proposed) >= 1
    assert "version: '1'" in proposed[0].payload["manifest_text"]
