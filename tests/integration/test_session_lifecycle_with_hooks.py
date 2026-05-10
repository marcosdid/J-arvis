from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.events.broadcaster import InMemoryWsBroadcaster
from orchestrator.hooks.tokens import TokenRegistry
from orchestrator.main import create_app
from orchestrator.notifications.notify_send import NoopNotifier
from orchestrator.store.database import Database
from tests.integration.conftest import FakeSessionRuntime
from tests.integration.test_sessions_api import (
    _create_project_and_worktree,
    _make_repo,
)


@pytest.mark.integration
async def test_lifecycle_with_hooks(db: Database, tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    runtime = FakeSessionRuntime()
    bc = InMemoryWsBroadcaster()
    registry = TokenRegistry()
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    app.state.token_registry = registry
    app.state.ws_broadcaster = bc
    app.state.notifier = NoopNotifier()
    app.state.hook_base_url = "http://localhost:8765"

    received: list[dict] = []

    class Cap:
        async def send_json(self, data: dict) -> None:
            received.append(data)

    bc.subscribe(Cap())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        _, wt_id = await _create_project_and_worktree(client, repo)
        sess = (await client.post("/api/sessions", json={"worktree_id": wt_id})).json()
        sid = sess["id"]
        token = registry.find_token_for(sid)
        assert token is not None

        await client.post(f"/api/hooks/Notification/{token}", json={"message": "?"})
        await client.post(f"/api/hooks/Stop/{token}", json={"reason": "end"})
        await client.post(f"/api/sessions/{sid}/stop")

    types = [e["type"] for e in received]
    # POST /api/sessions now emits task.created for the implicit quick-session task.
    assert "task.created" in types
    session_types = [t for t in types if t.startswith("session.")]
    assert session_types == ["session.status", "session.status", "session.stopped"]
    assert registry.resolve(token) is None
