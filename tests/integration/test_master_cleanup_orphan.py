"""F8.e: cleanup_orphan_master_at_startup mata PID antigo."""
import signal
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from orchestrator.core.master_session import cleanup_orphan_master_at_startup
from orchestrator.store.database import Database
from orchestrator.store.models import MasterSession


@pytest.mark.integration
async def test_cleanup_kills_orphan_pid(db: Database) -> None:
    async with db.session() as s:
        s.add(MasterSession(
            id="singleton", claude_session_id="x", pid=99999,
            started_at=datetime.now(UTC), last_active=datetime.now(UTC),
        ))
        await s.commit()

    with patch("orchestrator.core.master_session.os.killpg") as mock_kill, \
         patch("orchestrator.core.master_session.os.getpgid", return_value=99999):
        async with db.session() as s:
            await cleanup_orphan_master_at_startup(s)
        mock_kill.assert_called_with(99999, signal.SIGKILL)

    async with db.session() as s:
        master = await s.get(MasterSession, "singleton")
        assert master is not None
        assert master.pid is None


@pytest.mark.integration
async def test_cleanup_handles_already_dead_pid(db: Database) -> None:
    async with db.session() as s:
        s.add(MasterSession(
            id="singleton", claude_session_id="x", pid=99999,
            started_at=datetime.now(UTC), last_active=datetime.now(UTC),
        ))
        await s.commit()

    with patch(
        "orchestrator.core.master_session.os.killpg",
        side_effect=ProcessLookupError(),
    ), patch("orchestrator.core.master_session.os.getpgid", return_value=99999):
        async with db.session() as s:
            await cleanup_orphan_master_at_startup(s)

    async with db.session() as s:
        master = await s.get(MasterSession, "singleton")
        assert master is not None
        assert master.pid is None


@pytest.mark.integration
async def test_cleanup_no_master_row_noop(db: Database) -> None:
    """Sem row prévia, cleanup é no-op."""
    async with db.session() as s:
        await cleanup_orphan_master_at_startup(s)  # não raise


@pytest.mark.integration
async def test_cleanup_master_with_null_pid_noop(db: Database) -> None:
    async with db.session() as s:
        s.add(MasterSession(
            id="singleton", claude_session_id="x", pid=None,
            started_at=datetime.now(UTC), last_active=datetime.now(UTC),
        ))
        await s.commit()
    async with db.session() as s:
        await cleanup_orphan_master_at_startup(s)
