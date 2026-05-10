"""Repository discovery and queries.

A Project may map to N git repositories:
- Monorepo: 1 Repository row with sub_path="."
- Multi-repo (umbrella): N Repository rows, each pointing to a subdir

`detect_repos` is the auto-detection entry: it scans `base_path` and
returns the list of repos found. Used at add-project time and in
migration 0004 backfill.

NB on naming: for monorepo, RepoSpec.name = base_path.name (the last
path component). For migration backfill, callers may prefer to use
project.name (the user-configured name) instead — the Repository row
in DB stores whatever the caller chose.
"""
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.store.models import Repository


class NoGitReposError(Exception):
    """Raised when detect_repos finds no .git directory at root or 1 level deep."""


@dataclass(frozen=True)
class RepoSpec:
    name: str
    sub_path: str


def detect_repos(base_path: Path) -> list[RepoSpec]:
    """Detect git repositories within ``base_path``.

    Algorithm:
    1. If ``base_path/.git/`` exists (directory, not file): monorepo.
       Return ``[RepoSpec(name=base_path.name, sub_path=".")]``.
    2. Else, scan immediate children. Each child with ``child/.git/``
       (directory) becomes a sub-repo. Returned alphabetically by name.
    3. Empty: raise ``NoGitReposError``.

    Submodules (where ``.git`` is a *file* pointing elsewhere) are
    skipped because they are not independent repositories.
    """
    if not base_path.is_dir():
        raise NoGitReposError(f"path is not a directory: {base_path}")
    if (base_path / ".git").is_dir():
        return [RepoSpec(name=base_path.name, sub_path=".")]
    sub_repos = [
        RepoSpec(name=child.name, sub_path=child.name)
        for child in sorted(base_path.iterdir())
        if child.is_dir() and (child / ".git").is_dir()
    ]
    if not sub_repos:
        raise NoGitReposError(
            f"no .git dir found in {base_path} or 1 level below"
        )
    return sub_repos


async def list_project_repositories(
    session: AsyncSession, project_id: str
) -> Sequence[Repository]:
    """Returns repositories of a project ordered by sub_path ASC."""
    result = await session.execute(
        select(Repository)
        .where(Repository.project_id == project_id)
        .order_by(Repository.sub_path)
    )
    return result.scalars().all()
