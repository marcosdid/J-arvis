"""F8.c: wrapper ASGI pro MCP server.

Builds a sub-Starlette app that:
1. Validates `Authorization: Bearer <token>` against a fixed token.
2. Populates the local deps contextvar (see ``orchestrator.mcp.server``) from
   the parent FastAPI's `app.state`, so tools can grab `db`/`catalog`/etc.
3. Delegates the ASGI request to `StreamableHTTPSessionManager.handle_request`.

The session manager's `.run()` async context MUST be entered as part of the
host app's lifespan — see the integration in ``orchestrator/main.py``.
"""
from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator, Awaitable, Callable

from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount
from starlette.types import Receive, Scope, Send

from orchestrator.mcp.server import McpDeps, reset_deps, set_deps


def build_mcp_app(
    server: Server,
    state_provider: Callable[[Scope], McpDeps],
    auth: Callable[[dict[str, str]], Awaitable[str | None]],
) -> Starlette:
    """Return a Starlette ASGI app that mounts the MCP server.

    Parameters
    ----------
    server:
        The configured MCP `Server` instance (with `@list_tools`/`@call_tool`).
    state_provider:
        Callable receiving the raw ASGI scope; returns `McpDeps` populated
        from the parent FastAPI's `app.state`.
    auth:
        Async callable receiving the request headers dict (lower-cased keys);
        returns ``None`` on success, or an error string on auth failure (used
        as the JSON `error` field; status is always 401 on failure).
    """
    session_manager = StreamableHTTPSessionManager(
        app=server,
        json_response=True,
        stateless=True,
    )

    async def asgi_app(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":  # pragma: no cover
            return
        headers = {
            k.decode("latin-1").lower(): v.decode("latin-1")
            for k, v in scope.get("headers", [])
        }
        err = await auth(headers)
        if err is not None:
            response = JSONResponse({"error": err}, status_code=401)
            await response(scope, receive, send)
            return

        deps = state_provider(scope)
        token = set_deps(deps)
        try:
            await session_manager.handle_request(scope, receive, send)
        finally:
            reset_deps(token)

    @contextlib.asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            yield

    return Starlette(
        lifespan=lifespan,
        routes=[Mount("/", app=asgi_app)],
    )


__all__ = ["build_mcp_app"]
