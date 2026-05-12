"""F8.e: restart simulado preserva claude_session_id."""
from datetime import UTC, datetime

import pytest

from orchestrator.store.database import Database
from orchestrator.store.models import MasterSession


@pytest.mark.integration
async def test_master_session_id_persists_across_simulated_restart(
    db: Database,
) -> None:
    """Boot 1: persist sess-id. Boot 2: read e reusa."""
    async with db.session() as s:
        s.add(MasterSession(
            id="singleton",
            claude_session_id="boot1-session-uuid",
            pid=12345,
            started_at=datetime.now(UTC),
            last_active=datetime.now(UTC),
        ))
        await s.commit()

    async with db.session() as s:
        master = await s.get(MasterSession, "singleton")
        assert master is not None
        assert master.claude_session_id == "boot1-session-uuid"
