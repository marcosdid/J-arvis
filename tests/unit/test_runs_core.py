"""F6.e: start_run / stop_run state machine + atomic rollback."""
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import yaml as _yaml
from sqlalchemy import select as _select

from orchestrator.core.manifest import ManifestSpec, ServiceSpec
from orchestrator.core.port_allocator import PortAllocator
from orchestrator.core.runs import (
    RunAlreadyActiveError,
    RunStartError,
    TaskNotEligibleForRunError,
    _service_volumes,
    _topo_sort,
    get_active_run,
    start_run,
    stop_run,
)
from orchestrator.events.envelope import WsEvent
from orchestrator.sandbox.docker_ops import ContainerSpec, DockerError
from orchestrator.store.database import Database
from orchestrator.store.models import Project, RunInstance, Task


class FakeDockerOps:
    """Test fake: registra todas chamadas; opcionalmente levanta DockerError
    em métodos específicos.
    """

    def __init__(self) -> None:
        self.build_calls: list[tuple[Path, str, str]] = []
        self.network_create_calls: list[str] = []
        self.network_rm_calls: list[str] = []
        self.start_calls: list[ContainerSpec] = []
        self.exec_calls: list[tuple[str, list[str]]] = []
        self.stop_calls: list[tuple[str, bool]] = []
        self.rm_calls: list[str] = []
        self._cid_seq = 0
        # Fault injection
        self.build_raises_for: set[str] = set()  # service name → raise
        self.start_raises_for: set[str] = set()  # service name → raise
        self.network_create_raises = False
        # Healthcheck/seed canned: lookup por (cid, cmd_first_arg)
        self.exec_results: dict[str, tuple[int, str, str]] = {}

    async def build(self, *, context: Path, dockerfile: str, tag: str) -> None:
        self.build_calls.append((context, dockerfile, tag))
        # tag like "jarvis-run-abcdef12-backend" — match by svc name suffix
        for svc in self.build_raises_for:
            if tag.endswith(f"-{svc}"):
                raise DockerError(f"build {svc} failed", stderr="fake stderr")

    async def network_create(self, name: str) -> None:
        self.network_create_calls.append(name)
        if self.network_create_raises:
            raise DockerError("network create failed", stderr="fake")

    async def network_rm(self, name: str) -> None:
        self.network_rm_calls.append(name)

    async def container_start(self, spec: ContainerSpec) -> str:
        self.start_calls.append(spec)
        # spec.name like "jarvis-run-abcdef12-<svc>"
        for svc in self.start_raises_for:
            if spec.name.endswith(f"-{svc}"):
                raise DockerError(f"start {svc} failed", stderr="fake")
        self._cid_seq += 1
        return f"cid{self._cid_seq}"

    async def run_in_container(
        self, container_id: str, cmd: list[str],
    ) -> tuple[int, str, str]:
        self.exec_calls.append((container_id, cmd))
        # Key the canned result by container_id + first cmd arg
        key = f"{container_id}:{cmd[0] if cmd else ''}"
        return self.exec_results.get(key, (0, "", ""))

    def stream_logs(self, container_id: str) -> AsyncIterator[tuple[str, str]]:
        async def _empty() -> AsyncIterator[tuple[str, str]]:
            if False:
                yield "stdout", ""
        return _empty()

    async def stop(self, container_id: str, *, force: bool = False) -> None:
        self.stop_calls.append((container_id, force))

    async def rm(self, container_id: str) -> None:
        self.rm_calls.append(container_id)


class CollectingBroadcaster:
    def __init__(self) -> None:
        self.events: list[WsEvent] = []

    async def publish(self, event: WsEvent) -> None:
        self.events.append(event)


def _manifest(yaml_str: str) -> ManifestSpec:
    """Helper: build ManifestSpec a partir de YAML string."""
    return ManifestSpec.model_validate(_yaml.safe_load(yaml_str))


