from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.api._deps import get_db_session
from orchestrator.core.projects import ProjectNotFoundError
from orchestrator.core.worktrees import list_project_worktrees


class WorktreeRead(BaseModel):
    id: str
    project_id: str
    path: str
    branch: str | None

    model_config = {"from_attributes": True}


router = APIRouter(prefix="/projects", tags=["worktrees"])


@router.get("/{project_id}/worktrees", response_model=list[WorktreeRead])
async def get_worktrees(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[WorktreeRead]:
    try:
        worktrees = await list_project_worktrees(session, project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [WorktreeRead.model_validate(w) for w in worktrees]
