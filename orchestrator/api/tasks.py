import asyncio
from collections import defaultdict
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.api._deps import (
    get_db_session,
    resolve_catalog,
    resolve_git_ops,
    resolve_runtime,
)
from orchestrator.core.catalog import Catalog
from orchestrator.core.git import GitWorktreeError, GitWorktreeOps
from orchestrator.core.runs import get_active_run, stop_run
from orchestrator.core.sessions import (
    CwdAlreadyExistsError,
    start_session,
)
from orchestrator.core.slug import InvalidBranchSlugError
from orchestrator.core.tasks import (
    BranchImmutableAfterFirstSessionError,
    InvalidBranchOverrideError,
    InvalidTaskTitleError,
    InvalidTemplateError,
    InvalidTransitionError,
    ProjectNotFoundForTaskError,
    TaskAlreadyHasActiveSessionError,
    TaskHasActiveSessionError,
    TaskInTerminalStateError,
    TaskNotFoundError,
    create_task,
    get_task,
    list_tasks,
    update_task,
)
from orchestrator.core.worktrees import cleanup_task_worktrees
from orchestrator.events.envelope import WsEvent
from orchestrator.sandbox.runtime import SessionRuntime
from orchestrator.store.models import ClaudeSession


class TaskCreatePayload(BaseModel):
    project_id: str
    title: str
    description: str = ""
    branch: str | None = None
    template: str | None = None


class TaskPatchPayload(BaseModel):
    title: str | None = None
    description: str | None = None
    state: str | None = None
    branch: str | None = None


class TaskRead(BaseModel):
    id: str
    project_id: str
    title: str
    description: str
    state: str
    template: str | None
    permission_profile: str | None
    branch: str | None
    created_at: datetime
    updated_at: datetime
    active_session_id: str | None = None

    model_config = {"from_attributes": True}


class SessionCreatePayload(BaseModel):
    """F5 daemon picks the cwd; clients send empty body. ``extra=forbid``
    rejects legacy ``{"worktree_id": ...}`` clients with HTTP 422 (Pydantic).
    """

    model_config = {"extra": "forbid"}


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


router = APIRouter(prefix="/tasks", tags=["tasks"])

# Per-task asyncio locks prevent the check-then-insert race on 1-active-session constraint.
_task_start_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


async def _build_task_read(db: AsyncSession, task_id: str) -> TaskRead:
    row = await get_task(db, task_id)
    active = (await db.execute(
        select(ClaudeSession.id).where(
            ClaudeSession.task_id == task_id,
            ClaudeSession.status.notin_(["done", "error"]),
        ).limit(1)
    )).scalar_one_or_none()
    return TaskRead.model_validate(row).model_copy(update={"active_session_id": active})


@router.post("", status_code=201, response_model=TaskRead)
async def post_task(
    payload: TaskCreatePayload,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    catalog: Annotated[Catalog, Depends(resolve_catalog)],
) -> TaskRead:
    try:
        task = await create_task(
            db,
            project_id=payload.project_id,
            title=payload.title,
            description=payload.description,
            branch=payload.branch,
            template=payload.template,
            catalog=catalog,
        )
    except (InvalidTaskTitleError, InvalidBranchOverrideError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InvalidTemplateError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "template_not_in_catalog",
                "message": str(exc),
                "valid_templates": exc.valid_templates,
            },
        ) from exc
    except InvalidBranchSlugError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ProjectNotFoundForTaskError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    broadcaster = request.app.state.ws_broadcaster
    if broadcaster is not None:
        await broadcaster.publish(WsEvent.task_created(
            task_id=task.id,
            project_id=task.project_id,
            title=task.title,
            state=task.state,
        ))

    return TaskRead.model_validate(task).model_copy(update={"active_session_id": None})


@router.get("", response_model=list[TaskRead])
async def get_tasks(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    project_ids: Annotated[str | None, Query()] = None,
) -> list[TaskRead]:
    ids = project_ids.split(",") if project_ids else None
    rows = await list_tasks(db, project_ids=ids)
    if not rows:
        return []
    stmt = (
        select(ClaudeSession.task_id, func.min(ClaudeSession.id).label("active_id"))
        .where(
            ClaudeSession.task_id.in_([r.id for r in rows]),
            ClaudeSession.status.notin_(["done", "error"]),
        )
        .group_by(ClaudeSession.task_id)
    )
    active_by_task = dict((await db.execute(stmt)).all())
    return [
        TaskRead.model_validate(r).model_copy(
            update={"active_session_id": active_by_task.get(r.id)}
        )
        for r in rows
    ]


@router.get("/{task_id}", response_model=TaskRead)
async def get_task_route(
    task_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TaskRead:
    try:
        return await _build_task_read(db, task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{task_id}", response_model=TaskRead)
async def patch_task(
    task_id: str,
    payload: TaskPatchPayload,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    git: Annotated[GitWorktreeOps, Depends(resolve_git_ops)],
) -> TaskRead:
    try:
        row, previous_state = await update_task(
            db,
            task_id,
            title=payload.title,
            description=payload.description,
            state=payload.state,
            branch=payload.branch,
        )
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (
        InvalidTaskTitleError,
        InvalidTransitionError,
        BranchImmutableAfterFirstSessionError,
        InvalidBranchOverrideError,
        TaskHasActiveSessionError,
    ) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    broadcaster = request.app.state.ws_broadcaster

    if payload.state in ("done", "discarded") and previous_state is not None:
        # F6 lifecycle layer 3 (ADR-0018): stop run ativa antes do worktree
        # cleanup — containers Docker montam source via volume nos worktrees,
        # então parar run primeiro evita "broken bind mount" mid-cleanup.
        # Skipa graceful se F6 deps não estão wiradas (tests F1-F5 isoladas).
        docker = getattr(request.app.state, "docker_ops", None)
        allocator = getattr(request.app.state, "port_allocator", None)
        if docker is not None and allocator is not None and broadcaster is not None:
            active_run = await get_active_run(db, task_id)
            if active_run is not None:
                await stop_run(
                    db, docker, allocator, broadcaster,
                    run_id=active_run.id, reason="task_terminal",
                )
        await cleanup_task_worktrees(db, git, broadcaster, task_id)

    if broadcaster is not None and previous_state is not None:
        await broadcaster.publish(WsEvent.task_updated(
            task_id=row.id,
            project_id=row.project_id,
            title=row.title,
            new_state=row.state,
            previous_state=previous_state,
        ))

    return await _build_task_read(db, task_id)


@router.post("/{task_id}/sessions", status_code=201, response_model=SessionRead)
async def post_task_session(
    task_id: str,
    payload: SessionCreatePayload,  # Pydantic validates extra=forbid
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    runtime: Annotated[SessionRuntime, Depends(resolve_runtime)],
    git: Annotated[GitWorktreeOps, Depends(resolve_git_ops)],
) -> SessionRead:
    registry = request.app.state.token_registry
    base_url = request.app.state.hook_base_url
    broadcaster = request.app.state.ws_broadcaster

    async with _task_start_locks[task_id]:
        try:
            row = await start_session(
                db,
                runtime,
                git,
                task_id=task_id,
                token_registry=registry,
                base_url=base_url,
                broadcaster=broadcaster,
            )
        except TaskNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except TaskInTerminalStateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except TaskAlreadyHasActiveSessionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (InvalidBranchSlugError, CwdAlreadyExistsError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except GitWorktreeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return SessionRead.model_validate(row)
