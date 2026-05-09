import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from orchestrator.core.health import health_status


def create_app(ui_dist: Path | None = None) -> FastAPI:
    app = FastAPI(title="J-arvis Orchestrator", version="0.0.1")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": health_status()}

    if ui_dist is not None and ui_dist.is_dir():
        app.mount("/", StaticFiles(directory=str(ui_dist), html=True), name="ui")

    return app


def _resolve_ui_dist() -> Path | None:
    raw = os.environ.get("UI_DIST", "/app/ui-dist")
    candidate = Path(raw)
    return candidate if candidate.is_dir() else None


app = create_app(_resolve_ui_dist())
