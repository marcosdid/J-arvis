"""Task domain: CRUD + state machine + lifecycle policies."""
import re
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.store.models import Project, Task, Worktree

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


class TaskHasActiveSessionError(Exception):
    """Raised when transitioning task to terminal state with active session."""


class BranchImmutableAfterFirstSessionError(Exception):
    """Raised when changing task.branch after worktrees have been created."""


class InvalidBranchOverrideError(Exception):
    """Raised when task.branch override fails the regex/length validation."""


_BRANCH_OVERRIDE_RE = re.compile(r"^[a-z0-9][a-z0-9._/-]*$")
_BRANCH_OVERRIDE_MAX = 200


async def _count_worktrees_for_task(db: AsyncSession, task_id: str) -> int:
    return (await db.execute(
        select(func.count())
        .select_from(Worktree)
        .where(Worktree.task_id == task_id)
    )).scalar_one()


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
    branch: str | None = None,
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
    if branch is not None:
        if (
            len(branch) > _BRANCH_OVERRIDE_MAX
            or not _BRANCH_OVERRIDE_RE.match(branch)
        ):
            raise InvalidBranchOverrideError(
                f"branch must match ^[a-z0-9][a-z0-9._/-]*$ "
                f"and be <= {_BRANCH_OVERRIDE_MAX} chars"
            )
        wts_count = await _count_worktrees_for_task(db, task_id)
        if wts_count > 0:
            raise BranchImmutableAfterFirstSessionError(
                "branch cannot be changed after worktrees were created; "
                "discard task and recreate"
            )
        row.branch = branch
    if state is not None:
        if not is_valid_transition(row.state, state):
            raise InvalidTransitionError(
                f"invalid transition: {row.state} → {state}"
            )
        if state in ("done", "discarded") and state != row.state:
            # Local import to avoid circular: core.sessions imports from core.tasks
            from orchestrator.core.sessions import _count_active_sessions
            active = await _count_active_sessions(db, task_id)
            if active > 0:
                raise TaskHasActiveSessionError(
                    "task has active session; "
                    "stop it before completing/discarding"
                )
        if state != row.state:
            previous_state = row.state
            row.state = state

    row.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(row)
    return row, previous_state


async def ensure_task_for_quick_session(
    db: AsyncSession,
    *,
    worktree_id: str,
) -> Task:
    """Create implicit task for a quick (worktree-driven) session."""
    worktree = await db.get(Worktree, worktree_id)
    if worktree is None:
        raise ProjectNotFoundForTaskError(f"worktree not found: {worktree_id}")
    branch = worktree.branch or "(detached)"
    title = f"Quick session · {branch}"
    row = Task(
        project_id=worktree.project_id,
        title=title,
        description="",
        state="in_progress",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row
