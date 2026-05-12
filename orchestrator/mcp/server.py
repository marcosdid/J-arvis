"""F8.c: MCP server com tools que manipulam o banco do J-arvis.

Step 0 SDK spike findings (mcp==1.27.1):
- `mcp.server.Server` (alias of `mcp.server.lowlevel.Server`).
- Decorators confirmed: `@server.list_tools()` and `@server.call_tool()`.
- `Server.request_context` (property) → `RequestContext` dataclass; backed by
  contextvar `mcp.server.lowlevel.server.request_ctx`. Setting it directly is
  not supported in stable API.
- HTTP transport: `mcp.server.streamable_http_manager.StreamableHTTPSessionManager`
  with `.handle_request(scope, receive, send)` (ASGI) and `.run()` (async ctx
  manager that MUST be entered as part of the host app's lifespan).
- The transport injects the raw Starlette `Request` into `RequestContext.request`
  via `ServerMessageMetadata.request_context`, so tools COULD reach back to
  `request.app.state` — but `request.app` is the inner Starlette sub-app, not
  the parent FastAPI. To avoid that ladder we wire deps via a local contextvar
  (`_DEPS_CTX`) populated by the ASGI auth middleware before delegating to the
  session manager.
"""
from __future__ import annotations

import contextvars
import json
from dataclasses import dataclass
from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool

from orchestrator.core.catalog import Catalog
from orchestrator.core.git import GitWorktreeOps
from orchestrator.core.projects import get_project, list_projects
from orchestrator.core.tasks import (
    InvalidTemplateError,
    create_task,
    get_task,
    list_tasks,
    update_task,
)
from orchestrator.events.broadcaster import WsBroadcaster
from orchestrator.events.envelope import WsEvent


@dataclass
class McpDeps:
    """Request-scoped dependencies injected by the ASGI mount layer.

    `db` is a `Database` (not an `AsyncSession`) because tools open per-call
    sessions via `db.session()` — keeps each tool transactional and matches
    the FastAPI DI pattern used by the rest of the API.
    """

    db: Any  # orchestrator.store.database.Database — Any to avoid circular import
    catalog: Catalog | None
    broadcaster: WsBroadcaster | None
    git_ops: GitWorktreeOps | None


_DEPS_CTX: contextvars.ContextVar[McpDeps] = contextvars.ContextVar("jarvis_mcp_deps")


def set_deps(deps: McpDeps) -> contextvars.Token[McpDeps]:
    """Set the request-scoped deps. Returns the token for `reset_deps`."""
    return _DEPS_CTX.set(deps)


def reset_deps(token: contextvars.Token[McpDeps]) -> None:
    _DEPS_CTX.reset(token)


def current_deps() -> McpDeps:
    return _DEPS_CTX.get()


mcp_server: Server = Server("j-arvis-master")


# SDK ships untyped decorators (mcp 1.27.1); ignore mypy noise
@mcp_server.list_tools()  # type: ignore[no-untyped-call,untyped-decorator]
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="list_projects",
            description="List all projects with their ids, names, and paths.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_project",
            description="Get a project by id.",
            inputSchema={
                "type": "object",
                "required": ["project_id"],
                "properties": {"project_id": {"type": "string"}},
            },
        ),
        Tool(
            name="list_tasks",
            description="List tasks, optionally filtered by project and/or state.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "state": {
                        "type": "string",
                        "enum": [
                            "idea", "ready", "in_progress",
                            "review", "done", "discarded",
                        ],
                    },
                },
            },
        ),
        Tool(
            name="get_task",
            description="Get a task by id.",
            inputSchema={
                "type": "object",
                "required": ["task_id"],
                "properties": {"task_id": {"type": "string"}},
            },
        ),
        Tool(
            name="create_task",
            description=(
                "Create a new task. Optionally with a template "
                "(frontend/backend/refactor/bugfix) which auto-derives "
                "permission_profile and branch prefix."
            ),
            inputSchema={
                "type": "object",
                "required": ["project_id", "title"],
                "properties": {
                    "project_id": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "template": {
                        "type": "string",
                        "enum": ["frontend", "backend", "refactor", "bugfix"],
                    },
                    "branch": {"type": "string"},
                },
            },
        ),
        Tool(
            name="update_task",
            description=(
                "Update task fields. State transitions follow F4 state "
                "machine. NOTE: template é snapshot-at-create (F7) — não "
                "editável aqui."
            ),
            inputSchema={
                "type": "object",
                "required": ["task_id"],
                "properties": {
                    "task_id": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "state": {"type": "string"},
                    "branch": {"type": "string"},
                },
            },
        ),
        Tool(
            name="discard_task",
            description="Move task to discarded state.",
            inputSchema={
                "type": "object",
                "required": ["task_id"],
                "properties": {"task_id": {"type": "string"}},
            },
        ),
    ]


