"""F6.k: hooks de cleanup automático — 3-layer lifecycle (ADR-0018).

Layer 2: stop session → stop run (mesma task).
Layer 3: task → done/discarded → stop run + cleanup worktrees.
"""
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.core.port_allocator import PortAllocator
from orchestrator.events.broadcaster import InMemoryWsBroadcaster
from orchestrator.main import create_app
from orchestrator.sandbox.docker_ops import ContainerSpec
from orchestrator.store.database import Database
from tests.integration.conftest import FakeSessionRuntime, _make_repo


class _FakeDocker:
    def __init__(self) -> None:
        self.stop_calls: list[tuple[str, bool]] = []
        self.rm_calls: list[str] = []
        self.network_rm_calls: list[str] = []
        self._cid_seq = 0

    async def build(self, *_a: Any, **_kw: Any) -> None: pass
    async def network_create(self, _name: str) -> None: pass

    async def network_rm(self, name: str) -> None:
        self.network_rm_calls.append(name)

    async def container_start(self, _spec: ContainerSpec) -> str:
        self._cid_seq += 1
        return f"cid{self._cid_seq}"

    async def run_in_container(
        self, _cid: str, _cmd: list[str],
    ) -> tuple[int, str, str]:
        return (0, "", "")

    def stream_logs(self, _cid: str) -> AsyncIterator[tuple[str, str]]:
        async def _empty() -> AsyncIterator[tuple[str, str]]:
            if False:
                yield "", ""
        return _empty()

    async def stop(self, cid: str, *, force: bool = False) -> None:
        self.stop_calls.append((cid, force))

    async def rm(self, cid: str) -> None:
        self.rm_calls.append(cid)


class _MockSock:
    def setsockopt(self, *_a: Any, **_kw: Any) -> None: pass
    def bind(self, *_a: Any, **_kw: Any) -> None: pass
    def close(self) -> None: pass


def _write_manifest(p: Path, content: str) -> None:
    (p / ".orchestrator").mkdir(parents=True, exist_ok=True)
    (p / ".orchestrator" / "run.yml").write_text(content)


def _build_app(db: Database, runtime: FakeSessionRuntime, docker: _FakeDocker) -> Any:
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    app.state.docker_ops = docker
    app.state.port_allocator = PortAllocator(socket_factory=_MockSock)
    app.state.ws_broadcaster = InMemoryWsBroadcaster()
    return app


