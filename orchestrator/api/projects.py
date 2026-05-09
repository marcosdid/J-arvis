from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.api._deps import get_db_session
from orchestrator.core.projects import (
    DuplicateProjectError,
    NotAGitRepoError,
    PathDoesNotExistError,
    ProjectNotFoundError,
    create_project,
    delete_project,
    list_projects,
)


class ProjectCreatePayload(BaseModel):
    name: str
    path: str


class ProjectRead(BaseModel):
    id: str
    name: str
    path: str
    created_at: datetime

    model_config = {"from_attributes": True}


router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", status_code=201, response_model=ProjectRead)
async def post_project(
    payload: ProjectCreatePayload,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProjectRead:
    try:
        project = await create_project(session, payload.name, payload.path)
    except (PathDoesNotExistError, NotAGitRepoError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DuplicateProjectError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ProjectRead.model_validate(project)


@router.get("", response_model=list[ProjectRead])
async def get_projects(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[ProjectRead]:
    projects = await list_projects(session)
    return [ProjectRead.model_validate(p) for p in projects]


@router.delete("/{project_id}", status_code=204)
async def delete_project_route(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    try:
        await delete_project(session, project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
