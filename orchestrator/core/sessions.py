import contextlib
import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.core.git import GitWorktreeError, GitWorktreeOps
from orchestrator.core.repositories import list_project_repositories
from orchestrator.core.slug import slugify_for_branch
from orchestrator.core.tasks import (
    TaskAlreadyHasActiveSessionError,
    TaskInTerminalStateError,
    get_task,
)
from orchestrator.events.broadcaster import WsBroadcaster
from orchestrator.events.envelope import WsEvent
from orchestrator.hooks.tokens import TokenRegistry, generate_token
from orchestrator.sandbox.runtime import JailHandle, SessionRuntime
from orchestrator.store.models import (
    ClaudeSession,
    Project,
    Repository,
    Worktree,
)

_log = logging.getLogger(__name__)


class SessionStatus(StrEnum):
    EXECUTING = "executing"
    AWAITING_RESPONSE = "awaiting_response"
    IDLE = "idle"
    ERROR = "error"
    DONE = "done"


class WorktreeNotFoundError(Exception):
    pass


class SessionNotFoundError(Exception):
    pass


class CwdAlreadyExistsError(Exception):
    """Raised when the derived cwd already exists on disk before worktree creation."""


async def list_worktrees_for_task(
    session: AsyncSession, task_id: str
) -> list[Worktree]:
    """Worktrees of a task ordered by path. Will move to core/worktrees.py in F5.f."""
    result = await session.execute(
        select(Worktree).where(Worktree.task_id == task_id).order_by(Worktree.path)
    )
    return list(result.scalars().all())


def _derive_cwd(project_path: str, branch_slug: str) -> Path:
    p = Path(project_path)
    return p.parent / f"{p.name}--{branch_slug}"


def _derive_cwd_from_existing(worktrees: list[Worktree]) -> Path:
    if len(worktrees) == 1:
        return Path(worktrees[0].path)  # monorepo
    return Path(worktrees[0].path).parent  # multi-repo


async def _count_active_sessions(session: AsyncSession, task_id: str) -> int:
    return (await session.execute(
        select(func.count()).select_from(ClaudeSession).where(
            ClaudeSession.task_id == task_id,
            ClaudeSession.status.notin_([SessionStatus.DONE, SessionStatus.ERROR]),
        )
    )).scalar_one()


async def _create_worktrees_atomic(
    session: AsyncSession,
    git: GitWorktreeOps,
    project: Project,
    repos: Sequence[Repository],
    task_id: str,
    branch: str,
    cwd: Path,
) -> list[tuple[Worktree, Repository]]:
    """Create N worktrees atomically. On failure: rollback git ops + session, raise."""
    if cwd.exists():
        raise CwdAlreadyExistsError(f"cwd path '{cwd}' already exists")

    is_multi = len(repos) > 1
    if is_multi:
        cwd.mkdir(parents=False, exist_ok=False)

    created_pairs: list[tuple[Worktree, Repository]] = []
    try:
        for repo in repos:
            repo_full = Path(project.path) / repo.sub_path
            target = cwd / repo.name if is_multi else cwd
            await git.add(repo_full, target, branch)
            wt = Worktree(
                repository_id=repo.id,
                task_id=task_id,
                path=str(target),
                branch=branch,
            )
            session.add(wt)
            await session.flush()
            created_pairs.append((wt, repo))
        await session.commit()
    except Exception:
        await _rollback_worktrees(git, project, created_pairs)
        await session.rollback()
        if is_multi and cwd.exists():
            with contextlib.suppress(OSError):
                cwd.rmdir()
        raise
    return created_pairs


async def _rollback_worktrees(
    git: GitWorktreeOps,
    project: Project,
    created_pairs: list[tuple[Worktree, Repository]],
) -> None:
    """Best-effort rollback. Iterates in reverse to undo last-first."""
    for wt, repo in reversed(created_pairs):
        repo_full = Path(project.path) / repo.sub_path
        try:
            await git.remove(repo_full, Path(wt.path), force=True)
        except GitWorktreeError as exc:
            _log.warning(f"rollback failed for {wt.path}: {exc}")


