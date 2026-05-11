"""F6.f API routes — POST /tasks/{id}/runs, /runs/{id}/stop, /runs/{id}/logs (SSE).

Endpoints:
- POST /api/tasks/{task_id}/runs            → start run; 201 RunRead
- GET  /api/tasks/{task_id}/run             → current run (or 404)
- POST /api/runs/{run_id}/stop              → stop; 204 idempotent
- GET  /api/runs/{run_id}/logs?service=X    → SSE stream linhas docker logs
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.api._deps import (
    get_db_session,
    resolve_broadcaster,
    resolve_docker_ops,
    resolve_port_allocator,
)
from orchestrator.core.manifest import (
    ManifestInvalidError,
    ManifestMissingError,
    ManifestSpec,
    load_manifest,
)
from orchestrator.core.port_allocator import PortAllocator
from orchestrator.core.runs import (
    RunAlreadyActiveError,
    RunStartError,
    TaskNotEligibleForRunError,
    derive_run_cwd,
    get_active_run,
    start_run,
    stop_run,
)
from orchestrator.events.broadcaster import WsBroadcaster
from orchestrator.sandbox.docker_ops import DockerOps
from orchestrator.store.models import Project, RunInstance, Task


class ServiceStatusRead(BaseModel):
    model_config = {"extra": "forbid"}
    name: str
    state: str
    port_host: int | None
    port_container: int | None
    container_id: str | None
    error: str | None


class RunRead(BaseModel):
    model_config = {"extra": "forbid", "from_attributes": True}
    id: str
    task_id: str
    cwd: str
    manifest_path: str
    status: str
    services: list[ServiceStatusRead]
    network_name: str
    started_at: datetime
    ended_at: datetime | None
    error_message: str | None


def _services_for_response(
    run: RunInstance, manifest: ManifestSpec | None,
) -> list[ServiceStatusRead]:
    """Build payload de serviços a partir do RunInstance + manifest opcional.

    Se o manifesto não é mais carregável (foi editado/removido depois do
    start), retorna lista vazia em vez de quebrar."""
    if manifest is None:
        return []
    ports = json.loads(run.ports_json or "{}")
    containers = json.loads(run.containers_json or "{}")
    out: list[ServiceStatusRead] = []
    for name, svc in manifest.services.items():
        out.append(ServiceStatusRead(
            name=name,
            state=run.status,
            port_host=ports.get(name),
            port_container=svc.port,
            container_id=containers.get(name),
            error=run.error_message if run.status == "failed" else None,
        ))
    return out


def _to_run_read(run: RunInstance, manifest: ManifestSpec | None) -> RunRead:
    return RunRead(
        id=run.id,
        task_id=run.task_id,
        cwd=run.cwd,
        manifest_path=run.manifest_path,
        status=run.status,
        services=_services_for_response(run, manifest),
        network_name=run.network_name,
        started_at=run.started_at,
        ended_at=run.ended_at,
        error_message=run.error_message,
    )


task_router = APIRouter(prefix="/tasks/{task_id}", tags=["runs"])
run_router = APIRouter(prefix="/runs", tags=["runs"])


@task_router.post("/runs", response_model=RunRead, status_code=201)
async def create_run(
    task_id: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    docker: Annotated[DockerOps, Depends(resolve_docker_ops)],
    allocator: Annotated[PortAllocator, Depends(resolve_port_allocator)],
    broadcaster: Annotated[WsBroadcaster, Depends(resolve_broadcaster)],
) -> RunRead:
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(404, "task not found")
    project = await db.get(Project, task.project_id)
    assert project is not None  # FK guarantee

    try:
        manifest = load_manifest(Path(project.path))
    except ManifestMissingError:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "manifest_missing",
                "bootstrap_url": f"/api/tasks/{task_id}/bootstrap-manifest",
            },
        ) from None
    except ManifestInvalidError as e:
        raise HTTPException(
            status_code=422,
            detail={"error": "manifest_invalid", "path": e.path, "msg": e.msg},
        ) from e

    cwd = await derive_run_cwd(db, task)

    try:
        run = await start_run(
            db, docker, allocator, broadcaster,
            task_id=task_id, cwd=cwd, manifest=manifest,
        )
    except TaskNotEligibleForRunError as e:
        raise HTTPException(422, str(e)) from e
    except RunAlreadyActiveError as e:
        raise HTTPException(409, str(e)) from e
    except RunStartError as e:
        raise HTTPException(500, f"run failed during start: {e}") from e

    return _to_run_read(run, manifest)


@task_router.get("/run", response_model=RunRead)
async def get_task_active_run(
    task_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> RunRead:
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(404, "task not found")
    run = await get_active_run(db, task_id)
    if run is None:
        raise HTTPException(404, "no active run for task")
    project = await db.get(Project, task.project_id)
    assert project is not None
    try:
        manifest: ManifestSpec | None = load_manifest(
            Path(project.path),
        )
    except (ManifestMissingError, ManifestInvalidError):
        manifest = None
    return _to_run_read(run, manifest)


@run_router.post("/{run_id}/stop", status_code=204)
async def stop_run_route(
    run_id: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    docker: Annotated[DockerOps, Depends(resolve_docker_ops)],
    allocator: Annotated[PortAllocator, Depends(resolve_port_allocator)],
    broadcaster: Annotated[WsBroadcaster, Depends(resolve_broadcaster)],
    reason: Literal["manual", "session_stopped", "task_terminal"] = "manual",
) -> None:
    await stop_run(
        db, docker, allocator, broadcaster,
        run_id=run_id, reason=reason,
    )


@run_router.get("/{run_id}/logs")
async def stream_logs_route(
    run_id: str,
    service: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    docker: Annotated[DockerOps, Depends(resolve_docker_ops)],
) -> StreamingResponse:
    """SSE: cada linha vira `data: {"service","stream","text"}\\n\\n`."""
    run = await db.get(RunInstance, run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    containers = json.loads(run.containers_json or "{}")
    container_id = containers.get(service)
    if container_id is None:
        raise HTTPException(404, f"service '{service}' not found in run")

    async def event_stream() -> Any:
        async for stream_name, text in docker.stream_logs(container_id):
            payload = json.dumps(
                {"service": service, "stream": stream_name, "text": text},
            )
            yield f"data: {payload}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
