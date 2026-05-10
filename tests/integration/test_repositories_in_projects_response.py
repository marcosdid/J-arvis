"""F5.g: GET /projects includes repositories array per project."""
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from orchestrator.main import create_app
from orchestrator.store.database import Database
from tests.integration.conftest import _make_multi_repo, _make_repo


async def test_get_projects_includes_repositories(db: Database, tmp_path: Path) -> None:
    repo_a = _make_repo(tmp_path, name="repo_a")
    repo_b = _make_multi_repo(tmp_path, ["api", "web"], name="repo_b")
    app = create_app(database=db, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        await client.post("/api/projects", json={"name": "A", "path": str(repo_a)})
        await client.post("/api/projects", json={"name": "B", "path": str(repo_b)})
        listing = await client.get("/api/projects")

    assert listing.status_code == 200
    projects = listing.json()
    by_name = {p["name"]: p for p in projects}

    assert len(by_name["A"]["repositories"]) == 1
    assert by_name["A"]["repositories"][0]["sub_path"] == "."
    assert by_name["A"]["repositories"][0]["name"] == "A"

    sub_paths = sorted(r["sub_path"] for r in by_name["B"]["repositories"])
    assert sub_paths == ["api", "web"]