async def start_session(
    session: AsyncSession,
    runtime: SessionRuntime,
    git: GitWorktreeOps,
    *,
    task_id: str,
    token_registry: TokenRegistry | None = None,
    base_url: str | None = None,
    broadcaster: WsBroadcaster | None = None,
) -> ClaudeSession:
    task = await get_task(session, task_id)
    await session.refresh(task)

    if task.state in ("done", "discarded"):
        raise TaskInTerminalStateError(
            f"cannot start session: task is in terminal state '{task.state}'"
        )

    active = await _count_active_sessions(session, task_id)
    if active > 0:
        raise TaskAlreadyHasActiveSessionError("task already has active session")

    project = await session.get(Project, task.project_id)
    repos = list(await list_project_repositories(session, project.id))

    branch = task.branch or slugify_for_branch(task.title)

    existing = await list_worktrees_for_task(session, task_id)
    if existing:
        cwd = _derive_cwd_from_existing(existing)
        new_worktree_pairs: list[tuple[Worktree, Repository]] = []
    else:
        cwd = _derive_cwd(project.path, branch)
        new_worktree_pairs = await _create_worktrees_atomic(
            session, git, project, repos, task_id, branch, cwd
        )

    prev_state = task.state
    if task.state in ("idea", "ready", "review"):
        task.state = "in_progress"
        task.updated_at = datetime.now(UTC)

    token = generate_token() if token_registry is not None else None
    try:
        handle = await runtime.spawn(cwd, token=token, base_url=base_url)
    except Exception:
        if new_worktree_pairs:
            await _rollback_worktrees(git, project, new_worktree_pairs)
        if prev_state != task.state:
            task.state = prev_state
            await session.commit()
        raise

    row = ClaudeSession(
        task_id=task_id,
        cwd=str(cwd),
        status=SessionStatus.EXECUTING,
        pid=handle.pid,
        jail_id=handle.id,
        started_at=handle.started_at,
        hook_token=token,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)

    if token_registry is not None and token is not None:
        token_registry.register(token, row.id)

    if broadcaster is not None:
        for wt, repo in new_worktree_pairs:
            await broadcaster.publish(WsEvent.worktree_created(
                worktree_id=wt.id,
                project_id=repo.project_id,
                repository_id=repo.id,
                task_id=task_id,
                path=wt.path,
                branch=wt.branch,
            ))

    return row


async def list_sessions(session: AsyncSession) -> Sequence[ClaudeSession]:
    result = await session.execute(select(ClaudeSession))
    return result.scalars().all()


_TERMINAL_STATUSES = frozenset({SessionStatus.DONE, SessionStatus.ERROR})


async def stop_session(
    session: AsyncSession,
    runtime: SessionRuntime,
    session_id: str,
    *,
    token_registry: TokenRegistry | None = None,
) -> None:
    row = await session.get(ClaudeSession, session_id)
    if row is None:
        raise SessionNotFoundError(f"session not found: {session_id}")

    if row.status in _TERMINAL_STATUSES:
        return  # idempotent: already terminal

    handle = _rehydrate_handle(row)
    cwd_path = Path(row.cwd) if row.cwd else None
    await runtime.kill(handle, worktree=cwd_path)
    row.status = SessionStatus.DONE
    row.ended_at = datetime.now(UTC)
    await session.commit()
    if token_registry is not None and row.hook_token is not None:
        token_registry.revoke(row.hook_token)


def _rehydrate_handle(row: ClaudeSession) -> JailHandle:
    # start_session always populates jail_id and pid; this guard catches DB
    # rows that bypassed that path (e.g., manual seeding or future bugs).
    if row.jail_id is None or row.pid is None:  # pragma: no cover
        raise SessionNotFoundError(
            f"session {row.id} has no runtime handle (status={row.status})"
        )
    return JailHandle(id=row.jail_id, pid=row.pid, started_at=row.started_at)


async def update_status(
    session: AsyncSession,
    session_id: str,
    new_status: SessionStatus,
) -> tuple[SessionStatus, SessionStatus]:
    """Idempotent status mutation. Returns (previous, new).

    `session.refresh(row)` is intentional (per spec §7): when multiple hook
    handlers share the same `AsyncSession`, the in-identity-map row may be
    stale from a sibling write. SQLite serialises writes; refresh bridges
    reads cleanly. Postgres migration will revisit.
    """
    row = await session.get(ClaudeSession, session_id)
    if row is None:
        raise SessionNotFoundError(f"session not found: {session_id}")
    await session.refresh(row)
    previous = SessionStatus(row.status)
    row.last_hook_at = datetime.now(UTC)
    if previous in _TERMINAL_STATUSES or previous == new_status:
        await session.commit()
        return previous, previous
    row.status = new_status
    await session.commit()
    return previous, new_status


async def bump_last_hook_at(session: AsyncSession, session_id: str) -> None:
    """Update only ``last_hook_at`` without touching status.

    Used by audit-only hooks (``PreToolUse``) where we don't want a status
    transition but still want to record that the session is alive.
    """
    row = await session.get(ClaudeSession, session_id)
    if row is None:
        raise SessionNotFoundError(f"session not found: {session_id}")
    await session.refresh(row)
    row.last_hook_at = datetime.now(UTC)
    await session.commit()
