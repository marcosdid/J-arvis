"""F6.f: integration tests pro /api/tasks/{id}/runs + /api/runs/{id}/{stop,logs}."""
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.core.port_allocator import PortAllocator
from orchestrator.events.broadcaster import InMemoryWsBroadcaster
from orchestrator.main import create_app
from orchestrator.sandbox.docker_ops import ContainerSpec, DockerError
from orchestrator.store.database import Database
from tests.integration.conftest import FakeSessionRuntime, _make_repo


class _FakeDocker:
    def __init__(self) -> None:
        self.build_calls: list[tuple[Path, str, str]] = []
        self.network_create_calls: list[str] = []
        self.network_rm_calls: list[str] = []
        self.start_calls: list[ContainerSpec] = []
        self.exec_calls: list[tuple[str, list[str]]] = []
        self.stop_calls: list[tuple[str, bool]] = []
        self.rm_calls: list[str] = []
        self._cid_seq = 0
        self.start_raises_for: set[str] = set()
        self.logs_lines: list[tuple[str, str]] = []

    async def build(self, *, context: Path, dockerfile: str, tag: str) -> None:
        self.build_calls.append((context, dockerfile, tag))

    async def network_create(self, name: str) -> None:
        self.network_create_calls.append(name)

    async def network_rm(self, name: str) -> None:
        self.network_rm_calls.append(name)

    async def container_start(self, spec: ContainerSpec) -> str:
        self.start_calls.append(spec)
        for svc in self.start_raises_for:
            if spec.name.endswith(f"-{svc}"):
                raise DockerError("start failed", stderr="fake")
        self._cid_seq += 1
        return f"cid{self._cid_seq}"

    async def run_in_container(
        self, container_id: str, cmd: list[str],
    ) -> tuple[int, str, str]:
        self.exec_calls.append((container_id, cmd))
        return (0, "", "")

    def stream_logs(self, container_id: str) -> AsyncIterator[tuple[str, str]]:
        lines = list(self.logs_lines)

        async def _gen() -> AsyncIterator[tuple[str, str]]:
            for stream, text in lines:
                yield stream, text
        return _gen()

    async def stop(self, container_id: str, *, force: bool = False) -> None:
        self.stop_calls.append((container_id, force))

    async def rm(self, container_id: str) -> None:
        self.rm_calls.append(container_id)


class _MockSock:
    def setsockopt(self, *_a: Any, **_kw: Any) -> None: pass
    def bind(self, *_a: Any, **_kw: Any) -> None: pass
    def close(self) -> None: pass


async def _seed_task_in_progress(
    client: AsyncClient, repo_path: Path,
) -> tuple[str, str]:
    proj = (await client.post(
        "/api/projects", json={"name": "p", "path": str(repo_path)},
    )).json()
    task = (await client.post(
        "/api/tasks", json={"project_id": proj["id"], "title": "T"},
    )).json()
    # idea → ready → in_progress (estado initial é 'idea'; transitions.ts +
    # core/tasks.py exigem essa cadeia, não permitem pular pra in_progress)
    await client.patch(f"/api/tasks/{task['id']}", json={"state": "ready"})
    await client.patch(f"/api/tasks/{task['id']}", json={"state": "in_progress"})
    return proj["id"], task["id"]


def _write_manifest(project_path: Path, content: str) -> None:
    (project_path / ".orchestrator").mkdir(parents=True, exist_ok=True)
    (project_path / ".orchestrator" / "run.yml").write_text(content)


def _build_app_with_run_infra(
    db: Database, runtime: FakeSessionRuntime, docker: _FakeDocker,
) -> Any:
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    app.state.docker_ops = docker
    app.state.port_allocator = PortAllocator(socket_factory=_MockSock)
    app.state.ws_broadcaster = InMemoryWsBroadcaster()
    return app


# === POST /tasks/{id}/runs ===================================================


