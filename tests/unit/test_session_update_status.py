from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from orchestrator.core.sessions import (
    SessionNotFoundError,
    SessionStatus,
    bump_last_hook_at,
    update_status,
)
from orchestrator.store.database import Database
from orchestrator.store.models import ClaudeSession, Project, Worktree


@pytest.fixture
async def db(tmp_path: Path) -> AsyncIterator[Database]:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    await database.bootstrap()
    try:
        yield database
    finally:
        await database.close()


async def _seed_session(database: Database, status: SessionStatus) -> str:
    async with database.session() as s:
        proj = Project(name="p", path="/tmp/p")
        s.add(proj)
        await s.commit()
        await s.refresh(proj)
        wt = Worktree(project_id=proj.id, path="/tmp/p/wt", branch="main")
        s.add(wt)
        await s.commit()
        await s.refresh(wt)
        row = ClaudeSession(
            worktree_id=wt.id,
            status=status,
            pid=1,
            jail_id="j-1",
            started_at=datetime.now(UTC),
        )
        s.add(row)
        await s.commit()
        await s.refresh(row)
        return row.id


@pytest.mark.asyncio
async def test_update_status_changes_row_and_returns_pair(db: Database) -> None:
    sid = await _seed_session(db, SessionStatus.EXECUTING)
    async with db.session() as s:
        prev, new = await update_status(s, sid, SessionStatus.AWAITING_RESPONSE)
    assert (prev, new) == (SessionStatus.EXECUTING, SessionStatus.AWAITING_RESPONSE)
    async with db.session() as s:
        fresh = await s.get(ClaudeSession, sid)
        assert fresh is not None
        assert fresh.status == SessionStatus.AWAITING_RESPONSE
        assert fresh.last_hook_at is not None


@pytest.mark.asyncio
async def test_update_status_is_idempotent_no_change(db: Database) -> None:
    sid = await _seed_session(db, SessionStatus.IDLE)
    async with db.session() as s:
        prev, new = await update_status(s, sid, SessionStatus.IDLE)
    assert prev == new == SessionStatus.IDLE


@pytest.mark.asyncio
async def test_update_status_terminal_blocks_change(db: Database) -> None:
    sid = await _seed_session(db, SessionStatus.DONE)
    async with db.session() as s:
        prev, new = await update_status(s, sid, SessionStatus.AWAITING_RESPONSE)
    assert prev == new == SessionStatus.DONE


@pytest.mark.asyncio
async def test_update_status_unknown_session_raises(db: Database) -> None:
    async with db.session() as s:
        with pytest.raises(SessionNotFoundError):
            await update_status(s, "no-such-id", SessionStatus.IDLE)


@pytest.mark.asyncio
async def test_update_status_bumps_last_hook_at_even_when_idempotent(db: Database) -> None:
    sid = await _seed_session(db, SessionStatus.IDLE)
    baseline = datetime.now(UTC).replace(tzinfo=None)
    async with db.session() as s:
        await update_status(s, sid, SessionStatus.IDLE)
    async with db.session() as s:
        fresh = await s.get(ClaudeSession, sid)
        assert fresh is not None
        assert fresh.last_hook_at is not None
        assert fresh.last_hook_at >= baseline


@pytest.mark.asyncio
async def test_bump_last_hook_at_updates_only_timestamp(db: Database) -> None:
    sid = await _seed_session(db, SessionStatus.EXECUTING)
    async with db.session() as s:
        await bump_last_hook_at(s, sid)
    async with db.session() as s:
        row = await s.get(ClaudeSession, sid)
        assert row is not None
        assert row.status == SessionStatus.EXECUTING  # unchanged
        assert row.last_hook_at is not None


@pytest.mark.asyncio
async def test_bump_last_hook_at_unknown_raises(db: Database) -> None:
    async with db.session() as s:
        with pytest.raises(SessionNotFoundError):
            await bump_last_hook_at(s, "no-such-id")
