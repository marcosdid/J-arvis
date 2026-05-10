"""F5.g: branch clash — pre-existing branch causes git add to fail,
which the route maps to HTTP 500 GitWorktreeError."""
import os
import subprocess
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from orchestrator.main import create_app
from orchestrator.store.database import Database
from tests.integration.conftest import FakeSessionRuntime, _make_repo


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "t@x.com",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "t@x.com",
        },
    )


async def test_branch_clash_returns_500(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    # Pre-create a branch that will clash with the task slug
    _git(repo, "branch", "fix-bug")

    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        proj = (await client.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        task = (await client.post(
            "/api/tasks", json={"project_id": proj["id"], "title": "Fix bug"},
        )).json()
        r = await client.post(f"/api/tasks/{task['id']}/sessions", json={})
    # `git worktree add -b <existing>` fails -> GitWorktreeError -> 500
    assert r.status_code == 500
