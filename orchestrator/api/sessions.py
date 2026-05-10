from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.api._deps import get_db_session, resolve_runtime
from orchestrator.core.sessions import (
    SessionNotFoundError,
    list_sessions,
    stop_session,
)
from orchestrator.sandbox.runtime import SessionRuntime


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
    try:
        await stop_session(session, runtime, session_id, token_registry=registry)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)
