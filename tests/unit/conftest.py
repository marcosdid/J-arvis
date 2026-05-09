from pathlib import Path

import pytest

from orchestrator.store.database import Database


@pytest.fixture
async def db_session(tmp_path: Path):
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'unit.db'}")
    await db.bootstrap()
    async with db.session() as s:
        yield s
