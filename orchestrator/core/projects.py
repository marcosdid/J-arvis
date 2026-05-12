# Domain layer for projects.
#
# F5: path validation moved to ``core.repositories.detect_repos`` (a project
# may now map to N git repos under a single base_path). The old
# ``PathDoesNotExistError``/``NotAGitRepoError`` aren't raised anymore — the
# new code path returns ``NoGitReposError`` from detect_repos via the API.
#
# ``create_project`` is retained as a unit-test helper (skip path validation)
# and is NOT used by the API. Production projects are created via
# ``api.projects.post_project`` which calls ``detect_repos`` directly.
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.store.models import Project, Task


class ProjectNotFoundError(Exception):
    pass


class ProjectHasTasksError(Exception):
    pass


async def create_project(session: AsyncSession, name: str, path: str) -> Project:
    """Create a Project row directly. Test-only helper: bypasses the path
    validation done by the API. Production code uses POST /api/projects."""
    project = Project(name=name, path=path)
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def list_projects(session: AsyncSession) -> Sequence[Project]:
    result = await session.execute(select(Project))
    return result.scalars().all()


async def get_project(session: AsyncSession, project_id: str) -> Project:
    proj = await session.get(Project, project_id)
    if proj is None:
        raise ProjectNotFoundError(f"project not found: {project_id}")
    return proj


async def delete_project(session: AsyncSession, project_id: str) -> None:
    project = await session.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError(f"project not found: {project_id}")
    count = (await session.execute(
        select(func.count()).select_from(Task).where(Task.project_id == project_id)
    )).scalar_one()
    if count > 0:
        raise ProjectHasTasksError(
            f"project has {count} task(s); discard them before deleting"
        )
    await session.delete(project)
    await session.commit()
