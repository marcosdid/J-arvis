import asyncio
from collections import defaultdict
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.api._deps import get_db_session, resolve_runtime
from orchestrator.core.sessions import (
    WorktreeNotFoundError,
    start_session,
)
from orchestrator.core.tasks import (
    InvalidTaskTitleError,
    InvalidTransitionError,
    ProjectNotFoundForTaskError,
    TaskAlreadyHasActiveSessionError,
    TaskInTerminalStateError,
    TaskNotFoundError,
    create_task,
    get_task,
    list_tasks,
    update_task,
)
from orchestrator.events.envelope import WsEvent
from orchestrator.sandbox.runtime import SessionRuntime
from orchestrator.store.models import ClaudeSession


class TaskCreatePayload(BaseModel):
    project_id: str
    title: str
    description: str = ""


class TaskPatchPayload(BaseModel):
    title: str | None = None
    description: str | None = None
    state: str | None = None


class TaskRead(BaseModel):
    id: str
    project_id: str
    title: str
    description: str
    state: str
    template: str | None
    permission_profile: str | None
    created_at: datetime
    updated_at: datetime
    active_session_id: str | None = None

    model_config = {"from_attributes": True}


class SessionCreatePayload(BaseModel):
    worktree_id: str


class SessionRead(BaseModel):
    id: str
    worktree_id: str
    task_id: str
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
) -> TaskRead:
    try:
        task = await create_task(
            db,
            project_id=payload.project_id,
            title=payload.title,
            description=payload.description,
        )
    except InvalidTaskTitleError as exc:
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
) -> TaskRead:
    try:
        row, previous_state = await update_task(
            db,
            task_id,
            title=payload.title,
            description=payload.description,
            state=payload.state,
        )
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidTaskTitleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    broadcaster = request.app.state.ws_broadcaster
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
    payload: SessionCreatePayload,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    runtime: Annotated[SessionRuntime, Depends(resolve_runtime)],
) -> SessionRead:
    registry = request.app.state.token_registry
    base_url = request.app.state.hook_base_url
    broadcaster = request.app.state.ws_broadcaster

    try:
        task = await get_task(db, task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    prev_state = task.state

    async with _task_start_locks[task_id]:
        try:
            row = await start_session(
                db,
                runtime,
                task_id=task_id,
                worktree_id=payload.worktree_id,
                token_registry=registry,
                base_url=base_url,
            )
        except TaskNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except TaskInTerminalStateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except TaskAlreadyHasActiveSessionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except WorktreeNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    await db.refresh(task)
    if broadcaster is not None and task.state != prev_state:
        await broadcaster.publish(WsEvent.task_updated(
            task_id=task_id,
            project_id=task.project_id,
            title=task.title,
            new_state=task.state,
            previous_state=prev_state,
        ))

    return SessionRead.model_validate(row)
