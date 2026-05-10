"""F5.g: an externally-created git worktree is discovered by the sync
on GET /projects/{id}/worktrees and surfaced as an orphan (task_id=None,
is_orphan=True)."""
import os
import subprocess
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from orchestrator.main import create_app
from orchestrator.store.database import Database
from tests.integration.conftest import _make_repo


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "t@x.com",
            "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "t@x.com",
        },
    )


async def test_external_worktree_appears_as_orphan(db: Database, tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    external = tmp_path / "ext"
    _git(repo, "worktree", "add", str(external), "-b", "ext-branch")

    app = create_app(database=db, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        proj = (await client.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        wts = (await client.get(f"/api/projects/{proj['id']}/worktrees")).json()

    paths = {w["path"]: w for w in wts}
    assert str(external) in paths
    discovered = paths[str(external)]
    assert discovered["is_orphan"] is True
    assert discovered["task_id"] is None
    assert discovered["branch"] == "ext-branch"