async def _seed_task(db: Database, state: str = "in_progress") -> tuple[Project, Task]:
    async with db.session() as s:
        p = Project(name="p", path="/tmp/p")
        s.add(p)
        await s.commit()
        await s.refresh(p)
        t = Task(project_id=p.id, title="t", description="", state=state)
        s.add(t)
        await s.commit()
        await s.refresh(t)
        return p, t


# === _topo_sort ==============================================================


@pytest.mark.unit
def test_topo_sort_chain() -> None:
    m = _manifest("""
version: "1"
services:
  db: {image: x}
  backend: {image: y, depends_on: [db]}
  frontend: {image: z, depends_on: [backend]}
""")
    assert _topo_sort(m) == ["db", "backend", "frontend"]


@pytest.mark.unit
def test_topo_sort_diamond() -> None:
    m = _manifest("""
version: "1"
services:
  db: {image: x}
  a: {image: y, depends_on: [db]}
  b: {image: z, depends_on: [db]}
  c: {image: w, depends_on: [a, b]}
""")
    order = _topo_sort(m)
    assert order[0] == "db"
    assert order[-1] == "c"
    assert order.index("a") < order.index("c")
    assert order.index("b") < order.index("c")


@pytest.mark.unit
def test_service_volumes_image_with_forced_mount_source_returns_empty() -> None:
    """mount_source=True forçado num service sem `build:` → mount no-op
    (sem path canônico pra mountar; documentado como caveat futuro)."""
    svc = ServiceSpec(image="postgres", mount_source=True)
    assert _service_volumes(svc, Path("/cwd")) == ()


@pytest.mark.unit
def test_topo_sort_no_deps() -> None:
    m = _manifest("""
version: "1"
services:
  a: {image: x}
  b: {image: y}
""")
    # Order pode ser qualquer permutação válida (ambos in_degree=0)
    assert set(_topo_sort(m)) == {"a", "b"}


# === start_run happy path ====================================================


@pytest.mark.integration
async def test_start_run_happy_path_2_services(tmp_path: Path) -> None:
    """db (image) → backend (build + healthcheck) → ready."""
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 't.db'}")
    await db.bootstrap()
    docker = FakeDockerOps()
    alloc = PortAllocator(socket_factory=_MockSock)
    bc = CollectingBroadcaster()
    try:
        _, task = await _seed_task(db)
        manifest = _manifest("""
version: "1"
services:
  db:
    image: postgres:16
    port: 5432
  backend:
    build: ./back
    port: 8000
    depends_on: [db]
    healthcheck:
      command: ["curl", "-f", "http://localhost:8000/health"]
""")
        async with db.session() as s:
            run = await start_run(
                s, docker, alloc, bc,
                task_id=task.id, cwd=tmp_path, manifest=manifest,
            )
            assert run.status == "ready"
            assert run.ended_at is None
            ports = json.loads(run.ports_json)
            assert ports == {"db": 31000, "backend": 31001}
            containers = json.loads(run.containers_json)
            assert containers == {"db": "cid1", "backend": "cid2"}

        # 1 build (backend), 1 network, 2 starts, 1 healthcheck (backend)
        assert len(docker.build_calls) == 1
        assert docker.network_create_calls == [run.network_name]
        assert [s.name.split("-")[-1] for s in docker.start_calls] == ["db", "backend"]
        assert len(docker.exec_calls) == 1  # healthcheck do backend

        # WS event sequence: building → seeding → ready
        statuses = [e.payload["status"] for e in bc.events if e.type == "run.status"]
        assert statuses == ["building", "seeding", "ready"]
    finally:
        await db.close()


# === start_run errors ========================================================


@pytest.mark.integration
async def test_start_run_rejects_task_in_backlog(tmp_path: Path) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 't.db'}")
    await db.bootstrap()
    try:
        _, task = await _seed_task(db, state="idea")
        manifest = _manifest("version: '1'\nservices: {a: {image: x}}")
        async with db.session() as s:
            with pytest.raises(TaskNotEligibleForRunError):
                await start_run(
                    s, FakeDockerOps(),
                    PortAllocator(socket_factory=_MockSock),
                    CollectingBroadcaster(),
                    task_id=task.id, cwd=tmp_path, manifest=manifest,
                )
    finally:
        await db.close()


