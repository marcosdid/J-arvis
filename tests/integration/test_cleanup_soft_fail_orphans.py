"""F5.g: cleanup is tolerant — when git remove fails for a worktree,
the row is orphaned (task_id=NULL) instead of blocking the transition."""
import shutil
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from orchestrator.core.git import GitWorktreeError, SubprocessGitWorktreeOps
from orchestrator.main import create_app
from orchestrator.store.database import Database
from tests.integration.conftest import FakeSessionRuntime, _make_repo


class FlakyRemoveGit(SubprocessGitWorktreeOps):
    """Wraps real subprocess ops; fails on remove() to simulate stuck worktree."""

    async def remove(self, repo: Path, target: Path, *, force: bool = False) -> None:
        raise GitWorktreeError(f"simulated git remove failure on {target}")


async def test_cleanup_soft_fail_orphans_row(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        proj = (await client.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        task = (await client.post(
            "/api/tasks", json={"project_id": proj["id"], "title": "T"},
        )).json()
        sess = (await client.post(f"/api/tasks/{task['id']}/sessions", json={})).json()
        cwd = Path(sess["cwd"])

        # Stop session to free the active-session guard
        await client.post(f"/api/sessions/{sess['id']}/stop")

        # Swap to flaky git ops AFTER session creation (cleanup will use this)
        app.state.git_ops = FlakyRemoveGit()

        await client.patch(f"/api/tasks/{task['id']}", json={"state": "review"})
        r = await client.patch(f"/api/tasks/{task['id']}", json={"state": "done"})
        assert r.status_code == 200  # transition succeeds despite cleanup failure

        wts = (await client.get(f"/api/projects/{proj['id']}/worktrees")).json()

    # Worktree row is now orphan (task_id=None), still in DB
    orphans = [w for w in wts if w["task_id"] is None]
    assert any(w["path"] == str(cwd) for w in orphans)

    # Manual cleanup — leave tmp_path tidy
    if cwd.exists():
        shutil.rmtree(cwd, ignore_errors=True)
