"""F8.c: POST /api/mcp via JSON-RPC tools/list e tools/call (read-only)."""
import json as _json

from httpx import ASGITransport, AsyncClient

from orchestrator.main import create_app
from orchestrator.store.database import Database
from tests.integration.conftest import FakeSessionRuntime

_MCP_HEADERS_BASE = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "MCP-Protocol-Version": "2025-11-25",
}


def _headers(token: str) -> dict[str, str]:
    return {**_MCP_HEADERS_BASE, "Authorization": f"Bearer {token}"}


def _rpc(method: str, params: dict | None = None, _id: int = 1) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": _id,
        "method": method,
        "params": params or {},
    }


async def _initialize(client: AsyncClient, token: str) -> None:
    """Stateless mode still requires the initialize handshake before tools/*.
    No session id is returned (stateless), but the call MUST succeed first."""
    r = await client.post(
        "/api/mcp/",
        json=_rpc(
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0"},
            },
        ),
        headers=_headers(token),
    )
    assert r.status_code == 200, r.text


async def test_tools_list_returns_read_tools(
    db: Database, runtime: FakeSessionRuntime,
) -> None:
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    token = app.state.master_mcp_token
    async with (
        AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c,
        app.router.lifespan_context(app),
    ):
        await _initialize(c, token)
        r = await c.post(
            "/api/mcp/",
            json=_rpc("tools/list"),
            headers=_headers(token),
        )
    assert r.status_code == 200, r.text
    body = r.json()
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "list_projects" in tool_names
    assert "get_task" in tool_names
    assert set(tool_names) == {
        # F8.c read-only
        "list_projects", "get_project", "list_tasks", "get_task",
        # F8.d write tools
        "create_task", "update_task", "discard_task",
    }


async def test_tools_call_list_projects_empty(
    db: Database, runtime: FakeSessionRuntime,
) -> None:
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    token = app.state.master_mcp_token
    async with (
        AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c,
        app.router.lifespan_context(app),
    ):
        await _initialize(c, token)
        r = await c.post(
            "/api/mcp/",
            json=_rpc(
                "tools/call",
                {"name": "list_projects", "arguments": {}},
            ),
            headers=_headers(token),
        )
    assert r.status_code == 200, r.text
    body = r.json()
    content = body["result"]["content"]
    parsed = _json.loads(content[0]["text"])
    assert parsed == []


async def test_tools_call_missing_auth_401(
    db: Database, runtime: FakeSessionRuntime,
) -> None:
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with (
        AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c,
        app.router.lifespan_context(app),
    ):
        r = await c.post(
            "/api/mcp/",
            json=_rpc("tools/list"),
            headers=_MCP_HEADERS_BASE,
        )
    assert r.status_code == 401


async def test_tools_call_invalid_token_401(
    db: Database, runtime: FakeSessionRuntime,
) -> None:
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with (
        AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c,
        app.router.lifespan_context(app),
    ):
        r = await c.post(
            "/api/mcp/",
            json=_rpc("tools/list"),
            headers=_headers("wrong-token"),
        )
    assert r.status_code == 401