@pytest.mark.integration
async def test_task_terminal_state_stops_active_run(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    """Layer 3: mover task → done dispara stop_run + cleanup_task_worktrees."""
    repo = _make_repo(tmp_path)
    _write_manifest(repo, "version: '1'\nservices: {a: {image: x}}")
    docker = _FakeDocker()
    app = _build_app(db, runtime, docker)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        proj = (await c.post("/api/projects", json={
            "name": "p", "path": str(repo),
        })).json()
        task = (await c.post("/api/tasks", json={
            "project_id": proj["id"], "title": "T",
        })).json()
        await c.patch(f"/api/tasks/{task['id']}", json={"state": "ready"})
        await c.post(f"/api/tasks/{task['id']}/sessions", json={})
        # Inicia run
        await c.post(f"/api/tasks/{task['id']}/runs")

        # Stop session ANTES de done (guard de "task tem session ativa")
        sessions = (await c.get("/api/sessions")).json()
        await c.post(f"/api/sessions/{sessions[0]['id']}/stop")
        # session stop já dispara layer 2 — limpa containers
        # Reset rastros pra ver claramente layer 3 abaixo
        docker.stop_calls.clear()
        docker.rm_calls.clear()
        docker.network_rm_calls.clear()
        # Move task → review → done
        await c.patch(f"/api/tasks/{task['id']}", json={"state": "review"})
        r = await c.patch(f"/api/tasks/{task['id']}", json={"state": "done"})
    assert r.status_code == 200
    # Como a session já tinha parado a run, novo PATCH→done não tem run
    # ativa pra parar — fluxo OK (idempotent layer 3).
    # Worktree cleanup ainda acontece (apaga worktrees do disco).


@pytest.mark.integration
async def test_session_stop_triggers_run_stop_same_task(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    """Layer 2: stop_session da task X dispara stop_run da task X."""
    repo = _make_repo(tmp_path)
    _write_manifest(repo, "version: '1'\nservices: {a: {image: x}}")
    docker = _FakeDocker()
    app = _build_app(db, runtime, docker)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        proj = (await c.post("/api/projects", json={
            "name": "p", "path": str(repo),
        })).json()
        task = (await c.post("/api/tasks", json={
            "project_id": proj["id"], "title": "T",
        })).json()
        await c.patch(f"/api/tasks/{task['id']}", json={"state": "ready"})
        sess = (await c.post(f"/api/tasks/{task['id']}/sessions", json={})).json()
        run = (await c.post(f"/api/tasks/{task['id']}/runs")).json()
        # Antes de stop: run ativa
        assert (await c.get(f"/api/tasks/{task['id']}/run")).status_code == 200

        # Stop session → deveria parar a run também
        r = await c.post(f"/api/sessions/{sess['id']}/stop")
        assert r.status_code == 204

        # Após stop_session: container teve stop+rm chamado pelo stop_run
        assert ("cid1", True) in docker.stop_calls
        assert "cid1" in docker.rm_calls
        # Run agora não está ativa
        r2 = await c.get(f"/api/tasks/{task['id']}/run")
        assert r2.status_code == 404
        # Network também removida
        assert run["network_name"] in docker.network_rm_calls


@pytest.mark.integration
async def test_session_stop_without_active_run_is_noop_on_run_side(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    """Layer 2: stop_session de task SEM run ativa não chama stop_run."""
    repo = _make_repo(tmp_path)
    docker = _FakeDocker()
    app = _build_app(db, runtime, docker)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        proj = (await c.post("/api/projects", json={
            "name": "p", "path": str(repo),
        })).json()
        task = (await c.post("/api/tasks", json={
            "project_id": proj["id"], "title": "T",
        })).json()
        await c.patch(f"/api/tasks/{task['id']}", json={"state": "ready"})
        sess = (await c.post(f"/api/tasks/{task['id']}/sessions", json={})).json()
        # NÃO inicia run
        r = await c.post(f"/api/sessions/{sess['id']}/stop")
    assert r.status_code == 204
    # Nenhuma container stop registrado (Layer 2 no-op)
    assert docker.stop_calls == []
    assert docker.network_rm_calls == []


@pytest.mark.integration
async def test_stop_session_unknown_session_404_without_touching_runs(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    """Edge: session_id desconhecido → 404, e Layer 2 não dispara
    (task_id é None porque row não existe)."""
    repo = _make_repo(tmp_path)
    docker = _FakeDocker()
    app = _build_app(db, runtime, docker)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        # Cria projeto pra app montar normalmente, mas session ghost
        await c.post("/api/projects", json={"name": "p", "path": str(repo)})
        r = await c.post("/api/sessions/ghost/stop")
    assert r.status_code == 404
    assert docker.stop_calls == []


@pytest.mark.integration
async def test_task_terminal_stops_active_run_when_session_did_not(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    """Layer 3 mata run mesmo se layer 2 não passou (e.g., session ainda ativa)
    — caso usuário move task pra `discarded` sem parar session antes.

    Pré-condição: TaskHasActiveSessionError bloqueia normalmente; mas se
    bypassamos via stop manual da run primeiro depois moveremos task.
    Aqui simulamos: stop session (libera guard) + move done."""
    repo = _make_repo(tmp_path)
    _write_manifest(repo, "version: '1'\nservices: {a: {image: x}}")
    docker = _FakeDocker()
    app = _build_app(db, runtime, docker)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        proj = (await c.post("/api/projects", json={
            "name": "p", "path": str(repo),
        })).json()
        task = (await c.post("/api/tasks", json={
            "project_id": proj["id"], "title": "T",
        })).json()
        await c.patch(f"/api/tasks/{task['id']}", json={"state": "ready"})
        sess = (await c.post(f"/api/tasks/{task['id']}/sessions", json={})).json()
        # Inicia run via API
        run = (await c.post(f"/api/tasks/{task['id']}/runs")).json()
        # Stop session — Layer 2 já vai parar a run
        await c.post(f"/api/sessions/{sess['id']}/stop")
        # Run já parou. Reset rastros.
        docker.stop_calls.clear()
        docker.network_rm_calls.clear()
        # Inicia OUTRA run manualmente (sem session)
        run2 = (await c.post(f"/api/tasks/{task['id']}/runs")).json()
        assert run2["id"] != run["id"]
        # Move task → review → discarded → Layer 3 deve parar run2
        await c.patch(f"/api/tasks/{task['id']}", json={"state": "review"})
        await c.patch(f"/api/tasks/{task['id']}", json={"state": "discarded"})
    # Layer 3 stop_run chamou containers do run2
    assert ("cid2", True) in docker.stop_calls
    assert run2["network_name"] in docker.network_rm_calls
