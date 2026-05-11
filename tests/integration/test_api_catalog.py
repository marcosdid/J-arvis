"""F7.b: GET /api/catalog."""
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.main import create_app
from orchestrator.store.database import Database
from tests.integration.conftest import FakeSessionRuntime


@pytest.mark.integration
async def test_get_catalog_returns_full_structure(
    db: Database, runtime: FakeSessionRuntime,
) -> None:
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/catalog")
    assert r.status_code == 200
    body: dict[str, Any] = r.json()
    assert body["version"] == "1"
    assert body["fallback_permission_profile"] == "yolo"
    assert isinstance(body["permission_profiles"], list)
    assert isinstance(body["templates"], list)
    profile_names = [p["name"] for p in body["permission_profiles"]]
    assert profile_names == sorted(profile_names)  # ordem alfabética
    assert set(profile_names) == {"yolo", "default", "read-only"}
    template_names = [t["name"] for t in body["templates"]]
    assert set(template_names) == {"frontend", "backend", "refactor", "bugfix"}
    yolo = next(p for p in body["permission_profiles"] if p["name"] == "yolo")
    assert yolo["claude_args"] == ["--dangerously-skip-permissions"]
    assert isinstance(yolo["description"], str)
    fe = next(t for t in body["templates"] if t["name"] == "frontend")
    assert fe["default_permission_profile"] == "yolo"
    assert fe["branch_prefix"] == "feat-ui/"


@pytest.mark.integration
async def test_get_catalog_no_auth_required(
    db: Database, runtime: FakeSessionRuntime,
) -> None:
    """Catálogo é leitura pública (read-only, sem dados sensíveis)."""
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/catalog")
    assert r.status_code == 200
