import os
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from starlette.types import Scope

from orchestrator.api.bootstrap import router as bootstrap_router
from orchestrator.api.catalog import router as catalog_router
from orchestrator.api.projects import router as projects_router
from orchestrator.api.runs import run_router
from orchestrator.api.runs import task_router as runs_task_router
from orchestrator.api.sessions import router as sessions_router
from orchestrator.api.tasks import router as tasks_router
from orchestrator.api.worktrees import router as worktrees_router
from orchestrator.api.worktrees import worktree_router
from orchestrator.api.ws import router as ws_router
from orchestrator.config import RuntimeMode, Settings
from orchestrator.core.catalog import load_catalog
from orchestrator.core.git import SubprocessGitWorktreeOps
from orchestrator.core.health import health_status
from orchestrator.core.port_allocator import PortAllocator
from orchestrator.core.runs import cleanup_orphan_runs_at_startup
from orchestrator.events.broadcaster import InMemoryWsBroadcaster
from orchestrator.hooks.router import router as hooks_router
from orchestrator.hooks.tokens import TokenRegistry
from orchestrator.mcp.asgi_mount import build_mcp_app
from orchestrator.mcp.server import McpDeps, mcp_server
from orchestrator.notifications.notify_send import NoopNotifier, NotifySendNotifier
from orchestrator.notifications.sink import NotifierSink
from orchestrator.sandbox.aijail import (
    AiJailRuntime,
    SubprocessProcessOps,
    detect_terminal,
)
from orchestrator.sandbox.docker_ops import SubprocessDockerOps
from orchestrator.sandbox.null import NullSessionRuntime
from orchestrator.sandbox.runtime import SessionRuntime
from orchestrator.store.database import Database


def create_app(
    database: Database | None = None,
    runtime: SessionRuntime | None = None,
    ui_dist: Path | None = None,
) -> FastAPI:
    # F8.c: build sub-app first so we can chain its lifespan.
    async def _verify_mcp_auth(headers: dict[str, str]) -> str | None:
        auth_header = headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return "missing bearer token"
        if auth_header[7:] != app.state.master_mcp_token:
            return "invalid MCP token"
        return None

    def _state_provider(_scope: Scope) -> McpDeps:
        return McpDeps(
            db=app.state.database,
            catalog=app.state.catalog,
            broadcaster=app.state.ws_broadcaster,
            git_ops=app.state.git_ops,
        )

    mcp_asgi = build_mcp_app(
        server=mcp_server,
        state_provider=_state_provider,
        auth=_verify_mcp_auth,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if database is not None:
            await database.bootstrap()
            # Restart-recovery (F6): marca runs com `ended_at IS NULL` como
            # `stopped` + best-effort kill+rm de containers/network/ports.
            # Sem isso, partial unique bloqueia novos POST /runs e portas
            # ficam presas. docker_ops/port_allocator são sempre wirados
            # via create_app defaults (SubprocessDockerOps + PortAllocator).
            async with database.session() as s:
                await cleanup_orphan_runs_at_startup(
                    s, _app.state.docker_ops, _app.state.port_allocator,
                )
        # F8.c: chain the MCP sub-app lifespan (StreamableHTTPSessionManager.run()).
        async with mcp_asgi.router.lifespan_context(mcp_asgi):
            yield

    app = FastAPI(title="J-arvis Orchestrator", version="0.0.1", lifespan=lifespan)
    app.state.master_mcp_token = getattr(
        app.state, "master_mcp_token", None,
    ) or secrets.token_urlsafe(32)
    app.state.database = database
    app.state.runtime = runtime
    app.state.token_registry = getattr(app.state, "token_registry", None)
    app.state.ws_broadcaster = getattr(app.state, "ws_broadcaster", None)
    app.state.notifier = getattr(app.state, "notifier", None)
    app.state.hook_base_url = getattr(app.state, "hook_base_url", None)
    app.state.git_ops = getattr(app.state, "git_ops", None) or SubprocessGitWorktreeOps()
    app.state.docker_ops = getattr(app.state, "docker_ops", None) or SubprocessDockerOps()
    app.state.port_allocator = (
        getattr(app.state, "port_allocator", None) or PortAllocator()
    )
    catalog_path = Path(__file__).parent / "config" / "catalog.yml"
    app.state.catalog = (
        getattr(app.state, "catalog", None) or load_catalog(catalog_path)
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": health_status()}

    if database is not None:
        app.include_router(catalog_router, prefix="/api")
        app.include_router(projects_router, prefix="/api")
        app.include_router(worktrees_router, prefix="/api")
        app.include_router(worktree_router, prefix="/api")
        app.include_router(tasks_router, prefix="/api")
        app.include_router(runs_task_router, prefix="/api")
        app.include_router(run_router, prefix="/api")
        if runtime is not None:
            app.include_router(sessions_router, prefix="/api")
            app.include_router(bootstrap_router, prefix="/api")
        app.include_router(hooks_router, prefix="/api")
        app.include_router(ws_router)

        if os.environ.get("JARVIS_DEBUG") == "1":  # pragma: no cover
            @app.get("/api/_debug/token/{session_id}")
            async def _debug_token(session_id: str, request: Request) -> dict[str, str]:
                registry = request.app.state.token_registry
                token = registry.find_token_for(session_id)
                if token is None:
                    raise HTTPException(status_code=404)
                return {"token": token}

    # F8.c: MCP server mounted before any catch-all UI static files.
    app.mount("/api/mcp", mcp_asgi)

    if ui_dist is not None and ui_dist.is_dir():
        app.mount("/", StaticFiles(directory=str(ui_dist), html=True), name="ui")

    return app


def build_runtime(mode: RuntimeMode) -> SessionRuntime:
    if mode == "aijail":
        return AiJailRuntime(detect_terminal, SubprocessProcessOps())
    return NullSessionRuntime()


def _build_production_app() -> FastAPI:  # pragma: no cover
    settings = Settings()
    database = Database(settings.database_url)
    runtime = build_runtime(settings.runtime)
    ui_dist = settings.effective_ui_dist

    broadcaster = InMemoryWsBroadcaster()
    registry = TokenRegistry()
    notifier: NotifierSink = (
        NotifySendNotifier() if settings.notify == "on" else NoopNotifier()
    )
    git_ops = SubprocessGitWorktreeOps()

    app = create_app(database=database, runtime=runtime, ui_dist=ui_dist)
    app.state.token_registry = registry
    app.state.ws_broadcaster = broadcaster
    app.state.notifier = notifier
    app.state.hook_base_url = settings.effective_hook_base_url
    app.state.git_ops = git_ops
    return app


app = _build_production_app()
