"""F6 Run from Panel — start_run, stop_run, state machine.

Orquestração:
- 1 run ativa por task (partial unique index garante).
- State machine: pending → building → seeding → ready; ou → failed
  em qualquer ponto. stop_run leva ready → stopping → stopped.
- Atomic rollback em 3 camadas: containers (Docker), network (Docker),
  ports (allocator) — DB row sempre persiste, com status `failed` e
  `error_message` populado pra UI.

Lock: confiamos no partial unique do schema (`ix_run_instances_active_task`
em F6.a) — INSERT concorrente do segundo run gera IntegrityError, capturado
como `RunAlreadyActiveError`. Não usamos asyncio.Lock por-task; o DB
constraint é suficiente pro modelo single-daemon single-DB.
"""
import asyncio
import contextlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.core.manifest import (
    HealthcheckSpec,
    ManifestSpec,
    SeedSpec,
    ServiceSpec,
    resolve_substitutions,
)
from orchestrator.core.port_allocator import PortAllocator
from orchestrator.core.slug import slugify_for_branch
from orchestrator.core.worktrees import list_worktrees_for_task
from orchestrator.events.broadcaster import WsBroadcaster
from orchestrator.events.envelope import WsEvent
from orchestrator.sandbox.docker_ops import (
    ContainerSpec,
    DockerError,
    DockerOps,
)
from orchestrator.store.models import Project, RunInstance, Task

_log = logging.getLogger(__name__)


# === Public errors ============================================================


class RunStartError(Exception):
    """Base pra erros de start_run."""


class RunAlreadyActiveError(RunStartError):
    """Já existe RunInstance ativa pra essa task (409)."""


class TaskNotEligibleForRunError(RunStartError):
    """Task não está em `in_progress`/`review` (422)."""


class _RunFailureError(Exception):
    """Falha interna durante start_run; carrega `service` opcional pra erro.

    Não exposto fora do módulo — capturado pra rollback + broadcast."""

    def __init__(self, msg: str, service: str | None = None) -> None:
        super().__init__(msg)
        self.service = service


StopReason = Literal["manual", "session_stopped", "task_terminal"]


# === State machine helpers ====================================================


def _now() -> datetime:
    return datetime.now(UTC)


def _services_payload(
    run: RunInstance, manifest: ManifestSpec,
) -> list[dict[str, Any]]:
    """Snapshot dos serviços pra payload do WS event run.status."""
    ports = json.loads(run.ports_json or "{}")
    containers = json.loads(run.containers_json or "{}")
    out: list[dict[str, Any]] = []
    for name, svc in manifest.services.items():
        out.append({
            "name": name,
            "state": run.status,
            "port_host": ports.get(name),
            "port_container": svc.port,
            "container_id": containers.get(name),
            "error": None,
        })
    return out


async def _set_status(
    db: AsyncSession,
    run: RunInstance,
    status: str,
    broadcaster: WsBroadcaster,
    manifest: ManifestSpec,
) -> None:
    run.status = status
    await db.commit()
    await broadcaster.publish(WsEvent.run_status(
        task_id=run.task_id,
        run_id=run.id,
        status=status,
        services=_services_payload(run, manifest),
    ))


# === Topological sort =========================================================


def _topo_sort(manifest: ManifestSpec) -> list[str]:
    """Retorna service names em ordem topológica (deps primeiro).

    Manifest já validou ausência de ciclos; aqui só ordenamos. Estabilidade:
    se múltiplos services têm in_degree=0, mantém ordem do dict (insertion).
    """
    in_degree: dict[str, int] = {
        name: len(svc.depends_on) for name, svc in manifest.services.items()
    }
    ready = [name for name in manifest.services if in_degree[name] == 0]
    order: list[str] = []
    while ready:
        n = ready.pop(0)
        order.append(n)
        for other_name, other_svc in manifest.services.items():
            if n in other_svc.depends_on:
                in_degree[other_name] -= 1
                if in_degree[other_name] == 0:
                    ready.append(other_name)
    return order


# === Container spec composition ==============================================


def _service_image_tag(run_id: str, svc_name: str, svc: ServiceSpec) -> str:
    if svc.image:
        return svc.image
    return f"jarvis-run-{run_id[:8]}-{svc_name}"


