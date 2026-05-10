from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.api._deps import get_db_session
from orchestrator.core.projects import (
    ProjectHasTasksError,
    ProjectNotFoundError,
    delete_project,
    list_projects,
)
from orchestrator.core.repositories import (
    NoGitReposError,
    detect_repos,
    list_project_repositories,
)
from orchestrator.store.models import Project, Repository


class ProjectCreatePayload(BaseModel):
    name: str
    path: str


class RepositoryRead(BaseModel):
    id: str
    name: str
    sub_path: str

    model_config = {"from_attributes": True}


class ProjectRead(BaseModel):
    id: str
    name: str
    path: str
    created_at: datetime
    repositories: list[RepositoryRead]

    model_config = {"from_attributes": True}


router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", status_code=201, response_model=ProjectRead)
async def post_project(
    payload: ProjectCreatePayload,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProjectRead:
    try:
        repo_specs = detect_repos(Path(payload.path))
    except NoGitReposError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    project = Project(name=payload.name, path=payload.path)
    session.add(project)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"a project with that path already exists: {payload.path}",
        ) from exc

    repo_rows: list[Repository] = []
    for spec in repo_specs:
        # Monorepo (sub_path=".") borrows the user-given project name; sub-repos keep their own.
        repo_name = project.name if spec.sub_path == "." else spec.name
        r = Repository(project_id=project.id, name=repo_name, sub_path=spec.sub_path)
        session.add(r)
        repo_rows.append(r)
    # Path uniqueness was caught at flush above; (project_id, sub_path) uniqueness
    # cannot be violated here because detect_repos returns distinct sub_paths.
    await session.commit()

    await session.refresh(project)
    for r in repo_rows:
        await session.refresh(r)

    return ProjectRead(
        id=project.id,
        name=project.name,
        path=project.path,
        created_at=project.created_at,
        repositories=[RepositoryRead.model_validate(r) for r in repo_rows],
    )


@router.get("", response_model=list[ProjectRead])
async def get_projects(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[ProjectRead]:
    projects = await list_projects(session)
    result: list[ProjectRead] = []
    for p in projects:
        repos = await list_project_repositories(session, p.id)
        result.append(ProjectRead(
            id=p.id,
            name=p.name,
            path=p.path,
            created_at=p.created_at,
            repositories=[RepositoryRead.model_validate(r) for r in repos],
        ))
    return result


@router.delete("/{project_id}", status_code=204)
async def delete_project_route(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    try:
        await delete_project(session, project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ProjectHasTasksError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
