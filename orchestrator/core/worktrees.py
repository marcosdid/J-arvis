"""Worktree queries, sync with git, cleanup, and removal.

A Project may map to N git repositories (per F5.b). Worktrees are
attached to a Repository (FK CASCADE) and optionally to a Task
(FK SET NULL; NULL = orphan, created externally or left over from
a failed cleanup).

Sync (`list_project_worktrees`) iterates each Repository, runs
`git worktree list`, and inserts unknowns as orphans.

Cleanup (`cleanup_task_worktrees`) is tolerant: per-worktree
failures orphan the row instead of blocking task state transitions.
"""
import logging
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.core.git import GitWorktreeError, GitWorktreeOps, WorktreeInfo
from orchestrator.core.projects import ProjectNotFoundError
from orchestrator.core.repositories import list_project_repositories
from orchestrator.events.broadcaster import WsBroadcaster
from orchestrator.events.envelope import WsEvent
from orchestrator.store.models import Project, Repository, Worktree

_log = logging.getLogger(__name__)


class WorktreeNotFoundError(Exception):
    """Raised when a worktree id doesn't exist in the DB."""


class WorktreeNotOrphanError(Exception):
    """Raised when delete_worktree is called on a worktree that still has a task_id."""


async def list_project_worktrees(
    session: AsyncSession,
    git: GitWorktreeOps,
    project_id: str,
) -> Sequence[Worktree]:
    """Sync git worktrees with DB across all repositories of a project.

    For each Repository, runs `git worktree list` and inserts new paths
    as orphans (task_id=NULL). Worktrees that were already present (from
    daemon-created start_session flow) keep their task_id.

    Returns all Worktrees of the project (orphan + task-owned).
    Tolerant: a sub-repo whose `git worktree list` fails is skipped (logged).
    """
    project = await session.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError(f"project not found: {project_id}")

    repos = list(await list_project_repositories(session, project_id))

    discovered: dict[str, tuple[Repository, WorktreeInfo]] = {}
    for repo in repos:
        repo_path = Path(project.path) / repo.sub_path
        try:
            infos = await git.list(repo_path)
        except GitWorktreeError as exc:
            _log.warning(
                "git worktree list failed in %s/%s: %s; skipping repo in sync",
                project.path, repo.sub_path, exc,
            )
            continue
        for info in infos:
            discovered[info.path] = (repo, info)

    existing_rows = (await session.execute(
        select(Worktree)
        .join(Repository, Repository.id == Worktree.repository_id)
        .where(Repository.project_id == project_id)
    )).scalars().all()
    by_path = {w.path: w for w in existing_rows}

    for path, (repo, info) in discovered.items():
        existing = by_path.get(path)
        if existing is None:
            session.add(Worktree(
                repository_id=repo.id,
                task_id=None,
                path=path,
                branch=info.branch,
            ))
        elif existing.branch != info.branch:
            existing.branch = info.branch

    await session.commit()

    return (await session.execute(
        select(Worktree)
        .join(Repository, Repository.id == Worktree.repository_id)
        .where(Repository.project_id == project_id)
        .order_by(Worktree.path)
    )).scalars().all()


async def list_worktrees_for_task(
    session: AsyncSession, task_id: str
) -> list[Worktree]:
    """Worktrees of a task ordered by path."""
    result = await session.execute(
        select(Worktree).where(Worktree.task_id == task_id).order_by(Worktree.path)
    )
    return list(result.scalars().all())


async def list_orphan_worktrees(
    session: AsyncSession, project_id: str
) -> Sequence[Worktree]:
    """Worktrees of a project where task_id IS NULL (created externally
    or left over from a failed cleanup)."""
    result = await session.execute(
        select(Worktree)
        .join(Repository, Repository.id == Worktree.repository_id)
        .where(Repository.project_id == project_id, Worktree.task_id.is_(None))
        .order_by(Worktree.path)
    )
    return result.scalars().all()


async def cleanup_task_worktrees(
    session: AsyncSession,
    git: GitWorktreeOps,
    broadcaster: WsBroadcaster | None,
    task_id: str,
) -> None:
    """Remove worktrees physically + DB rows when a task transitions to
    terminal state.

    Tolerant: per-worktree `git remove` failures orphan the row
    (task_id=NULL) instead of bubbling up. Broadcasts deferred until after
    the commit (same atomicity pattern as start_session).
    """
    wts = await list_worktrees_for_task(session, task_id)
    if not wts:
        return

    cwds: set[Path] = set()
    pending_broadcasts: list[WsEvent] = []

    for wt in wts:
        repo = await session.get(Repository, wt.repository_id)
        project = await session.get(Project, repo.project_id)
        repo_full = Path(project.path) / repo.sub_path
        wt_path = Path(wt.path)
        cwds.add(wt_path.parent)
        try:
            await git.remove(repo_full, wt_path, force=True)
            wt_id = wt.id
            project_id = repo.project_id
            await session.delete(wt)
            pending_broadcasts.append(WsEvent.worktree_removed(
                worktree_id=wt_id, project_id=project_id, task_id=task_id,
            ))
        except GitWorktreeError as exc:
            _log.warning(
                "cleanup of %s failed: %s; orphaning row", wt_path, exc,
            )
            wt.task_id = None
            pending_broadcasts.append(WsEvent.worktree_orphaned(
                worktree_id=wt.id, project_id=repo.project_id, path=wt.path,
            ))

    await session.commit()

    for cwd in cwds:
        if cwd.exists() and not any(cwd.iterdir()):
            try:
                cwd.rmdir()
            except OSError:
                pass

    if broadcaster is not None:
        for event in pending_broadcasts:
            await broadcaster.publish(event)


async def delete_worktree(
    session: AsyncSession,
    git: GitWorktreeOps,
    worktree_id: str,
    *,
    broadcaster: WsBroadcaster | None = None,
) -> None:
    """Remove a single ORPHAN worktree (used by DELETE /api/worktrees/{id}).

    Refuses with WorktreeNotOrphanError if the worktree still belongs to
    a task — those should go through cleanup_task_worktrees instead.

    Broadcasts `worktree.removed` after commit (deferred, mesma atomicidade
    de cleanup_task_worktrees). `task_id` field of the broadcast is None
    (orphans by definition have no task).
    """
    wt = await session.get(Worktree, worktree_id)
    if wt is None:
        raise WorktreeNotFoundError(f"worktree not found: {worktree_id}")
    if wt.task_id is not None:
        raise WorktreeNotOrphanError(
            f"worktree {worktree_id} belongs to active task {wt.task_id}; "
            "use task cleanup flow instead"
        )
    repo = await session.get(Repository, wt.repository_id)
    project = await session.get(Project, repo.project_id)
    repo_full = Path(project.path) / repo.sub_path

    wt_id = wt.id
    project_id = repo.project_id

    await git.remove(repo_full, Path(wt.path), force=True)
    await session.delete(wt)
    await session.commit()

    if broadcaster is not None:
        await broadcaster.publish(WsEvent.worktree_removed(
            worktree_id=wt_id, project_id=project_id, task_id=None,
        ))
