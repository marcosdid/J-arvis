from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.api._deps import get_db_session, resolve_runtime
from orchestrator.core.runs import get_active_run, stop_run
from orchestrator.core.sessions import (
    SessionNotFoundError,
    list_sessions,
    stop_session,
)
from orchestrator.sandbox.runtime import SessionRuntime
from orchestrator.store.models import ClaudeSession


class SessionRead(BaseModel):
    id: str
    task_id: str
    cwd: str
    status: str
    pid: int | None
    jail_id: str | None
    started_at: datetime
    ended_at: datetime | None

    model_config = {"from_attributes": True}


router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionRead])
async def get_sessions(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[SessionRead]:
    rows = await list_sessions(session)
    return [SessionRead.model_validate(r) for r in rows]


@router.post("/{session_id}/stop", status_code=204)
async def stop_session_route(
    session_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    runtime: Annotated[SessionRuntime, Depends(resolve_runtime)],
) -> Response:
    registry = request.app.state.token_registry
    # Captura task_id ANTES do stop_session pra usar no F6 layer 2 hook.
    # task_id é FK NOT NULL (ADR-0012): se row existe, task_id existe.
    row = await session.get(ClaudeSession, session_id)
    task_id = row.task_id if row is not None else None
    try:
        await stop_session(session, runtime, session_id, token_registry=registry)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # F6 lifecycle layer 2 (ADR-0018): stop run ativa da mesma task. Skipa
    # graceful se F6 deps não estão wiradas (fluxo F1-F5 isolado).
    # task_id é não-None aqui — se row era None, stop_session teria raised.
    assert task_id is not None
    docker = getattr(request.app.state, "docker_ops", None)
    allocator = getattr(request.app.state, "port_allocator", None)
    broadcaster = getattr(request.app.state, "ws_broadcaster", None)
    if docker is not None and allocator is not None and broadcaster is not None:
        active_run = await get_active_run(session, task_id)
        if active_run is not None:
            await stop_run(
                session, docker, allocator, broadcaster,
                run_id=active_run.id, reason="session_stopped",
            )

    return Response(status_code=204)