def _service_container_name(run_id: str, svc_name: str) -> str:
    return f"jarvis-run-{run_id[:8]}-{svc_name}"


def _service_volumes(
    svc: ServiceSpec, cwd: Path,
) -> tuple[tuple[str, str], ...]:
    """Mount source code conforme `effective_mount_source()`.

    Build-based service: mounts `<cwd>/<build_path>` em /app. Image-based
    service com mount_source explicit True: no-op (sem path canônico —
    documente como caveat futuro)."""
    if not svc.effective_mount_source():
        return ()
    if svc.build is None:
        return ()
    return ((str(cwd / svc.build), "/app"),)


def _build_container_spec(
    svc_name: str,
    svc: ServiceSpec,
    *,
    run_id: str,
    cwd: Path,
    network: str,
    ports_host: dict[str, int],
) -> ContainerSpec:
    env = resolve_substitutions(
        svc.env,
        ports_host=ports_host,
        run_id=run_id,
        cwd=str(cwd),
    )
    port_map: dict[int, int] = {}
    if svc.port is not None and svc_name in ports_host:
        port_map[ports_host[svc_name]] = svc.port
    return ContainerSpec(
        name=_service_container_name(run_id, svc_name),
        image=_service_image_tag(run_id, svc_name, svc),
        network=network,
        env=env,
        port_map=port_map,
        volumes=_service_volumes(svc, cwd),
        command=tuple(svc.command) if svc.command else None,
    )


# === Health / seed ===========================================================


async def _wait_healthy(
    docker: DockerOps, container_id: str, hc: HealthcheckSpec,
) -> None:
    for _ in range(hc.retries):
        code, _, _ = await docker.run_in_container(container_id, hc.command)
        if code == 0:
            return
        await asyncio.sleep(hc.interval)
    raise _RunFailureError(
        f"healthcheck timeout after {hc.retries} retries"
    )


async def _run_seed(
    docker: DockerOps, container_id: str, seed: SeedSpec,
) -> None:
    code, _, stderr = await docker.run_in_container(container_id, seed.command)
    if code != 0:
        raise _RunFailureError(f"seed failed (exit {code}): {stderr.strip()}")


# === Rollback ================================================================


async def _allocate_ports(
    port_allocator: PortAllocator,
    manifest: ManifestSpec,
    order: list[str],
    run: RunInstance,
    ports_host: dict[str, int],
    db: AsyncSession,
) -> None:
    for svc_name in order:
        svc = manifest.services[svc_name]
        if svc.port is not None:
            ports_host[svc_name] = await port_allocator.allocate()
    run.ports_json = json.dumps(ports_host)
    await db.commit()


async def _build_images(
    docker: DockerOps,
    manifest: ManifestSpec,
    order: list[str],
    cwd: Path,
    run_id: str,
) -> None:
    for svc_name in order:
        svc = manifest.services[svc_name]
        if svc.build is None:
            continue
        try:
            await docker.build(
                context=cwd / svc.build,
                dockerfile=svc.dockerfile,
                tag=_service_image_tag(run_id, svc_name, svc),
            )
        except DockerError as e:
            raise _RunFailureError(
                f"build failed: {e.stderr}", service=svc_name,
            ) from e


async def _spawn_containers(
    docker: DockerOps,
    db: AsyncSession,
    run: RunInstance,
    manifest: ManifestSpec,
    order: list[str],
    run_id: str,
    cwd: Path,
    ports_host: dict[str, int],
    containers: dict[str, str],
) -> None:
    for svc_name in order:
        svc = manifest.services[svc_name]
        spec = _build_container_spec(
            svc_name, svc,
            run_id=run_id, cwd=cwd, network=run.network_name,
            ports_host=ports_host,
        )
        try:
            cid = await docker.container_start(spec)
        except DockerError as e:
            raise _RunFailureError(
                f"container_start failed: {e.stderr}", service=svc_name,
            ) from e
        containers[svc_name] = cid
        run.containers_json = json.dumps(containers)
        await db.commit()
        if svc.healthcheck is not None:
            try:
                await _wait_healthy(docker, cid, svc.healthcheck)
            except _RunFailureError as e:
                e.service = svc_name
                raise
        if svc.seed is not None:
            try:
                await _run_seed(docker, cid, svc.seed)
            except _RunFailureError as e:
                e.service = svc_name
                raise


