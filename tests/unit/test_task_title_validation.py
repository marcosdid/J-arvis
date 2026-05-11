import pytest

from orchestrator.core.catalog import Catalog
from orchestrator.core.projects import create_project
from orchestrator.core.tasks import (
    InvalidTaskTitleError,
    create_task,
    update_task,
)


@pytest.mark.parametrize("bad", ["", "   ", "\t\n  "])
async def test_create_task_rejects_blank_title(
    db_session, tmp_path, catalog: Catalog, bad: str,
) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / ".git").mkdir()
    p = await create_project(db_session, "p", str(repo))
    with pytest.raises(InvalidTaskTitleError):
        await create_task(db_session, project_id=p.id, title=bad, catalog=catalog)


async def test_update_task_rejects_blank_title(db_session, tmp_path, catalog: Catalog) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / ".git").mkdir()
    p = await create_project(db_session, "p", str(repo))
    t = await create_task(db_session, project_id=p.id, title="OK", catalog=catalog)
    with pytest.raises(InvalidTaskTitleError):
        await update_task(db_session, t.id, title="   ")
