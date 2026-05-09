from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from orchestrator.api.projects import router as projects_router
from orchestrator.api.sessions import router as sessions_router
from orchestrator.api.worktrees import router as worktrees_router
from orchestrator.api.ws import router as ws_router
from orchestrator.config import RuntimeMode, Settings
from orchestrator.core.health import health_status
from orchestrator.events.broadcaster import InMemoryWsBroadcaster
from orchestrator.hooks.router import router as hooks_router
from orchestrator.hooks.tokens import TokenRegistry
from orchestrator.notifications.notify_send import NoopNotifier, NotifySendNotifier
from orchestrator.notifications.sink import NotifierSink
from orchestrator.sandbox.aijail import (
    AiJailRuntime,
    SubprocessProcessOps,
    detect_terminal,
)
from orchestrator.sandbox.null import NullSessionRuntime
from orchestrator.sandbox.runtime import SessionRuntime
from orchestrator.store.database import Database


def create_app(
    database: Database | None = None,
    runtime: SessionRuntime | None = None,
    ui_dist: Path | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if database is not None:
            await database.bootstrap()
        yield

    app = FastAPI(title="J-arvis Orchestrator", version="0.0.1", lifespan=lifespan)
    app.state.database = database
    app.state.runtime = runtime
    app.state.token_registry = getattr(app.state, "token_registry", None)
    app.state.ws_broadcaster = getattr(app.state, "ws_broadcaster", None)
    app.state.notifier = getattr(app.state, "notifier", None)
    app.state.hook_base_url = getattr(app.state, "hook_base_url", None)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": health_status()}

    if database is not None:
        app.include_router(projects_router, prefix="/api")
        app.include_router(worktrees_router, prefix="/api")
        if runtime is not None:
            app.include_router(sessions_router, prefix="/api")
        app.include_router(hooks_router, prefix="/api")
        app.include_router(ws_router)

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
    ui_dist = settings.ui_dist if settings.ui_dist.is_dir() else None

    broadcaster = InMemoryWsBroadcaster()
    registry = TokenRegistry()
    notifier: NotifierSink = (
        NotifySendNotifier() if settings.notify == "on" else NoopNotifier()
    )

    app = create_app(database=database, runtime=runtime, ui_dist=ui_dist)
    app.state.token_registry = registry
    app.state.ws_broadcaster = broadcaster
    app.state.notifier = notifier
    app.state.hook_base_url = settings.effective_hook_base_url
    return app


app = _build_production_app()
