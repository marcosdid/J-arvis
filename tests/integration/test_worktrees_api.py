import os
import subprocess
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.main import create_app
from orchestrator.store.database import Database


def _git_env() -> dict[str, str]:
    return {
        **os.environ,
        "GIT_AUTHOR_NAME": "test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    }


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        env=_git_env(),
    )


def _make_repo_with_worktrees(parent: Path) -> Path:
    main = parent / "main"
    main.mkdir()
    _git(main, "init", "-b", "main")
    (main / "README.md").write_text("hi", encoding="utf-8")
    _git(main, "add", ".")
    # -c commit.gpgsign=false isolates the test from the user's global config
    # which may require an SSH/GPG key the test environment doesn't have.
    _git(main, "-c", "commit.gpgsign=false", "commit", "-m", "init")

    feature_path = parent / "feature"
    _git(main, "worktree", "add", str(feature_path), "-b", "feature")
    return main


@pytest.mark.integration
async def test_list_worktrees_returns_existing_worktrees(
    db: Database, tmp_path: Path
) -> None:
    repo = _make_repo_with_worktrees(tmp_path)
    app = create_app(database=db, ui_dist=None)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        create = await client.post("/api/projects", json={"name": "main", "path": str(repo)})
        project_id = create.json()["id"]

        response = await client.get(f"/api/projects/{project_id}/worktrees")

    assert response.status_code == 200
    worktrees = response.json()
    assert len(worktrees) == 2
    paths = {w["path"] for w in worktrees}
    branches = {w["branch"] for w in worktrees}
    assert str(repo) in paths
    assert "feature" in branches


@pytest.mark.integration
async def test_list_worktrees_unknown_project_returns_404(db: Database) -> None:
    app = create_app(database=db, ui_dist=None)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/projects/nope/worktrees")
    assert response.status_code == 404


@pytest.mark.integration
async def test_list_worktrees_updates_branch_on_rename(
    db: Database, tmp_path: Path
) -> None:
    repo = _make_repo_with_worktrees(tmp_path)
    app = create_app(database=db, ui_dist=None)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        create = await client.post("/api/projects", json={"name": "main", "path": str(repo)})
        project_id = create.json()["id"]

        first = await client.get(f"/api/projects/{project_id}/worktrees")
        assert "feature" in {w["branch"] for w in first.json()}

        feature_path = tmp_path / "feature"
        _git(feature_path, "-c", "commit.gpgsign=false", "branch", "-m", "feature", "feat-renamed")

        second = await client.get(f"/api/projects/{project_id}/worktrees")

    branches = {w["branch"] for w in second.json()}
    assert "feat-renamed" in branches
    assert "feature" not in branches


@pytest.mark.integration
async def test_list_worktrees_idempotent_no_duplicates(
    db: Database, tmp_path: Path
) -> None:
    repo = _make_repo_with_worktrees(tmp_path)
    app = create_app(database=db, ui_dist=None)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        create = await client.post("/api/projects", json={"name": "main", "path": str(repo)})
        project_id = create.json()["id"]

        first = await client.get(f"/api/projects/{project_id}/worktrees")
        second = await client.get(f"/api/projects/{project_id}/worktrees")

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(first.json()) == 2
    assert len(second.json()) == 2