@pytest.mark.integration
async def test_start_run_rejects_unknown_task(tmp_path: Path) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 't.db'}")
    await db.bootstrap()
    try:
        manifest = _manifest("version: '1'\nservices: {a: {image: x}}")
        async with db.session() as s:
            with pytest.raises(TaskNotEligibleForRunError):
                await start_run(
                    s, FakeDockerOps(),
                    PortAllocator(socket_factory=_MockSock),
                    CollectingBroadcaster(),
                    task_id="nonexistent", cwd=tmp_path, manifest=manifest,
                )
    finally:
        await db.close()


@pytest.mark.integration
async def test_start_run_409_when_already_active(tmp_path: Path) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 't.db'}")
    await db.bootstrap()
    try:
        _, task = await _seed_task(db)
        manifest = _manifest("version: '1'\nservices: {a: {image: x}}")
        async with db.session() as s:
            await start_run(
                s, FakeDockerOps(),
                PortAllocator(socket_factory=_MockSock),
                CollectingBroadcaster(),
                task_id=task.id, cwd=tmp_path, manifest=manifest,
            )
        async with db.session() as s:
            with pytest.raises(RunAlreadyActiveError):
                await start_run(
                    s, FakeDockerOps(),
                    PortAllocator(socket_factory=_MockSock),
                    CollectingBroadcaster(),
                    task_id=task.id, cwd=tmp_path, manifest=manifest,
                )
    finally:
        await db.close()


@pytest.mark.integration
async def test_start_run_build_failure_rolls_back_atomically(tmp_path: Path) -> None:
    """Build do `backend` falha → status=failed, error_message populado,
    nenhum container criado (network nem foi criada), porta liberada."""
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 't.db'}")
    await db.bootstrap()
    docker = FakeDockerOps()
    docker.build_raises_for = {"backend"}
    alloc = PortAllocator(socket_factory=_MockSock)
    bc = CollectingBroadcaster()
    try:
        _, task = await _seed_task(db)
        manifest = _manifest("""
version: "1"
services:
  backend: {build: ./back, port: 8000}
""")
        async with db.session() as s:
            with pytest.raises(RunStartError):
                await start_run(
                    s, docker, alloc, bc,
                    task_id=task.id, cwd=tmp_path, manifest=manifest,
                )

        async with db.session() as s:
            row = (await s.execute(_select(RunInstance))).scalar_one()
            assert row.status == "failed"
            assert "build" in (row.error_message or "")
            assert row.ended_at is not None

        # Network não foi criada (build é antes)
        assert docker.network_create_calls == []
        # Porta liberada — re-allocate retorna a mesma
        port = await alloc.allocate()
        assert port == 31000

        # run.failed broadcast
        failed = [e for e in bc.events if e.type == "run.failed"]
        assert len(failed) == 1
        assert failed[0].payload["service"] == "backend"
    finally:
        await db.close()


@pytest.mark.integration
async def test_start_run_container_start_failure_rolls_back(tmp_path: Path) -> None:
    """Build OK, network OK, container_start do backend falha →
    network removida + outros containers (db) stop+rm + ports liberadas."""
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 't.db'}")
    await db.bootstrap()
    docker = FakeDockerOps()
    docker.start_raises_for = {"backend"}
    alloc = PortAllocator(socket_factory=_MockSock)
    bc = CollectingBroadcaster()
    try:
        _, task = await _seed_task(db)
        manifest = _manifest("""
version: "1"
services:
  db: {image: postgres, port: 5432}
  backend: {build: ./back, port: 8000, depends_on: [db]}
""")
        async with db.session() as s:
            with pytest.raises(RunStartError):
                await start_run(
                    s, docker, alloc, bc,
                    task_id=task.id, cwd=tmp_path, manifest=manifest,
                )

        # db container foi criado e depois rolled back (stop+rm)
        assert len(docker.start_calls) == 2  # tentou db + backend
        assert any(cid == "cid1" for cid, _ in docker.stop_calls)
        assert "cid1" in docker.rm_calls

        # Network criada e depois removida
        assert len(docker.network_create_calls) == 1
        assert len(docker.network_rm_calls) == 1
    finally:
        await db.close()


