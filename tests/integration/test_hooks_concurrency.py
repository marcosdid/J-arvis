import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.events.broadcaster import InMemoryWsBroadcaster
from orchestrator.hooks.tokens import TokenRegistry
from orchestrator.main import create_app
from orchestrator.notifications.notify_send import NoopNotifier
from orchestrator.store.database import Database
from orchestrator.store.models import ClaudeSession
from tests.integration.conftest import FakeSessionRuntime
from tests.integration.test_hooks_routes import _seed


@pytest.mark.integration
async def test_concurrent_hooks_do_not_corrupt_state(db: Database) -> None:
    sid, token = await _seed(db)
    registry = TokenRegistry()
    registry.register(token, sid)
    app = create_app(database=db, runtime=FakeSessionRuntime(), ui_dist=None)
    app.state.token_registry = registry
    app.state.ws_broadcaster = InMemoryWsBroadcaster()
    app.state.notifier = NoopNotifier()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        await asyncio.gather(*[
            client.post(f"/api/hooks/Notification/{token}", json={"message": "x"})
            for _ in range(10)
        ])

    async with db.session() as s:
        row = await s.get(ClaudeSession, sid)
        assert row.status == "awaiting_response"
        assert row.last_hook_at is not None
