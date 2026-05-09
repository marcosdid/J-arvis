from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.api._deps import get_db_session, resolve_runtime
from orchestrator.core.sessions import (
    SessionNotFoundError,
    WorktreeNotFoundError,
    list_sessions,
    start_session,
    stop_session,
)
from orchestrator.sandbox.runtime import SessionRuntime


class SessionCreatePayload(BaseModel):
    worktree_id: str


class SessionRead(BaseModel):
    id: str
    worktree_id: str
    status: str
    pid: int | None
    jail_id: str | None
    started_at: datetime
    ended_at: datetime | None

    model_config = {"from_attributes": True}


router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", status_code=201, response_model=SessionRead)
async def post_session(
    payload: SessionCreatePayload,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    runtime: Annotated[SessionRuntime, Depends(resolve_runtime)],
) -> SessionRead:
    registry = request.app.state.token_registry
    base_url = request.app.state.hook_base_url
    try:
        row = await start_session(
            session,
            runtime,
            payload.worktree_id,
            token_registry=registry,
            base_url=base_url,
        )
    except WorktreeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SessionRead.model_validate(row)


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
    try:
        await stop_session(session, runtime, session_id, token_registry=registry)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)