@pytest.mark.integration
async def test_start_run_healthcheck_timeout(tmp_path: Path) -> None:
    """Healthcheck retorna exit≠0 nas N tentativas → failed."""
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 't.db'}")
    await db.bootstrap()
    docker = FakeDockerOps()
    # Healthcheck sempre falha
    docker.exec_results = {"cid1:curl": (1, "", "connection refused")}
    alloc = PortAllocator(socket_factory=_MockSock)
    bc = CollectingBroadcaster()
    try:
        _, task = await _seed_task(db)
        manifest = _manifest("""
version: "1"
services:
  backend:
    image: nginx
    port: 80
    healthcheck:
      command: ["curl", "-f", "http://localhost"]
      interval: 1
      retries: 2
""")
        async with db.session() as s:
            with pytest.raises(RunStartError):
                await start_run(
                    s, docker, alloc, bc,
                    task_id=task.id, cwd=tmp_path, manifest=manifest,
                )
        # 2 retries do healthcheck
        assert len(docker.exec_calls) == 2
        failed = [e for e in bc.events if e.type == "run.failed"]
        assert failed[0].payload["service"] == "backend"
    finally:
        await db.close()


@pytest.mark.integration
async def test_start_run_seed_success_reaches_ready(tmp_path: Path) -> None:
    """Seed retorna exit=0 → run prossegue até ready (cobre branch
    `code == 0` em `_run_seed`)."""
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 't.db'}")
    await db.bootstrap()
    docker = FakeDockerOps()
    # seed retorna 0 explicitamente (default já é 0, mas testamos a chamada)
    docker.exec_results = {"cid1:psql": (0, "INSERT 0 1", "")}
    alloc = PortAllocator(socket_factory=_MockSock)
    bc = CollectingBroadcaster()
    try:
        _, task = await _seed_task(db)
        manifest = _manifest("""
version: "1"
services:
  db:
    image: postgres
    seed:
      command: ["psql", "-f", "/seed.sql"]
""")
        async with db.session() as s:
            run = await start_run(
                s, docker, alloc, bc,
                task_id=task.id, cwd=tmp_path, manifest=manifest,
            )
            assert run.status == "ready"
        # seed foi chamado (cid1:psql)
        assert any(cmd[0] == "psql" for _, cmd in docker.exec_calls)
    finally:
        await db.close()


@pytest.mark.integration
async def test_start_run_rollback_tolerates_docker_errors(tmp_path: Path) -> None:
    """Rollback após falha continua mesmo se stop/rm/network_rm Docker
    levantam erros (containers já mortos, etc.). Cobre branches dos
    except DockerError no _rollback."""
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 't.db'}")
    await db.bootstrap()

    class FlakyOnRollback(FakeDockerOps):
        async def stop(self, cid: str, *, force: bool = False) -> None:
            self.stop_calls.append((cid, force))
            raise DockerError("stop failed", stderr="x")
        async def rm(self, cid: str) -> None:
            self.rm_calls.append(cid)
            raise DockerError("rm failed", stderr="x")
        async def network_rm(self, name: str) -> None:
            self.network_rm_calls.append(name)
            raise DockerError("network_rm failed", stderr="x")

    docker = FlakyOnRollback()
    docker.start_raises_for = {"backend"}
    alloc = PortAllocator(socket_factory=_MockSock)
    bc = CollectingBroadcaster()
    try:
        _, task = await _seed_task(db)
        manifest = _manifest("""
version: "1"
services:
  db: {image: postgres, port: 5432}
  backend: {build: ./b, port: 8000, depends_on: [db]}
""")
        async with db.session() as s:
            with pytest.raises(RunStartError):
                await start_run(
                    s, docker, alloc, bc,
                    task_id=task.id, cwd=tmp_path, manifest=manifest,
                )
        # Rollback foi chamado mesmo com Docker quebrado
        assert len(docker.network_rm_calls) == 1  # tentou
        # Run final está failed
        async with db.session() as s:
            row = (await s.execute(_select(RunInstance))).scalar_one()
            assert row.status == "failed"
    finally:
        await db.close()


