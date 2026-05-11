"""F7.c: POST /api/tasks com template."""
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from orchestrator.main import create_app
from orchestrator.store.database import Database
from tests.integration.conftest import FakeSessionRuntime, _make_repo


async def test_post_task_with_template_frontend(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        proj = (await c.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        r = await c.post("/api/tasks", json={
            "project_id": proj["id"],
            "title": "Add dark mode toggle",
            "template": "frontend",
        })
    assert r.status_code == 201
    body = r.json()
    assert body["template"] == "frontend"
    assert body["permission_profile"] == "yolo"
    assert body["branch"] == "feat-ui/add-dark-mode-toggle"


async def test_post_task_without_template_back_compat(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        proj = (await c.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        r = await c.post("/api/tasks", json={"project_id": proj["id"], "title": "t"})
    assert r.status_code == 201
    body = r.json()
    assert body["template"] is None
    assert body["permission_profile"] is None
    assert body["branch"] is None


async def test_post_task_invalid_template_422(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        proj = (await c.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        r = await c.post("/api/tasks", json={
            "project_id": proj["id"], "title": "t", "template": "ghost",
        })
    assert r.status_code == 422
    body = r.json()
    assert body["detail"]["error"] == "template_not_in_catalog"
    assert set(body["detail"]["valid_templates"]) == {"frontend", "backend", "refactor", "bugfix"}


async def test_post_task_template_with_branch_override(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        proj = (await c.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        r = await c.post("/api/tasks", json={
            "project_id": proj["id"], "title": "anything",
            "template": "frontend", "branch": "custom-branch",
        })
    assert r.status_code == 201
    body = r.json()
    assert body["template"] == "frontend"
    assert body["permission_profile"] == "yolo"
    assert body["branch"] == "custom-branch"


async def test_post_task_template_with_degenerate_title_422(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        proj = (await c.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        r = await c.post("/api/tasks", json={
            "project_id": proj["id"], "title": "!!!", "template": "frontend",
        })
    assert r.status_code == 422
    assert "slugify" in r.text.lower() or "slug" in r.text.lower()


async def test_post_task_template_duplicate_branch_accepted(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    """POST aceita branches que slugificam pro mesmo prefix+slug. Collision
    é detectada só em start_session (CwdAlreadyExistsError de F5)."""
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        proj = (await c.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        r1 = await c.post("/api/tasks", json={
            "project_id": proj["id"], "title": "Fix logout", "template": "bugfix",
        })
        r2 = await c.post("/api/tasks", json={
            "project_id": proj["id"], "title": "Fix logout", "template": "bugfix",
        })
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["branch"] == r2.json()["branch"] == "fix/fix-logout"