async def _rollback(
    docker: DockerOps,
    port_allocator: PortAllocator,
    *,
    containers: dict[str, str],
    network_name: str,
    network_created: bool,
    ports_host: dict[str, int],
) -> None:
    """Best-effort cleanup. Cada erro é logado mas não impede o próximo step."""
    for svc_name, cid in containers.items():
        try:
            await docker.stop(cid, force=True)
        except DockerError as e:
            _log.warning("rollback: stop %s (%s) failed: %s", svc_name, cid, e)
        try:
            await docker.rm(cid)
        except DockerError as e:
            _log.warning("rollback: rm %s (%s) failed: %s", svc_name, cid, e)
    if network_created:
        try:
            await docker.network_rm(network_name)
        except DockerError as e:
            _log.warning("rollback: network_rm %s failed: %s", network_name, e)
    for port in ports_host.values():
        await port_allocator.release(port)


# === Public API ==============================================================


async def get_active_run(
    db: AsyncSession, task_id: str,
) -> RunInstance | None:
    result = await db.execute(
        select(RunInstance)
        .where(RunInstance.task_id == task_id, RunInstance.ended_at.is_(None))
    )
    return result.scalar_one_or_none()


async def start_run(
    db: AsyncSession,
    docker: DockerOps,
    port_allocator: PortAllocator,
    broadcaster: WsBroadcaster,
    *,
    task_id: str,
    cwd: Path,
    manifest: ManifestSpec,
) -> RunInstance:
    """Sobe a stack pra `task_id` usando `manifest` em `cwd`.

    Raises:
        TaskNotEligibleForRunError: task estado ∉ {in_progress, review}.
        RunAlreadyActiveError: já existe run ativa pra essa task.
    """
    task = await db.get(Task, task_id)
    if task is None:
        raise TaskNotEligibleForRunError(f"task not found: {task_id}")
    if task.state not in ("in_progress", "review"):
        raise TaskNotEligibleForRunError(
            f"task state '{task.state}' not in (in_progress, review)"
        )

    run = RunInstance(
        task_id=task_id,
        cwd=str(cwd),
        manifest_path=str(cwd / ".orchestrator" / "run.yml"),
        network_name=f"jarvis-run-{uuid4().hex[:8]}",
        status="pending",
    )
    db.add(run)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise RunAlreadyActiveError(
            f"task {task_id} already has an active run"
        ) from e
    await db.refresh(run)
    run_id = run.id
    order = _topo_sort(manifest)

    ports_host: dict[str, int] = {}
    containers: dict[str, str] = {}
    network_created = False

    try:
        await _allocate_ports(port_allocator, manifest, order, run, ports_host, db)
        await _set_status(db, run, "building", broadcaster, manifest)
        await _build_images(docker, manifest, order, cwd, run_id)
        await docker.network_create(run.network_name)
        network_created = True
        await _set_status(db, run, "seeding", broadcaster, manifest)
        await _spawn_containers(
            docker, db, run, manifest, order, run_id, cwd, ports_host, containers,
        )
        await _set_status(db, run, "ready", broadcaster, manifest)
        return run

    except DockerError as e:
        # Catch DockerError from network_create only — other Docker calls are
        # wrapped in helpers that translate to _RunFailureError already.
        failure = _RunFailureError(f"network create failed: {e.stderr}")
        await _handle_failure(
            failure, docker, port_allocator, db, run, broadcaster,
            containers=containers, network_created=network_created,
            ports_host=ports_host,
        )
        raise RunStartError(str(failure)) from failure

    except _RunFailureError as e:
        await _handle_failure(
            e, docker, port_allocator, db, run, broadcaster,
            containers=containers, network_created=network_created,
            ports_host=ports_host,
        )
        raise RunStartError(str(e)) from e


