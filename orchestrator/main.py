import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from orchestrator.api.projects import router as projects_router
from orchestrator.api.worktrees import router as worktrees_router
from orchestrator.core.health import health_status
from orchestrator.store.database import Database


def create_app(database: Database | None = None, ui_dist: Path | None = None) -> FastAPI:
    app = FastAPI(title="J-arvis Orchestrator", version="0.0.1")
    app.state.database = database

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": health_status()}

    if database is not None:
        app.include_router(projects_router, prefix="/api")
        app.include_router(worktrees_router, prefix="/api")

    if ui_dist is not None and ui_dist.is_dir():
        app.mount("/", StaticFiles(directory=str(ui_dist), html=True), name="ui")

    return app


def _resolve_ui_dist() -> Path | None:
    raw = os.environ.get("UI_DIST", "/app/ui-dist")
    candidate = Path(raw)
    return candidate if candidate.is_dir() else None


app = create_app(ui_dist=_resolve_ui_dist())