async def _list_projects_tool(database: Any) -> str:
    async with database.session() as s:
        rows = await list_projects(s)
    return json.dumps([_serialize_project(r) for r in rows])


async def _get_project_tool(database: Any, project_id: str) -> str:
    async with database.session() as s:
        row = await get_project(s, project_id)
    return json.dumps(_serialize_project(row))


async def _list_tasks_tool(
    database: Any,
    project_id: str | None,
    state: str | None,
) -> str:
    async with database.session() as s:
        rows = await list_tasks(
            s,
            project_ids=[project_id] if project_id else None,
            state=state,
        )
    return json.dumps([_serialize_task(r) for r in rows])


async def _get_task_tool(database: Any, task_id: str) -> str:
    async with database.session() as s:
        row = await get_task(s, task_id)
    return json.dumps(_serialize_task(row))


async def _broadcast_task_created(
    broadcaster: WsBroadcaster | None,
    task: Any,
) -> None:
    if broadcaster is None:
        return
    await broadcaster.publish(WsEvent.task_created(
        task_id=task.id,
        project_id=task.project_id,
        title=task.title,
        state=task.state,
    ))


async def _broadcast_task_updated(
    broadcaster: WsBroadcaster | None,
    task: Any,
    previous_state: str | None,
) -> None:
    if broadcaster is None:
        return
    await broadcaster.publish(WsEvent.task_updated(
        task_id=task.id,
        project_id=task.project_id,
        title=task.title,
        new_state=task.state,
        previous_state=previous_state or task.state,
    ))


async def _create_task_tool(
    database: Any,
    catalog: Catalog | None,
    broadcaster: WsBroadcaster | None,
    arguments: dict[str, Any],
) -> str:
    if catalog is None:
        raise ValueError("catalog not configured for MCP server")
    async with database.session() as s:
        try:
            task = await create_task(s, catalog=catalog, **arguments)
        except InvalidTemplateError as exc:
            raise ValueError(
                f"template_not_in_catalog: valid={exc.valid_templates}",
            ) from exc
    await _broadcast_task_created(broadcaster, task)
    return json.dumps(_serialize_task(task))


async def _update_task_tool(
    database: Any,
    broadcaster: WsBroadcaster | None,
    arguments: dict[str, Any],
) -> str:
    # F7: template é snapshot-at-create — não editável. core.tasks.update_task
    # aceita apenas title?, description?, state?, branch?. Sem catalog kwarg.
    task_id = arguments.pop("task_id")
    async with database.session() as s:
        task, prev_state = await update_task(s, task_id, **arguments)
    await _broadcast_task_updated(broadcaster, task, prev_state)
    return json.dumps(_serialize_task(task))


async def _discard_task_tool(
    database: Any,
    broadcaster: WsBroadcaster | None,
    task_id: str,
) -> str:
    async with database.session() as s:
        task, prev_state = await update_task(s, task_id, state="discarded")
    await _broadcast_task_updated(broadcaster, task, prev_state)
    return json.dumps(_serialize_task(task))


# SDK ships untyped decorators (mcp 1.27.1); ignore mypy noise
@mcp_server.call_tool()  # type: ignore[untyped-decorator]
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Dispatch JSON-RPC tool calls. Deps come from the request contextvar
    populated by the ASGI mount middleware."""
    deps = current_deps()
    database = deps.db

    if name == "list_projects":
        text = await _list_projects_tool(database)
    elif name == "get_project":
        text = await _get_project_tool(database, arguments["project_id"])
    elif name == "list_tasks":
        text = await _list_tasks_tool(
            database,
            arguments.get("project_id"),
            arguments.get("state"),
        )
    elif name == "get_task":
        text = await _get_task_tool(database, arguments["task_id"])
    elif name == "create_task":
        text = await _create_task_tool(
            database, deps.catalog, deps.broadcaster, arguments,
        )
    elif name == "update_task":
        text = await _update_task_tool(database, deps.broadcaster, arguments)
    elif name == "discard_task":
        text = await _discard_task_tool(
            database, deps.broadcaster, arguments["task_id"],
        )
    else:
        raise ValueError(f"unknown tool {name!r}")

    return [TextContent(type="text", text=text)]


def _serialize_project(p: Any) -> dict[str, Any]:
    return {"id": p.id, "name": p.name, "path": p.path}


def _serialize_task(t: Any) -> dict[str, Any]:
    return {
        "id": t.id,
        "project_id": t.project_id,
        "title": t.title,
        "description": t.description,
        "state": t.state,
        "branch": t.branch,
        "template": t.template,
        "permission_profile": t.permission_profile,
    }