async def _handle_failure(
    failure: "_RunFailureError",
    docker: DockerOps,
    port_allocator: PortAllocator,
    db: AsyncSession,
    run: RunInstance,
    broadcaster: WsBroadcaster,
    *,
    containers: dict[str, str],
    network_created: bool,
    ports_host: dict[str, int],
) -> None:
    """Atomic rollback + persist failed state + broadcast run.failed."""
    await _rollback(
        docker, port_allocator,
        containers=containers,
        network_name=run.network_name,
        network_created=network_created,
        ports_host=ports_host,
    )
    run.status = "failed"
    run.error_message = str(failure)
    run.ended_at = _now()
    await db.commit()
    await broadcaster.publish(WsEvent.run_failed(
        task_id=run.task_id, run_id=run.id,
        service=failure.service, error=str(failure),
    ))


async def stop_run(
    db: AsyncSession,
    docker: DockerOps,
    port_allocator: PortAllocator,
    broadcaster: WsBroadcaster,
    *,
    run_id: str,
    reason: StopReason,
) -> None:
    """Para a stack. Idempotente: re-chamadas em run já parada são no-op."""
    run = await db.get(RunInstance, run_id)
    if run is None or run.ended_at is not None:
        return

    run.status = "stopping"
    await db.commit()

    containers = json.loads(run.containers_json or "{}")
    for svc_name, cid in containers.items():
        try:
            await docker.stop(cid, force=True)
        except DockerError as e:
            _log.warning("stop_run: stop %s (%s) failed: %s", svc_name, cid, e)
        try:
            await docker.rm(cid)
        except DockerError as e:
            _log.warning("stop_run: rm %s (%s) failed: %s", svc_name, cid, e)

    try:
        await docker.network_rm(run.network_name)
    except DockerError as e:
        _log.warning("stop_run: network_rm failed: %s", e)

    ports = json.loads(run.ports_json or "{}")
    for port in ports.values():
        await port_allocator.release(port)

    run.status = "stopped"
    run.ended_at = _now()
    await db.commit()

    await broadcaster.publish(WsEvent.run_stopped(
        task_id=run.task_id, run_id=run.id, reason=reason,
    ))


async def derive_run_cwd(db: AsyncSession, task: Task) -> Path:
    """cwd da run = cwd da sessão ativa (se houver) OU derivado do
    project.path + branch slug (mesmo cálculo de F5)."""
    worktrees = await list_worktrees_for_task(db, task.id)
    if worktrees:
        if len(worktrees) == 1:
            return Path(worktrees[0].path)
        return Path(worktrees[0].path).parent
    project = await db.get(Project, task.project_id)
    if project is None:  # pragma: no cover — FK should prevent
        raise TaskNotEligibleForRunError(f"project not found for task {task.id}")
    branch = task.branch or slugify_for_branch(task.title)
    p = Path(project.path)
    return p.parent / f"{p.name}--{branch}"


async def cleanup_orphan_runs_at_startup(
    db: AsyncSession, docker: DockerOps, port_allocator: PortAllocator,
) -> None:
    """Na inicialização do daemon, marca todas runs com `ended_at IS NULL`
    como `stopped` e tenta limpar containers/network/ports.

    Container Docker pode ter sobrevivido ao restart; best-effort kill+rm.
    Network bridge orphan: rm best-effort. Ports: liberar do allocator
    (não estavam reservadas porque é instância nova; mas registramos
    pra prevenir realocação).
    """
    result = await db.execute(
        select(RunInstance).where(RunInstance.ended_at.is_(None))
    )
    runs = result.scalars().all()
    for run in runs:
        containers = json.loads(run.containers_json or "{}")
        for cid in containers.values():
            with contextlib.suppress(DockerError):
                await docker.stop(cid, force=True)
            with contextlib.suppress(DockerError):
                await docker.rm(cid)
        with contextlib.suppress(DockerError):
            await docker.network_rm(run.network_name)
        ports = json.loads(run.ports_json or "{}")
        for port in ports.values():
            await port_allocator.release(port)
        run.status = "stopped"
        run.ended_at = _now()
        run.error_message = "orphaned by daemon restart"
    await db.commit()


__all__ = [
    "RunAlreadyActiveError",
    "RunStartError",
    "StopReason",
    "TaskNotEligibleForRunError",
    "cleanup_orphan_runs_at_startup",
    "derive_run_cwd",
    "get_active_run",
    "start_run",
    "stop_run",
]
