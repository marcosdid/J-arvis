from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.core.projects import ProjectNotFoundError
from orchestrator.core.worktrees import list_project_worktrees
from orchestrator.store.database import Database


class WorktreeRead(BaseModel):
    id: str
    project_id: str
    path: str
    branch: str | None

    model_config = {"from_attributes": True}


router = APIRouter(prefix="/projects", tags=["worktrees"])


def _resolve_database(request: Request) -> Database:
    db: Database | None = request.app.state.database
    if db is None:  # pragma: no cover
        raise RuntimeError("worktrees router mounted without a database")
    return db


async def _session(
    database: Annotated[Database, Depends(_resolve_database)],
) -> AsyncIterator[AsyncSession]:
    async with database.session() as s:
        yield s


@router.get("/{project_id}/worktrees", response_model=list[WorktreeRead])
async def get_worktrees(
    project_id: str,
    session: Annotated[AsyncSession, Depends(_session)],
) -> list[WorktreeRead]:
    try:
        worktrees = await list_project_worktrees(session, project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [WorktreeRead.model_validate(w) for w in worktrees]
