"""F5.g: DELETE /api/worktrees/{id} removes orphan worktrees only.

- Orphan (task_id=None): 204, row removed, fs cleaned.
- Belongs to task: 422 WorktreeNotOrphanError.
- Unknown id: 404.
"""
import os
import subprocess
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from orchestrator.core.git import GitWorktreeError, SubprocessGitWorktreeOps
from orchestrator.main import create_app
from orchestrator.store.database import Database
from tests.integration.conftest import FakeSessionRuntime, _make_repo


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "t@x.com",
            "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "t@x.com",
        },
    )


async def test_delete_orphan_worktree_204(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    # Create a worktree externally — appears as orphan after sync
    feature = tmp_path / "external"
    _git(repo, "worktree", "add", str(feature), "-b", "external")

    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        proj = (await client.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        # GET sync inserts the orphan
        wts = (await client.get(f"/api/projects/{proj['id']}/worktrees")).json()
        orphan = next(w for w in wts if w["path"] == str(feature))
        assert orphan["is_orphan"] is True

        r = await client.delete(f"/api/worktrees/{orphan['id']}")
        assert r.status_code == 204

        wts_after = (await client.get(f"/api/projects/{proj['id']}/worktrees")).json()
    assert all(w["id"] != orphan["id"] for w in wts_after)
    assert not feature.exists()


async def test_delete_active_worktree_returns_422(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        proj = (await client.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        task = (await client.post(
            "/api/tasks", json={"project_id": proj["id"], "title": "T"},
        )).json()
        await client.post(f"/api/tasks/{task['id']}/sessions", json={})

        wts = (await client.get(f"/api/projects/{proj['id']}/worktrees")).json()
        active = next(w for w in wts if w["task_id"] == task["id"])

        r = await client.delete(f"/api/worktrees/{active['id']}")
    assert r.status_code == 422


async def test_delete_unknown_worktree_returns_404(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        r = await client.delete("/api/worktrees/nope")
    assert r.status_code == 404


async def test_delete_orphan_git_error_returns_500(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    """When git remove fails (e.g. underlying worktree is locked), the
    DELETE route surfaces the error as HTTP 500."""
    repo = _make_repo(tmp_path)
    feature = tmp_path / "stuck"
    _git(repo, "worktree", "add", str(feature), "-b", "stuck")

    class FlakyGit(SubprocessGitWorktreeOps):
        async def remove(self, repo: Path, target: Path, *, force: bool = False) -> None:
            raise GitWorktreeError("simulated removal failure")

    app = create_app(database=db, runtime=runtime, ui_dist=None)
    app.state.git_ops = FlakyGit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        proj = (await client.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        wts = (await client.get(f"/api/projects/{proj['id']}/worktrees")).json()
        orphan = next(w for w in wts if w["path"] == str(feature))
        r = await client.delete(f"/api/worktrees/{orphan['id']}")
    assert r.status_code == 500
