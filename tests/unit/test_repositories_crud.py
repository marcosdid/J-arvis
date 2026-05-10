from pathlib import Path

import pytest

from orchestrator.core.repositories import list_project_repositories
from orchestrator.store.database import Database
from orchestrator.store.models import Project, Repository


@pytest.mark.asyncio
async def test_list_project_repositories_orders_by_sub_path(tmp_path: Path) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/r.db")
    await db.bootstrap()
    async with db.session() as s:
        p = Project(name="x", path=str(tmp_path))
        s.add(p)
        await s.flush()
        s.add(Repository(project_id=p.id, name="frontend", sub_path="frontend"))
        s.add(Repository(project_id=p.id, name="backend", sub_path="backend"))
        await s.commit()

        repos = await list_project_repositories(s, p.id)
        assert [r.sub_path for r in repos] == ["backend", "frontend"]
