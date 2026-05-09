# Domain layer for projects.
#
# F1 trade-off: this module imports SQLAlchemy types directly. ARCHITECTURE.md §10
# advocates Protocol-based seams between core/ and store/, but for F1 we have a
# single storage implementation and no isolated unit tests on the domain. A
# ProjectRepository Protocol can be introduced when we get a second implementation
# (e.g., in-memory fake for fast unit tests) or another storage backend.
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.store.models import Project, Task


class PathDoesNotExistError(Exception):
    pass


class NotAGitRepoError(Exception):
    pass


class ProjectNotFoundError(Exception):
    pass


class DuplicateProjectError(Exception):
    pass


class ProjectHasTasksError(Exception):
    pass


def _validate_path(path: str) -> Path:
    candidate = Path(path)
    if not candidate.is_dir():
        raise PathDoesNotExistError(f"path does not exist or is not a directory: {path}")
    if not (candidate / ".git").exists():
        raise NotAGitRepoError(f"not a git repository: {path}")
    return candidate


async def create_project(session: AsyncSession, name: str, path: str) -> Project:
    _validate_path(path)
    project = Project(name=name, path=path)
    session.add(project)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise DuplicateProjectError(f"a project with that path already exists: {path}") from exc
    await session.refresh(project)
    return project


async def list_projects(session: AsyncSession) -> Sequence[Project]:
    result = await session.execute(select(Project))
    return result.scalars().all()


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