@pytest.mark.integration
async def test_create_run_success(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    _write_manifest(repo, """
version: "1"
services:
  db: {image: postgres:16, port: 5432}
""")
    docker = _FakeDocker()
    app = _build_app_with_run_infra(db, runtime, docker)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        _, task_id = await _seed_task_in_progress(c, repo)
        r = await c.post(f"/api/tasks/{task_id}/runs")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["task_id"] == task_id
    assert body["status"] == "ready"
    assert len(body["services"]) == 1
    assert body["services"][0]["name"] == "db"
    assert body["services"][0]["port_host"] == 31000


@pytest.mark.integration
async def test_create_run_rejects_manifest_missing_with_bootstrap_hint(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    # NÃO escreve manifesto
    app = _build_app_with_run_infra(db, runtime, _FakeDocker())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        _, task_id = await _seed_task_in_progress(c, repo)
        r = await c.post(f"/api/tasks/{task_id}/runs")
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["error"] == "manifest_missing"
    assert detail["bootstrap_url"] == f"/api/tasks/{task_id}/bootstrap-manifest"


@pytest.mark.integration
async def test_create_run_rejects_manifest_invalid(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    _write_manifest(repo, """
version: "1"
services:
  bad: {image: x, build: ./y}
""")
    app = _build_app_with_run_infra(db, runtime, _FakeDocker())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        _, task_id = await _seed_task_in_progress(c, repo)
        r = await c.post(f"/api/tasks/{task_id}/runs")
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "manifest_invalid"


@pytest.mark.integration
async def test_create_run_rejects_task_not_in_progress(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    _write_manifest(repo, "version: '1'\nservices: {a: {image: x}}")
    app = _build_app_with_run_infra(db, runtime, _FakeDocker())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        proj = (await c.post(
            "/api/projects", json={"name": "p", "path": str(repo)},
        )).json()
        task = (await c.post(
            "/api/tasks", json={"project_id": proj["id"], "title": "T"},
        )).json()
        # Não move pra in_progress; state default = idea
        r = await c.post(f"/api/tasks/{task['id']}/runs")
    assert r.status_code == 422
    assert "task" in r.text.lower() or "state" in r.text.lower()


@pytest.mark.integration
async def test_create_run_404_when_task_unknown(
    db: Database, runtime: FakeSessionRuntime,
) -> None:
    app = _build_app_with_run_infra(db, runtime, _FakeDocker())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/tasks/ghost/runs")
    assert r.status_code == 404


@pytest.mark.integration
async def test_create_run_409_when_already_active(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    _write_manifest(repo, "version: '1'\nservices: {a: {image: x}}")
    app = _build_app_with_run_infra(db, runtime, _FakeDocker())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        _, task_id = await _seed_task_in_progress(c, repo)
        r1 = await c.post(f"/api/tasks/{task_id}/runs")
        r2 = await c.post(f"/api/tasks/{task_id}/runs")
    assert r1.status_code == 201
    assert r2.status_code == 409


# === GET /tasks/{id}/run =====================================================


@pytest.mark.integration
async def test_get_active_run_returns_404_when_no_run(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    app = _build_app_with_run_infra(db, runtime, _FakeDocker())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        _, task_id = await _seed_task_in_progress(c, repo)
        r = await c.get(f"/api/tasks/{task_id}/run")
    assert r.status_code == 404


@pytest.mark.integration
async def test_get_active_run_404_for_unknown_task(
    db: Database, runtime: FakeSessionRuntime,
) -> None:
    app = _build_app_with_run_infra(db, runtime, _FakeDocker())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/tasks/ghost/run")
    assert r.status_code == 404


@pytest.mark.integration
async def test_get_active_run_returns_run(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    _write_manifest(repo, "version: '1'\nservices: {a: {image: x}}")
    app = _build_app_with_run_infra(db, runtime, _FakeDocker())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        _, task_id = await _seed_task_in_progress(c, repo)
        await c.post(f"/api/tasks/{task_id}/runs")
        r = await c.get(f"/api/tasks/{task_id}/run")
    assert r.status_code == 200
    assert r.json()["task_id"] == task_id
    assert r.json()["status"] == "ready"


@pytest.mark.integration
async def test_get_active_run_when_manifest_was_removed_returns_empty_services(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    """Manifest removido pós-start → services vira []. Não quebra."""
    repo = _make_repo(tmp_path)
    _write_manifest(repo, "version: '1'\nservices: {a: {image: x}}")
    app = _build_app_with_run_infra(db, runtime, _FakeDocker())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        _, task_id = await _seed_task_in_progress(c, repo)
        await c.post(f"/api/tasks/{task_id}/runs")
        # Remove manifesto
        (repo / ".orchestrator" / "run.yml").unlink()
        r = await c.get(f"/api/tasks/{task_id}/run")
    assert r.status_code == 200
    assert r.json()["services"] == []


# === POST /runs/{id}/stop ====================================================


@pytest.mark.integration
async def test_stop_run_204(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    _write_manifest(repo, "version: '1'\nservices: {a: {image: x}}")
    docker = _FakeDocker()
    app = _build_app_with_run_infra(db, runtime, docker)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        _, task_id = await _seed_task_in_progress(c, repo)
        run = (await c.post(f"/api/tasks/{task_id}/runs")).json()
        r = await c.post(f"/api/runs/{run['id']}/stop")
    assert r.status_code == 204
    # Container foi stopped (force=True)
    assert ("cid1", True) in docker.stop_calls


@pytest.mark.integration
async def test_stop_run_idempotent_on_already_stopped(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    _write_manifest(repo, "version: '1'\nservices: {a: {image: x}}")
    app = _build_app_with_run_infra(db, runtime, _FakeDocker())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        _, task_id = await _seed_task_in_progress(c, repo)
        run = (await c.post(f"/api/tasks/{task_id}/runs")).json()
        r1 = await c.post(f"/api/runs/{run['id']}/stop")
        r2 = await c.post(f"/api/runs/{run['id']}/stop")
    assert r1.status_code == 204
    assert r2.status_code == 204


@pytest.mark.integration
async def test_stop_unknown_run_returns_204_noop(
    db: Database, runtime: FakeSessionRuntime,
) -> None:
    app = _build_app_with_run_infra(db, runtime, _FakeDocker())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/runs/ghost/stop")
    assert r.status_code == 204  # idempotent: stop_run on missing is no-op


# === GET /runs/{id}/logs (SSE) ==============================================


@pytest.mark.integration
async def test_stream_logs_yields_sse_data(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    _write_manifest(repo, "version: '1'\nservices: {a: {image: x}}")
    docker = _FakeDocker()
    docker.logs_lines = [("stdout", "line 1"), ("stderr", "warn"), ("stdout", "line 2")]
    app = _build_app_with_run_infra(db, runtime, docker)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        _, task_id = await _seed_task_in_progress(c, repo)
        run = (await c.post(f"/api/tasks/{task_id}/runs")).json()
        # Stream SSE
        async with c.stream("GET", f"/api/runs/{run['id']}/logs?service=a") as r:
            assert r.status_code == 200
            assert r.headers["content-type"].startswith("text/event-stream")
            payloads: list[dict[str, str]] = []
            async for line in r.aiter_lines():
                if line.startswith("data: "):
                    payloads.append(json.loads(line[6:]))
    assert payloads == [
        {"service": "a", "stream": "stdout", "text": "line 1"},
        {"service": "a", "stream": "stderr", "text": "warn"},
        {"service": "a", "stream": "stdout", "text": "line 2"},
    ]


@pytest.mark.integration
async def test_stream_logs_404_for_unknown_run(
    db: Database, runtime: FakeSessionRuntime,
) -> None:
    app = _build_app_with_run_infra(db, runtime, _FakeDocker())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/runs/ghost/logs?service=a")
    assert r.status_code == 404


@pytest.mark.integration
async def test_create_run_returns_500_when_start_run_internal_failure(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    """Container_start falha (Docker error) → start_run raises RunStartError
    → API converte pra 500 com mensagem."""
    repo = _make_repo(tmp_path)
    _write_manifest(repo, "version: '1'\nservices: {a: {image: x}}")
    docker = _FakeDocker()
    docker.start_raises_for = {"a"}
    app = _build_app_with_run_infra(db, runtime, docker)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        _, task_id = await _seed_task_in_progress(c, repo)
        r = await c.post(f"/api/tasks/{task_id}/runs")
    assert r.status_code == 500
    assert "run failed" in r.text.lower()


@pytest.mark.integration
async def test_stream_logs_404_for_unknown_service_in_run(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    _write_manifest(repo, "version: '1'\nservices: {a: {image: x}}")
    app = _build_app_with_run_infra(db, runtime, _FakeDocker())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        _, task_id = await _seed_task_in_progress(c, repo)
        run = (await c.post(f"/api/tasks/{task_id}/runs")).json()
        r = await c.get(f"/api/runs/{run['id']}/logs?service=ghost")
    assert r.status_code == 404
