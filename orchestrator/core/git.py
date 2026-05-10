import asyncio
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

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


class GitWorktreeError(Exception):
    """Raised on any failed git worktree operation."""


def _format_stderr(exc: subprocess.CalledProcessError) -> str:
    err = exc.stderr
    if err is None:
        return str(exc)
    if isinstance(err, bytes):
        return err.decode(errors="replace")
    return err


class GitWorktreeOps(Protocol):
    async def list(self, repo: Path) -> list["WorktreeInfo"]: ...
    async def add(self, repo: Path, target: Path, branch: str) -> None: ...
    async def remove(
        self, repo: Path, target: Path, *, force: bool = False
    ) -> None: ...


class SubprocessGitWorktreeOps:
    """Production impl: invokes git via subprocess on a thread pool."""

    async def list(self, repo: Path) -> list[WorktreeInfo]:
        try:
            output = await asyncio.to_thread(run_git_worktree_list, repo)
        except subprocess.CalledProcessError as exc:
            stderr = _format_stderr(exc)
            raise GitWorktreeError(
                f"git worktree list failed in {repo}: {stderr}"
            ) from exc
        return parse_worktree_list(output)

    async def add(self, repo: Path, target: Path, branch: str) -> None:
        def _run() -> None:
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo),
                    "worktree",
                    "add",
                    str(target),
                    "-b",
                    branch,
                ],
                check=True,
                capture_output=True,
                timeout=30.0,
            )

        try:
            await asyncio.to_thread(_run)
        except subprocess.CalledProcessError as exc:
            stderr = _format_stderr(exc)
            raise GitWorktreeError(
                f"git worktree add failed in {repo} -> {target} ({branch}): {stderr}"
            ) from exc

    async def remove(
        self, repo: Path, target: Path, *, force: bool = False
    ) -> None:
        def _run() -> None:
            cmd = ["git", "-C", str(repo), "worktree", "remove", str(target)]
            if force:
                cmd.append("--force")
            subprocess.run(cmd, check=True, capture_output=True, timeout=30.0)

        try:
            await asyncio.to_thread(_run)
        except subprocess.CalledProcessError as exc:
            stderr = _format_stderr(exc)
            raise GitWorktreeError(
                f"git worktree remove failed in {repo} -> {target}: {stderr}"
            ) from exc
