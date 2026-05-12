"""F8.d: create/update/discard_task via JSON-RPC."""
import json
from pathlib import Path
from typing import Any

from httpx import ASGITransport, AsyncClient

from orchestrator.main import create_app
from orchestrator.store.database import Database
from tests.integration.conftest import FakeSessionRuntime, _make_repo

_MCP_HEADERS_BASE = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "MCP-Protocol-Version": "2025-11-25",
}


def _headers(token: str) -> dict[str, str]:
    return {**_MCP_HEADERS_BASE, "Authorization": f"Bearer {token}"}


async def _initialize(c: AsyncClient, headers: dict[str, str]) -> None:
    """MCP requires initialize handshake before tools/list or tools/call."""
    r = await c.post(
        "/api/mcp/",
        json={
            "jsonrpc": "2.0", "id": 0,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text


async def _call_tool(
    c: AsyncClient,
    headers: dict[str, str],
    name: str,
    args: dict[str, Any],
) -> dict[str, Any]:
    r = await c.post(
        "/api/mcp/",
        json={
            "jsonrpc": "2.0", "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": args},
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    out: dict[str, Any] = r.json()
    return out


async def test_create_task_via_mcp_basic(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    token = app.state.master_mcp_token
    async with (
        AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c,
        app.router.lifespan_context(app),
    ):
        await _initialize(c, _headers(token))
        proj = (await c.post(
            "/api/projects",
            json={"name": "p", "path": str(repo)},
        )).json()
        result = await _call_tool(c, _headers(token), "create_task", {
            "project_id": proj["id"], "title": "from MCP",
        })
    parsed = json.loads(result["result"]["content"][0]["text"])
    assert parsed["title"] == "from MCP"
    assert parsed["project_id"] == proj["id"]


async def test_create_task_with_template(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    token = app.state.master_mcp_token
    async with (
        AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c,
        app.router.lifespan_context(app),
    ):
        await _initialize(c, _headers(token))
        proj = (await c.post(
            "/api/projects", json={"name": "p", "path": str(repo)},
        )).json()
        result = await _call_tool(c, _headers(token), "create_task", {
            "project_id": proj["id"],
            "title": "Add dark mode",
            "template": "frontend",
        })
    parsed = json.loads(result["result"]["content"][0]["text"])
    assert parsed["template"] == "frontend"
    assert parsed["permission_profile"] == "yolo"
    # Branch usa prefix do template + slug do title. Weak assert pra
    # tolerar variações no slugify_for_branch entre versões.
    assert parsed["branch"].startswith("feat-ui/")
    assert "dark" in parsed["branch"] and "mode" in parsed["branch"]


async def test_create_task_invalid_template_jsonrpc_error(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    token = app.state.master_mcp_token
    async with (
        AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c,
        app.router.lifespan_context(app),
    ):
        await _initialize(c, _headers(token))
        proj = (await c.post(
            "/api/projects", json={"name": "p", "path": str(repo)},
        )).json()
        result = await _call_tool(c, _headers(token), "create_task", {
            "project_id": proj["id"], "title": "t", "template": "ghost",
        })
    # JSON-RPC error response — either top-level "error" or result.isError
    assert "error" in result or result.get("result", {}).get("isError")


async def test_update_task_state(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    token = app.state.master_mcp_token
    async with (
        AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c,
        app.router.lifespan_context(app),
    ):
        await _initialize(c, _headers(token))
        proj = (await c.post(
            "/api/projects", json={"name": "p", "path": str(repo)},
        )).json()
        task = (await c.post(
            "/api/tasks", json={"project_id": proj["id"], "title": "t"},
        )).json()
        result = await _call_tool(c, _headers(token), "update_task", {
            "task_id": task["id"], "state": "ready",
        })
    parsed = json.loads(result["result"]["content"][0]["text"])
    assert parsed["state"] == "ready"


async def test_discard_task(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    token = app.state.master_mcp_token
    async with (
        AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c,
        app.router.lifespan_context(app),
    ):
        await _initialize(c, _headers(token))
        proj = (await c.post(
            "/api/projects", json={"name": "p", "path": str(repo)},
        )).json()
        task = (await c.post(
            "/api/tasks", json={"project_id": proj["id"], "title": "t"},
        )).json()
        result = await _call_tool(c, _headers(token), "discard_task", {
            "task_id": task["id"],
        })
    parsed = json.loads(result["result"]["content"][0]["text"])
    assert parsed["state"] == "discarded"
