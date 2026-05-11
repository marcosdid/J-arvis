"""F7.c: create_task com template resolve prefix + permission_profile."""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.core.catalog import Catalog
from orchestrator.core.slug import InvalidBranchSlugError
from orchestrator.core.tasks import (
    InvalidTemplateError,
    ProjectNotFoundForTaskError,
    create_task,
)
from orchestrator.store.models import Project


@pytest.fixture
async def project(db_session: AsyncSession) -> Project:
    proj = Project(id="p1", name="p", path="/tmp/p")
    db_session.add(proj)
    await db_session.commit()
    return proj


async def test_create_task_without_template_stays_null(
    db_session: AsyncSession, catalog: Catalog, project: Project,
) -> None:
    task = await create_task(
        db_session,
        project_id="p1", title="hello world",
        description="", branch=None,
        template=None, catalog=catalog,
    )
    assert task.template is None
    assert task.permission_profile is None
    assert task.branch is None  # branch deferred to first session start (F1 behavior)


async def test_create_task_with_template_resolves_prefix_and_profile(
    db_session: AsyncSession, catalog: Catalog, project: Project,
) -> None:
    task = await create_task(
        db_session,
        project_id="p1", title="Fix logout race",
        description="", branch=None,
        template="bugfix", catalog=catalog,
    )
    assert task.template == "bugfix"
    assert task.permission_profile == "yolo"
    assert task.branch == "fix/fix-logout-race"


async def test_create_task_with_template_and_branch_override(
    db_session: AsyncSession, catalog: Catalog, project: Project,
) -> None:
    """Branch explícito sempre literal, nunca aplica prefix."""
    task = await create_task(
        db_session,
        project_id="p1", title="anything",
        description="", branch="my-custom-branch",
        template="frontend", catalog=catalog,
    )
    assert task.template == "frontend"
    assert task.permission_profile == "yolo"
    assert task.branch == "my-custom-branch"


async def test_create_task_with_template_and_branch_starting_with_prefix(
    db_session: AsyncSession, catalog: Catalog, project: Project,
) -> None:
    """Even if branch happens to start with prefix, it's literal."""
    task = await create_task(
        db_session,
        project_id="p1", title="anything",
        description="", branch="feat-ui/already-prefixed",
        template="frontend", catalog=catalog,
    )
    assert task.template == "frontend"
    assert task.permission_profile == "yolo"
    assert task.branch == "feat-ui/already-prefixed"


async def test_create_task_invalid_template_raises(
    db_session: AsyncSession, catalog: Catalog, project: Project,
) -> None:
    with pytest.raises(InvalidTemplateError) as exc:
        await create_task(
            db_session,
            project_id="p1", title="t",
            description="", branch=None,
            template="ghost", catalog=catalog,
        )
    assert "ghost" in str(exc.value)
    assert set(exc.value.valid_templates) == {"frontend", "backend", "refactor", "bugfix"}


async def test_create_task_degenerate_title_with_template_raises(
    db_session: AsyncSession, catalog: Catalog, project: Project,
) -> None:
    """Título que slugify falha → InvalidBranchSlugError."""
    with pytest.raises(InvalidBranchSlugError):
        await create_task(
            db_session,
            project_id="p1", title="!!!",
            description="", branch=None,
            template="frontend", catalog=catalog,
        )


async def test_create_task_template_without_project_raises_first(
    db_session: AsyncSession, catalog: Catalog,
) -> None:
    """Order check: project validation runs DEPOIS de template; mas para ghost project
    + título válido, template sucede e project lookup falha."""
    with pytest.raises(ProjectNotFoundForTaskError):
        await create_task(
            db_session,
            project_id="ghost-p", title="t",
            description="", branch=None,
            template="frontend", catalog=catalog,
        )