@pytest.mark.integration
async def test_start_run_seed_failure(tmp_path: Path) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 't.db'}")
    await db.bootstrap()
    docker = FakeDockerOps()
    docker.exec_results = {"cid1:psql": (1, "", "syntax error")}
    alloc = PortAllocator(socket_factory=_MockSock)
    bc = CollectingBroadcaster()
    try:
        _, task = await _seed_task(db)
        manifest = _manifest("""
version: "1"
services:
  db:
    image: postgres
    seed:
      command: ["psql", "-f", "/seed.sql"]
""")
        async with db.session() as s:
            with pytest.raises(RunStartError):
                await start_run(
                    s, docker, alloc, bc,
                    task_id=task.id, cwd=tmp_path, manifest=manifest,
                )
        failed = [e for e in bc.events if e.type == "run.failed"]
        assert "seed" in failed[0].payload["error"]
    finally:
        await db.close()


@pytest.mark.integration
async def test_start_run_network_create_failure(tmp_path: Path) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 't.db'}")
    await db.bootstrap()
    docker = FakeDockerOps()
    docker.network_create_raises = True
    alloc = PortAllocator(socket_factory=_MockSock)
    bc = CollectingBroadcaster()
    try:
        _, task = await _seed_task(db)
        manifest = _manifest("version: '1'\nservices: {a: {image: x}}")
        async with db.session() as s:
            with pytest.raises(RunStartError):
                await start_run(
                    s, docker, alloc, bc,
                    task_id=task.id, cwd=tmp_path, manifest=manifest,
                )
        failed = [e for e in bc.events if e.type == "run.failed"]
        assert failed[0].payload["service"] is None  # network não tem service
    finally:
        await db.close()


# === stop_run ===============================================================


@pytest.mark.integration
async def test_stop_run_removes_containers_network_releases_ports(
    tmp_path: Path,
) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 't.db'}")
    await db.bootstrap()
    docker = FakeDockerOps()
    alloc = PortAllocator(socket_factory=_MockSock)
    bc = CollectingBroadcaster()
    try:
        _, task = await _seed_task(db)
        manifest = _manifest("""
version: "1"
services:
  db: {image: x, port: 5432}
  backend: {image: y, port: 8000, depends_on: [db]}
""")
        async with db.session() as s:
            run = await start_run(
                s, docker, alloc, bc,
                task_id=task.id, cwd=tmp_path, manifest=manifest,
            )
            run_id = run.id
            network = run.network_name

        bc.events.clear()
        async with db.session() as s:
            await stop_run(
                s, docker, alloc, bc,
                run_id=run_id, reason="manual",
            )

        # Containers parados + removidos
        stopped_cids = [cid for cid, _ in docker.stop_calls]
        assert "cid1" in stopped_cids and "cid2" in stopped_cids
        assert "cid1" in docker.rm_calls and "cid2" in docker.rm_calls
        # Network removida
        assert network in docker.network_rm_calls
        # Portas liberadas
        port = await alloc.allocate()
        assert port == 31000

        # DB
        async with db.session() as s:
            row = await s.get(RunInstance, run_id)
            assert row.status == "stopped"
            assert row.ended_at is not None

        # Broadcast
        stopped_events = [e for e in bc.events if e.type == "run.stopped"]
        assert len(stopped_events) == 1
        assert stopped_events[0].payload["reason"] == "manual"
    finally:
        await db.close()


