import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.core.catalog import Catalog
from orchestrator.core.projects import create_project
from orchestrator.core.tasks import (
    InvalidTransitionError,
    ProjectNotFoundForTaskError,
    TaskNotFoundError,
    create_task,
    get_task,
    list_tasks,
    update_task,
)


async def _seed_project(s: AsyncSession, tmp_path, name: str = "proj") -> str:
    repo = tmp_path / name
    repo.mkdir()
    (repo / ".git").mkdir()
    p = await create_project(s, name, str(repo))
    return p.id


async def test_create_task_with_title_only(db_session, tmp_path, catalog: Catalog) -> None:
    pid = await _seed_project(db_session, tmp_path)
    t = await create_task(db_session, project_id=pid, title="Hello", catalog=catalog)
    assert t.id and t.title == "Hello" and t.description == ""
    assert t.state == "idea" and t.template is None


async def test_list_tasks_no_filter(db_session, tmp_path, catalog: Catalog) -> None:
    pid = await _seed_project(db_session, tmp_path)
    await create_task(db_session, project_id=pid, title="A", catalog=catalog)
    await create_task(db_session, project_id=pid, title="B", catalog=catalog)
    rows = await list_tasks(db_session)
    assert {t.title for t in rows} == {"A", "B"}


async def test_list_tasks_filter_project_ids(db_session, tmp_path, catalog: Catalog) -> None:
    pid_a = await _seed_project(db_session, tmp_path, "projA")
    pid_b = await _seed_project(db_session, tmp_path, "projB")
    await create_task(db_session, project_id=pid_a, title="A1", catalog=catalog)
    await create_task(db_session, project_id=pid_b, title="B1", catalog=catalog)
    rows = await list_tasks(db_session, project_ids=[pid_a])
    assert [t.title for t in rows] == ["A1"]


async def test_get_task_not_found_raises(db_session) -> None:
    with pytest.raises(TaskNotFoundError):
        await get_task(db_session, "nonexistent")


async def test_update_task_title(db_session, tmp_path, catalog: Catalog) -> None:
    pid = await _seed_project(db_session, tmp_path)
    t = await create_task(db_session, project_id=pid, title="A", catalog=catalog)
    new, prev_state = await update_task(db_session, t.id, title="A2")
    assert new.title == "A2" and prev_state is None


async def test_update_task_state_returns_previous(db_session, tmp_path, catalog: Catalog) -> None:
    pid = await _seed_project(db_session, tmp_path)
    t = await create_task(db_session, project_id=pid, title="X", catalog=catalog)
    new, prev_state = await update_task(db_session, t.id, state="ready")
    assert new.state == "ready" and prev_state == "idea"


async def test_update_task_same_state_is_noop(db_session, tmp_path, catalog: Catalog) -> None:
    pid = await _seed_project(db_session, tmp_path)
    t = await create_task(db_session, project_id=pid, title="X", catalog=catalog)
    new, prev_state = await update_task(db_session, t.id, state="idea")
    assert new.state == "idea" and prev_state is None


async def test_create_task_project_not_found_raises(db_session, catalog: Catalog) -> None:
    with pytest.raises(ProjectNotFoundForTaskError):
        await create_task(db_session, project_id="nonexistent", title="T", catalog=catalog)


async def test_update_task_description(db_session, tmp_path, catalog: Catalog) -> None:
    pid = await _seed_project(db_session, tmp_path)
    t = await create_task(db_session, project_id=pid, title="X", catalog=catalog)
    new, prev_state = await update_task(db_session, t.id, description="new desc")
    assert new.description == "new desc" and prev_state is None


async def test_update_task_invalid_transition_raises(
    db_session, tmp_path, catalog: Catalog,
) -> None:
    pid = await _seed_project(db_session, tmp_path)
    t = await create_task(db_session, project_id=pid, title="X", catalog=catalog)
    with pytest.raises(InvalidTransitionError):
        await update_task(db_session, t.id, state="done")
