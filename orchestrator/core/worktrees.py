import asyncio
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.core.git import parse_worktree_list, run_git_worktree_list
from orchestrator.core.projects import ProjectNotFoundError
from orchestrator.store.models import Project, Worktree


async def list_project_worktrees(
    session: AsyncSession, project_id: str
) -> Sequence[Worktree]:
    """Sync git worktrees with DB and return all worktrees of the project.

    Insert-or-update by path; never deletes orphans. Single-user invariant:
    concurrent calls to this function on the same project are not supported
    (one browser tab assumed); a race could surface as IntegrityError on the
    unique-path constraint.
    """
    project = await session.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError(f"project not found: {project_id}")

    output = await asyncio.to_thread(run_git_worktree_list, Path(project.path))
    infos = parse_worktree_list(output)

    by_path: dict[str, Worktree] = {
        w.path: w
        for w in (
            (
                await session.execute(
                    select(Worktree).where(Worktree.project_id == project_id)
                )
            )
            .scalars()
            .all()
        )
    }

    for info in infos:
        existing = by_path.get(info.path)
        if existing is None:
            session.add(
                Worktree(project_id=project_id, path=info.path, branch=info.branch)
            )
        elif existing.branch != info.branch:
            existing.branch = info.branch

    await session.commit()

    result = await session.execute(
        select(Worktree).where(Worktree.project_id == project_id)
    )
    return result.scalars().all()
