"""F5.g: multi-repo flow — POST /tasks/{id}/sessions creates N worktrees
under cwd parent dir, one per Repository, all on the same branch."""
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from orchestrator.main import create_app
from orchestrator.store.database import Database
from tests.integration.conftest import FakeSessionRuntime, _make_multi_repo


async def test_multi_repo_session_creates_n_worktrees(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    base = _make_multi_repo(tmp_path, ["api", "web"])
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        proj = (await client.post("/api/projects", json={"name": "u", "path": str(base)})).json()
        task = (await client.post(
            "/api/tasks", json={"project_id": proj["id"], "title": "Refactor logging"},
        )).json()
        sess = (await client.post(f"/api/tasks/{task['id']}/sessions", json={})).json()

        wts = (await client.get(f"/api/projects/{proj['id']}/worktrees")).json()

    cwd = Path(sess["cwd"])
    assert cwd.is_dir()
    assert cwd.name == f"{base.name}--refactor-logging"
    # Two child dirs created — one per sub-repo
    assert (cwd / "api").is_dir()
    assert (cwd / "web").is_dir()

    task_wts = [w for w in wts if w["task_id"] == task["id"]]
    assert len(task_wts) == 2
    paths = sorted(w["path"] for w in task_wts)
    assert paths == sorted([str(cwd / "api"), str(cwd / "web")])
    branches = {w["branch"] for w in task_wts}
    assert branches == {"refactor-logging"}  # all on the same branch
