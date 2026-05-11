import pytest

from orchestrator.core.catalog import Catalog
from orchestrator.core.projects import (
    ProjectHasTasksError,
    ProjectNotFoundError,
    create_project,
    delete_project,
)
from orchestrator.core.tasks import create_task


async def test_delete_project_with_tasks_raises(db_session, tmp_path, catalog: Catalog) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / ".git").mkdir()
    p = await create_project(db_session, "p", str(repo))
    await create_task(db_session, project_id=p.id, title="T", catalog=catalog)
    with pytest.raises(ProjectHasTasksError):
        await delete_project(db_session, p.id)


async def test_delete_project_without_tasks_ok(db_session, tmp_path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / ".git").mkdir()
    p = await create_project(db_session, "p", str(repo))
    await delete_project(db_session, p.id)


async def test_delete_project_not_found_raises(db_session) -> None:
    with pytest.raises(ProjectNotFoundError):
        await delete_project(db_session, "nonexistent")
