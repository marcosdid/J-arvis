from collections.abc import Sequence
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.hooks.tokens import TokenRegistry, generate_token
from orchestrator.sandbox.runtime import JailHandle, SessionRuntime
from orchestrator.store.models import ClaudeSession, Worktree


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


async def start_session(
    session: AsyncSession,
    runtime: SessionRuntime,
    worktree_id: str,
    *,
    token_registry: TokenRegistry | None = None,
    base_url: str | None = None,
) -> ClaudeSession:
    worktree = await session.get(Worktree, worktree_id)
    if worktree is None:
        raise WorktreeNotFoundError(f"worktree not found: {worktree_id}")

    token = generate_token() if token_registry is not None else None
    handle = await runtime.spawn(Path(worktree.path), token=token, base_url=base_url)
    row = ClaudeSession(
        worktree_id=worktree_id,
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
    worktree_row = await session.get(Worktree, row.worktree_id)
    worktree_path = Path(worktree_row.path) if worktree_row else None
    await runtime.kill(handle, worktree=worktree_path)
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
