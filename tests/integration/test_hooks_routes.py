from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from orchestrator.events.broadcaster import InMemoryWsBroadcaster
from orchestrator.hooks.tokens import TokenRegistry, generate_token
from orchestrator.main import create_app
from orchestrator.notifications.notify_send import NoopNotifier
from orchestrator.store.database import Database
from orchestrator.store.models import ClaudeSession, Project, Task, Worktree
from tests.integration.conftest import FakeSessionRuntime


async def _seed(db: Database, status: str = "executing") -> tuple[str, str]:
    token = generate_token()
    async with db.session() as s:
        proj = Project(name="p", path="/tmp/p")
        s.add(proj)
        await s.commit()
        await s.refresh(proj)
        wt = Worktree(project_id=proj.id, path="/tmp/p/wt", branch="main")
        s.add(wt)
        await s.commit()
        await s.refresh(wt)
        task = Task(project_id=proj.id, title="seed", description="", state="in_progress")
        s.add(task)
        await s.commit()
        await s.refresh(task)
        sess = ClaudeSession(
            worktree_id=wt.id,
            task_id=task.id,
            status=status,
            pid=1,
            jail_id="j",
            started_at=datetime.now(UTC),
            hook_token=token,
        )
        s.add(sess)
        await s.commit()
        await s.refresh(sess)
        return sess.id, token


def _build_app(
    db: Database,
    registry: TokenRegistry,
    broadcaster: InMemoryWsBroadcaster,
    notifier: NoopNotifier,
) -> FastAPI:
    app = create_app(database=db, runtime=FakeSessionRuntime(), ui_dist=None)
    app.state.token_registry = registry
    app.state.ws_broadcaster = broadcaster
    app.state.notifier = notifier
    return app


@pytest.mark.integration
async def test_notification_unknown_token_returns_404(db: Database) -> None:
    app = _build_app(db, TokenRegistry(), InMemoryWsBroadcaster(), NoopNotifier())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post("/api/hooks/Notification/nope", json={"message": "x"})
    assert r.status_code == 404


@pytest.mark.integration
async def test_notification_mutates_status(db: Database) -> None:
    sid, token = await _seed(db)
    registry = TokenRegistry()
    registry.register(token, sid)
    app = _build_app(db, registry, InMemoryWsBroadcaster(), NoopNotifier())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(f"/api/hooks/Notification/{token}", json={"message": "x"})
    assert r.status_code == 204
    async with db.session() as s:
        row = await s.get(ClaudeSession, sid)
        assert row.status == "awaiting_response"


@pytest.mark.integration
async def test_pretooluse_returns_continue_true(db: Database) -> None:
    sid, token = await _seed(db)
    registry = TokenRegistry()
    registry.register(token, sid)
    app = _build_app(db, registry, InMemoryWsBroadcaster(), NoopNotifier())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            f"/api/hooks/PreToolUse/{token}",
            json={"tool_name": "Bash", "tool_input": {"command": "ls"}},
        )
    assert r.status_code == 200
    assert r.json() == {"continue": True}


@pytest.mark.integration
async def test_stop_hook_sets_idle(db: Database) -> None:
    sid, token = await _seed(db)
    registry = TokenRegistry()
    registry.register(token, sid)
    app = _build_app(db, registry, InMemoryWsBroadcaster(), NoopNotifier())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(f"/api/hooks/Stop/{token}", json={"reason": "end"})
    assert r.status_code == 204
    async with db.session() as s:
        row = await s.get(ClaudeSession, sid)
        assert row.status == "idle"


@pytest.mark.integration
async def test_notification_malformed_payload_returns_422(db: Database) -> None:
    sid, token = await _seed(db)
    registry = TokenRegistry()
    registry.register(token, sid)
    app = _build_app(db, registry, InMemoryWsBroadcaster(), NoopNotifier())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(f"/api/hooks/Notification/{token}", json={})
    assert r.status_code == 422


@pytest.mark.integration
async def test_pretooluse_malformed_payload_returns_422(db: Database) -> None:
    sid, token = await _seed(db)
    registry = TokenRegistry()
    registry.register(token, sid)
    app = _build_app(db, registry, InMemoryWsBroadcaster(), NoopNotifier())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(f"/api/hooks/PreToolUse/{token}", json={})
    assert r.status_code == 422


@pytest.mark.integration
async def test_notification_idempotent_when_already_awaiting(db: Database) -> None:
    sid, token = await _seed(db, status="awaiting_response")
    registry = TokenRegistry()
    registry.register(token, sid)
    bc = InMemoryWsBroadcaster()
    received: list[dict] = []

    class Cap:
        async def send_json(self, data: dict) -> None:
            received.append(data)

    bc.subscribe(Cap())
    app = _build_app(db, registry, bc, NoopNotifier())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(f"/api/hooks/Notification/{token}", json={"message": "x"})
    assert r.status_code == 204
    assert received == []


@pytest.mark.integration
async def test_stop_idempotent_when_already_idle(db: Database) -> None:
    sid, token = await _seed(db, status="idle")
    registry = TokenRegistry()
    registry.register(token, sid)
    bc = InMemoryWsBroadcaster()
    received: list[dict] = []

    class Cap:
        async def send_json(self, data: dict) -> None:
            received.append(data)

    bc.subscribe(Cap())
    app = _build_app(db, registry, bc, NoopNotifier())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(f"/api/hooks/Stop/{token}", json={"reason": "end"})
    assert r.status_code == 204
    assert received == []


@pytest.mark.integration
async def test_status_change_publishes_ws_event(db: Database) -> None:
    sid, token = await _seed(db)
    registry = TokenRegistry()
    registry.register(token, sid)
    bc = InMemoryWsBroadcaster()
    received: list[dict] = []

    class Cap:
        async def send_json(self, data: dict) -> None:
            received.append(data)

    bc.subscribe(Cap())

    app = _build_app(db, registry, bc, NoopNotifier())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        await client.post(f"/api/hooks/Notification/{token}", json={"message": "x"})

    assert len(received) == 1
    assert received[0]["type"] == "session.status"
    assert received[0]["payload"]["status"] == "awaiting_response"


@pytest.mark.integration
async def test_stop_publishes_status_and_stopped_events(db: Database) -> None:
    sid, token = await _seed(db)  # status defaults to "executing"
    registry = TokenRegistry()
    registry.register(token, sid)
    bc = InMemoryWsBroadcaster()
    received: list[dict] = []

    class Cap:
        async def send_json(self, data: dict) -> None:
            received.append(data)

    bc.subscribe(Cap())
    app = _build_app(db, registry, bc, NoopNotifier())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(f"/api/hooks/Stop/{token}", json={"reason": "end"})
    assert r.status_code == 204
    types = [e["type"] for e in received]
    assert "session.status" in types
    assert "session.stopped" in types
