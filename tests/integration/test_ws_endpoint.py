from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from orchestrator.events.broadcaster import InMemoryWsBroadcaster
from orchestrator.hooks.tokens import TokenRegistry, generate_token
from orchestrator.main import create_app
from orchestrator.notifications.notify_send import NoopNotifier
from orchestrator.store.database import Database
from orchestrator.store.models import ClaudeSession, Project, Worktree
from tests.integration.conftest import FakeSessionRuntime


async def _seed_session_with_token(db: Database) -> tuple[str, str]:
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
        sess = ClaudeSession(
            worktree_id=wt.id, status="executing", pid=1, jail_id="j",
            started_at=datetime.now(UTC), hook_token=token,
        )
        s.add(sess)
        await s.commit()
        await s.refresh(sess)
        return sess.id, token


@pytest.mark.integration
async def test_ws_receives_status_event_when_hook_fires(db: Database) -> None:
    sid, token = await _seed_session_with_token(db)
    bc = InMemoryWsBroadcaster()
    registry = TokenRegistry()
    registry.register(token, sid)
    app = create_app(database=db, runtime=FakeSessionRuntime(), ui_dist=None)
    app.state.token_registry = registry
    app.state.ws_broadcaster = bc
    app.state.notifier = NoopNotifier()

    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        r = client.post(f"/api/hooks/Notification/{token}", json={"message": "x"})
        assert r.status_code == 204
        data = ws.receive_json()
    assert data["type"] == "session.status"
    assert data["session_id"] == sid
    assert data["payload"]["status"] == "awaiting_response"


@pytest.mark.integration
async def test_ws_unsubscribes_on_disconnect(db: Database) -> None:
    sid, token = await _seed_session_with_token(db)
    bc = InMemoryWsBroadcaster()
    registry = TokenRegistry()
    registry.register(token, sid)
    app = create_app(database=db, runtime=FakeSessionRuntime(), ui_dist=None)
    app.state.token_registry = registry
    app.state.ws_broadcaster = bc
    app.state.notifier = NoopNotifier()

    with TestClient(app) as client, client.websocket_connect("/ws"):
        pass  # immediate disconnect
    assert len(bc.subscribers) == 0
