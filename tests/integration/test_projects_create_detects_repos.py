"""F5.g: POST /projects detects repositories via detect_repos.

- Monorepo: 1 repository row, sub_path='.', name=user-given project name.
- Multi-repo: N repository rows, alphabetic, with each sub-dir name.
- Empty (no .git): 422 NoGitReposError.
"""
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from orchestrator.main import create_app
from orchestrator.store.database import Database
from tests.integration.conftest import _make_multi_repo, _make_repo


async def test_create_monorepo_returns_single_repo(db: Database, tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        r = await client.post("/api/projects", json={"name": "myproj", "path": str(repo)})
    assert r.status_code == 201
    body = r.json()
    repos = body["repositories"]
    assert len(repos) == 1
    assert repos[0]["sub_path"] == "."
    assert repos[0]["name"] == "myproj"


async def test_create_multi_repo_returns_n_repos_alphabetic(
    db: Database, tmp_path: Path,
) -> None:
    base = _make_multi_repo(tmp_path, ["zeta", "alpha", "mid"])
    app = create_app(database=db, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        r = await client.post("/api/projects", json={"name": "umbrella", "path": str(base)})
    assert r.status_code == 201
    repos = r.json()["repositories"]
    assert [r["sub_path"] for r in repos] == ["alpha", "mid", "zeta"]
    assert [r["name"] for r in repos] == ["alpha", "mid", "zeta"]


async def test_create_no_git_repos_returns_422(db: Database, tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    app = create_app(database=db, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        r = await client.post("/api/projects", json={"name": "bad", "path": str(empty)})
    assert r.status_code == 422
