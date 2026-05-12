"""F8.c: get_project helper."""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.core.projects import (
    ProjectNotFoundError,
    get_project,
)
from orchestrator.store.models import Project


async def test_get_project_returns_existing(db_session: AsyncSession) -> None:
    db_session.add(Project(id="p1", name="p", path="/tmp/p"))
    await db_session.commit()
    p = await get_project(db_session, "p1")
    assert p.name == "p"


async def test_get_project_missing_raises(db_session: AsyncSession) -> None:
    with pytest.raises(ProjectNotFoundError):
        await get_project(db_session, "ghost")
