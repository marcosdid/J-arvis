from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.main import create_app
from orchestrator.store.database import Database


def _make_repo(parent: Path, name: str) -> Path:
    repo = parent / name
    (repo / ".git").mkdir(parents=True)
    return repo


@pytest.mark.integration
async def test_create_and_list_projects(db: Database, tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, "myrepo")
    app = create_app(database=db, ui_dist=None)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        create = await client.post("/api/projects", json={"name": "myrepo", "path": str(repo)})
        assert create.status_code == 201
        created = create.json()
        assert created["name"] == "myrepo"
        assert created["path"] == str(repo)
        assert created["id"]
        assert created["created_at"]

        listing = await client.get("/api/projects")
        assert listing.status_code == 200
        projects = listing.json()
        assert len(projects) == 1
        assert projects[0]["id"] == created["id"]


@pytest.mark.integration
async def test_create_project_rejects_missing_path(db: Database, tmp_path: Path) -> None:
    app = create_app(database=db, ui_dist=None)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/projects",
            json={"name": "ghost", "path": str(tmp_path / "does-not-exist")},
        )
    assert response.status_code == 422
    assert "path" in response.json()["detail"].lower()


@pytest.mark.integration
async def test_create_project_rejects_non_git_path(db: Database, tmp_path: Path) -> None:
    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()
    app = create_app(database=db, ui_dist=None)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/projects",
            json={"name": "plain", "path": str(not_a_repo)},
        )
    assert response.status_code == 422
    assert "git" in response.json()["detail"].lower()


@pytest.mark.integration
async def test_delete_project(db: Database, tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, "todelete")
    app = create_app(database=db, ui_dist=None)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        create_resp = await client.post(
            "/api/projects", json={"name": "todelete", "path": str(repo)}
        )
        created = create_resp.json()
        delete = await client.delete(f"/api/projects/{created['id']}")
        assert delete.status_code == 204

        listing = await client.get("/api/projects")
        assert listing.json() == []


@pytest.mark.integration
async def test_delete_unknown_project_returns_404(db: Database) -> None:
    app = create_app(database=db, ui_dist=None)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.delete("/api/projects/nope")
    assert response.status_code == 404


@pytest.mark.integration
async def test_create_project_with_duplicate_path_returns_409(
    db: Database, tmp_path: Path
) -> None:
    repo = _make_repo(tmp_path, "dup")
    app = create_app(database=db, ui_dist=None)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        first = await client.post("/api/projects", json={"name": "dup", "path": str(repo)})
        assert first.status_code == 201

        second = await client.post(
            "/api/projects", json={"name": "dup-again", "path": str(repo)}
        )
    assert second.status_code == 409
    assert "exists" in second.json()["detail"].lower()