@pytest.mark.integration
async def test_stop_run_idempotent_on_already_stopped(tmp_path: Path) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 't.db'}")
    await db.bootstrap()
    docker = FakeDockerOps()
    alloc = PortAllocator(socket_factory=_MockSock)
    bc = CollectingBroadcaster()
    try:
        _, task = await _seed_task(db)
        manifest = _manifest("version: '1'\nservices: {a: {image: x}}")
        async with db.session() as s:
            run = await start_run(
                s, docker, alloc, bc,
                task_id=task.id, cwd=tmp_path, manifest=manifest,
            )
            run_id = run.id
        async with db.session() as s:
            await stop_run(s, docker, alloc, bc, run_id=run_id, reason="manual")
        bc.events.clear()
        async with db.session() as s:
            # 2ª chamada não levanta nem broadcasta
            await stop_run(s, docker, alloc, bc, run_id=run_id, reason="manual")
        assert bc.events == []
    finally:
        await db.close()


@pytest.mark.integration
async def test_stop_run_unknown_id_is_noop(tmp_path: Path) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 't.db'}")
    await db.bootstrap()
    bc = CollectingBroadcaster()
    try:
        async with db.session() as s:
            await stop_run(
                s, FakeDockerOps(),
                PortAllocator(socket_factory=_MockSock),
                bc, run_id="ghost", reason="manual",
            )
        assert bc.events == []
    finally:
        await db.close()


@pytest.mark.integration
async def test_stop_run_tolerates_docker_errors(tmp_path: Path) -> None:
    """Container já morto, network já removida — stop_run continua e marca
    `stopped` sem propagar erros."""
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 't.db'}")
    await db.bootstrap()
    docker = FakeDockerOps()
    alloc = PortAllocator(socket_factory=_MockSock)
    bc = CollectingBroadcaster()
    try:
        _, task = await _seed_task(db)
        manifest = _manifest("version: '1'\nservices: {a: {image: x}}")
        async with db.session() as s:
            run = await start_run(
                s, docker, alloc, bc,
                task_id=task.id, cwd=tmp_path, manifest=manifest,
            )
            run_id = run.id

        # Substituir docker por um que falha em stop/rm/network_rm
        class FailingDocker(FakeDockerOps):
            async def stop(self, *a: Any, **kw: Any) -> None:
                raise DockerError("already dead", stderr="")
            async def rm(self, cid: str) -> None:
                raise DockerError("not found", stderr="")
            async def network_rm(self, name: str) -> None:
                raise DockerError("no such network", stderr="")

        async with db.session() as s:
            await stop_run(
                s, FailingDocker(), alloc, bc,
                run_id=run_id, reason="manual",
            )

        async with db.session() as s:
            row = await s.get(RunInstance, run_id)
            assert row.status == "stopped"
    finally:
        await db.close()


# === get_active_run =========================================================


@pytest.mark.integration
async def test_get_active_run_returns_none_when_no_run(tmp_path: Path) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 't.db'}")
    await db.bootstrap()
    try:
        _, task = await _seed_task(db)
        async with db.session() as s:
            assert await get_active_run(s, task.id) is None
    finally:
        await db.close()


@pytest.mark.integration
async def test_get_active_run_returns_only_unfinished(tmp_path: Path) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 't.db'}")
    await db.bootstrap()
    docker = FakeDockerOps()
    alloc = PortAllocator(socket_factory=_MockSock)
    bc = CollectingBroadcaster()
    try:
        _, task = await _seed_task(db)
        manifest = _manifest("version: '1'\nservices: {a: {image: x}}")
        async with db.session() as s:
            run = await start_run(
                s, docker, alloc, bc,
                task_id=task.id, cwd=tmp_path, manifest=manifest,
            )
            run_id = run.id
        # Stop → ended_at set → get_active_run retorna None
        async with db.session() as s:
            await stop_run(s, docker, alloc, bc, run_id=run_id, reason="manual")
        async with db.session() as s:
            assert await get_active_run(s, task.id) is None
    finally:
        await db.close()


# === Helpers =================================================================


class _MockSock:
    """Stub do socket que sempre permite bind (todas portas livres)."""
    def setsockopt(self, *a: Any, **kw: Any) -> None: pass
    def bind(self, *a: Any, **kw: Any) -> None: pass
    def close(self) -> None: pass
