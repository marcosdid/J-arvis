import os
import subprocess
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.main import create_app
from orchestrator.store.database import Database
from tests.integration.conftest import FakeSessionRuntime


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        },
    )


def _make_repo(parent: Path) -> Path:
    repo = parent / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    (repo / "f").write_text("x", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "-c", "commit.gpgsign=false", "commit", "-m", "init")
    return repo


async def _create_project_and_worktree(
    client: AsyncClient, repo: Path
) -> tuple[str, str]:
    project = (await client.post("/api/projects", json={"name": "r", "path": str(repo)})).json()
    worktrees = (await client.get(f"/api/projects/{project['id']}/worktrees")).json()
    return project["id"], worktrees[0]["id"]


@pytest.mark.integration
async def test_start_session_creates_executing_record(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        _, worktree_id = await _create_project_and_worktree(client, repo)
        response = await client.post(
            "/api/sessions", json={"worktree_id": worktree_id}
        )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "executing"
    assert body["worktree_id"] == worktree_id
    assert body["pid"] > 0
    assert body["jail_id"].startswith("fake-")
    assert len(runtime.spawned) == 1


@pytest.mark.integration
async def test_start_session_unknown_worktree_returns_404(
    db: Database, runtime: FakeSessionRuntime
) -> None:
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/sessions", json={"worktree_id": "nope"}
        )
    assert response.status_code == 404


@pytest.mark.integration
async def test_list_sessions_returns_existing(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        _, worktree_id = await _create_project_and_worktree(client, repo)
        await client.post("/api/sessions", json={"worktree_id": worktree_id})
        await client.post("/api/sessions", json={"worktree_id": worktree_id})
        listing = await client.get("/api/sessions")

    assert listing.status_code == 200
    sessions = listing.json()
    assert len(sessions) == 2
    assert all(s["status"] == "executing" for s in sessions)


@pytest.mark.integration
async def test_stop_session_marks_done_and_kills_runtime(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        _, worktree_id = await _create_project_and_worktree(client, repo)
        created = (
            await client.post("/api/sessions", json={"worktree_id": worktree_id})
        ).json()

        stop = await client.post(f"/api/sessions/{created['id']}/stop")
        assert stop.status_code == 204

        listing = await client.get("/api/sessions")
        sessions = listing.json()

    assert sessions[0]["status"] == "done"
    assert sessions[0]["ended_at"] is not None
    assert len(runtime.killed) == 1
    assert isinstance(runtime.killed[0][1], Path)


@pytest.mark.integration
async def test_stop_unknown_session_returns_404(
    db: Database, runtime: FakeSessionRuntime
) -> None:
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/sessions/nope/stop")
    assert response.status_code == 404


@pytest.mark.integration
async def test_stop_session_is_idempotent(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        _, worktree_id = await _create_project_and_worktree(client, repo)
        created = (
            await client.post("/api/sessions", json={"worktree_id": worktree_id})
        ).json()

        first = await client.post(f"/api/sessions/{created['id']}/stop")
        second = await client.post(f"/api/sessions/{created['id']}/stop")

    assert first.status_code == 204
    assert second.status_code == 204
    assert len(runtime.killed) == 1
