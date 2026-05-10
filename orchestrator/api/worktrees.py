from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.api._deps import get_db_session, resolve_git_ops
from orchestrator.core.git import GitWorktreeError, GitWorktreeOps
from orchestrator.core.projects import ProjectNotFoundError
from orchestrator.core.worktrees import (
    WorktreeNotFoundError,
    WorktreeNotOrphanError,
    delete_worktree,
    list_project_worktrees,
)
from orchestrator.store.models import Repository


class WorktreeRead(BaseModel):
    id: str
    repository_id: str
    repository_name: str
    task_id: str | None
    path: str
    branch: str | None
    is_orphan: bool

    model_config = {"from_attributes": True}


router = APIRouter(prefix="/projects", tags=["worktrees"])
worktree_router = APIRouter(prefix="/worktrees", tags=["worktrees"])


@router.get("/{project_id}/worktrees", response_model=list[WorktreeRead])
async def get_worktrees(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    git: Annotated[GitWorktreeOps, Depends(resolve_git_ops)],
) -> list[WorktreeRead]:
    try:
        worktrees = await list_project_worktrees(session, git, project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    result: list[WorktreeRead] = []
    for w in worktrees:
        repo = await session.get(Repository, w.repository_id)
        result.append(WorktreeRead(
            id=w.id,
            repository_id=w.repository_id,
            repository_name=repo.name if repo else "",
            task_id=w.task_id,
            path=w.path,
            branch=w.branch,
            is_orphan=w.task_id is None,
        ))
    return result


@worktree_router.delete("/{worktree_id}", status_code=204)
async def delete_worktree_route(
    worktree_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    git: Annotated[GitWorktreeOps, Depends(resolve_git_ops)],
) -> None:
    try:
        await delete_worktree(session, git, worktree_id)
    except WorktreeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorktreeNotOrphanError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except GitWorktreeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
