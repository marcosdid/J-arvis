from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
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
    session: Annotated[AsyncSession, Depends(get_db_session)],
    runtime: Annotated[SessionRuntime, Depends(resolve_runtime)],
) -> SessionRead:
    try:
        row = await start_session(session, runtime, payload.worktree_id)
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
    session: Annotated[AsyncSession, Depends(get_db_session)],
    runtime: Annotated[SessionRuntime, Depends(resolve_runtime)],
) -> None:
    try:
        await stop_session(session, runtime, session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
