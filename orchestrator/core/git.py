import subprocess
from dataclasses import dataclass
from pathlib import Path

_WORKTREE_PREFIX = "worktree "
_BRANCH_PREFIX = "branch refs/heads/"


def run_git_worktree_list(repo: Path, *, timeout: float = 10.0) -> str:
    """Invoke `git worktree list --porcelain` in the given repo and return stdout.

    Synchronous: callers in async code must wrap in ``asyncio.to_thread`` to
    avoid blocking the event loop.
    """
    completed = subprocess.run(
        ["git", "-C", str(repo), "worktree", "list", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return completed.stdout


@dataclass(frozen=True)
class WorktreeInfo:
    path: str
    branch: str | None


def parse_worktree_list(output: str) -> list[WorktreeInfo]:
    """Parse `git worktree list --porcelain` output.

    Each block declares a worktree with at least a `worktree <path>` line.
    Branches appear as `branch refs/heads/<name>`. Detached and bare
    worktrees lack a branch line and are returned with ``branch=None``.
    """
    text = output.strip()
    if not text:
        return []

    result: list[WorktreeInfo] = []
    for block in text.split("\n\n"):
        path: str | None = None
        branch: str | None = None
        for line in block.splitlines():
            if line.startswith(_WORKTREE_PREFIX):
                path = line[len(_WORKTREE_PREFIX) :]
            elif line.startswith(_BRANCH_PREFIX):
                branch = line[len(_BRANCH_PREFIX) :]
        if path is not None:
            result.append(WorktreeInfo(path=path, branch=branch))
    return result
