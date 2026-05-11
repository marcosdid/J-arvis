"""F6.h API — POST /api/tasks/{task_id}/bootstrap-manifest.

Spawn sessão Claude efêmera em `project.path` pra propor
`.orchestrator/run.yml`. Não cria `ClaudeSession` (sem `task_id`); só
um `JailHandle` que não rastreamos. O watcher async detecta o arquivo
salvo.
"""
import asyncio
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.api._deps import (
    get_db_session,
    resolve_broadcaster,
    resolve_catalog,
    resolve_runtime,
)
from orchestrator.core.bootstrap import watch_for_manifest
from orchestrator.core.catalog import Catalog
from orchestrator.events.broadcaster import WsBroadcaster
from orchestrator.sandbox.runtime import SessionRuntime
from orchestrator.store.models import Project, Task


class BootstrapSessionRead(BaseModel):
    model_config = {"extra": "forbid"}
    session_id: str
    cwd: str


router = APIRouter(prefix="/tasks/{task_id}", tags=["bootstrap"])


@router.post(
    "/bootstrap-manifest",
    response_model=BootstrapSessionRead,
    status_code=202,
)
async def bootstrap_manifest(
    task_id: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    runtime: Annotated[SessionRuntime, Depends(resolve_runtime)],
    broadcaster: Annotated[WsBroadcaster, Depends(resolve_broadcaster)],
    catalog: Annotated[Catalog, Depends(resolve_catalog)],
) -> BootstrapSessionRead:
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(404, "task not found")
    project = await db.get(Project, task.project_id)
    assert project is not None  # FK guarantee
    project_path = Path(project.path)
    (project_path / ".orchestrator").mkdir(exist_ok=True)

    # Spawn sessão efêmera (sem token/base_url → sem .claude/settings.json
    # nem hook plumbing). O usuário interage com Claude no terminal nativo;
    # daemon NÃO rastreia esse PID.
    await runtime.spawn(
        project_path,
        permission_profile=None,  # bootstrap usa fallback do catálogo
        catalog=catalog,
    )

    # Watcher polling em background. Não awaitamos — endpoint retorna 202
    # imediatamente; o watcher broadcasta bootstrap.proposed quando o
    # arquivo aparecer (ou desiste silenciosamente após 30min). Guarda
    # ref pra evitar GC prematuro (RUF006).
    watcher_task = asyncio.create_task(
        watch_for_manifest(project_path, broadcaster),
    )
    # Anexa ao app state pra não ser coletado mid-run; a fila é apenas
    # append-only — limpamos quando concluem.
    watchers: set[asyncio.Task[bool]] = getattr(
        request.app.state, "_bootstrap_watchers", set(),
    )
    watchers.add(watcher_task)
    watcher_task.add_done_callback(watchers.discard)
    request.app.state._bootstrap_watchers = watchers

    return BootstrapSessionRead(
        session_id=uuid4().hex,
        cwd=str(project_path),
    )
