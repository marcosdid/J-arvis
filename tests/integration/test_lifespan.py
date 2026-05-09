from pathlib import Path

import pytest
from sqlalchemy import select

from orchestrator.main import create_app
from orchestrator.store.database import Database
from orchestrator.store.models import Project


@pytest.mark.integration
async def test_lifespan_no_database_does_nothing() -> None:
    app = create_app(database=None, ui_dist=None)
    async with app.router.lifespan_context(app):
        pass  # must not raise


@pytest.mark.integration
async def test_lifespan_runs_bootstrap_so_tables_exist(tmp_path: Path) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'lifespan.db'}")
    app = create_app(database=db, ui_dist=None)

    try:
        async with app.router.lifespan_context(app), db.session() as s:
            # If lifespan didn't run bootstrap, this raises OperationalError.
            result = await s.execute(select(Project))
            assert list(result.scalars()) == []
    finally:
        await db.close()
