"""Task domain: CRUD + state machine + lifecycle policies."""
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.store.models import Project, Task

_VALID_TRANSITIONS: frozenset[tuple[str, str]] = frozenset({
    ("idea", "ready"), ("idea", "discarded"),
    ("ready", "idea"), ("ready", "in_progress"), ("ready", "discarded"),
    ("in_progress", "review"), ("in_progress", "discarded"),
    ("review", "in_progress"), ("review", "done"), ("review", "discarded"),
    ("discarded", "idea"),
})


def is_valid_transition(frm: str, to: str) -> bool:
    if frm == to:
        return True
    return (frm, to) in _VALID_TRANSITIONS


class TaskNotFoundError(Exception):
    pass


class InvalidTransitionError(Exception):
    pass


class TaskAlreadyHasActiveSessionError(Exception):
    pass


class TaskInTerminalStateError(Exception):
    pass


class InvalidTaskTitleError(Exception):
    pass


class ProjectNotFoundForTaskError(Exception):
    pass


async def create_task(
    db: AsyncSession,
    *,
    project_id: str,
    title: str,
    description: str = "",
) -> Task:
    if not title or not title.strip():
        raise InvalidTaskTitleError("title cannot be empty or whitespace-only")
    project = await db.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundForTaskError(f"project not found: {project_id}")
    row = Task(project_id=project_id, title=title, description=description)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def list_tasks(
    db: AsyncSession,
    *,
    project_ids: Sequence[str] | None = None,
) -> Sequence[Task]:
    stmt = select(Task)
    if project_ids:
        stmt = stmt.where(Task.project_id.in_(project_ids))
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_task(db: AsyncSession, task_id: str) -> Task:
    row = await db.get(Task, task_id)
    if row is None:
        raise TaskNotFoundError(f"task not found: {task_id}")
    return row


async def update_task(
    db: AsyncSession,
    task_id: str,
    *,
    title: str | None = None,
    description: str | None = None,
    state: str | None = None,
) -> tuple[Task, str | None]:
    row = await get_task(db, task_id)
    await db.refresh(row)
    previous_state: str | None = None

    if title is not None:
        if not title.strip():
            raise InvalidTaskTitleError("title cannot be empty")
        row.title = title
    if description is not None:
        row.description = description
    if state is not None:
        if not is_valid_transition(row.state, state):
            raise InvalidTransitionError(
                f"invalid transition: {row.state} → {state}"
            )
        if state != row.state:
            previous_state = row.state
            row.state = state

    row.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(row)
    return row, previous_state
