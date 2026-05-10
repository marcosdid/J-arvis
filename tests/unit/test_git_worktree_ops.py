import os
import subprocess
from pathlib import Path

import pytest

from orchestrator.core.git import (
    GitWorktreeError,
    SubprocessGitWorktreeOps,
    _format_stderr,
)


def _make_repo(tmp_path: Path, name: str = "repo") -> Path:
    repo = tmp_path / name
    repo.mkdir()
    subprocess.run(
        ["git", "-C", str(repo), "init", "-b", "main"],
        check=True,
        capture_output=True,
    )
    (repo / "f").write_text("x")
    subprocess.run(
        ["git", "-C", str(repo), "add", "."],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-m",
            "init",
        ],
        check=True,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@e",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@e",
            "PATH": os.environ["PATH"],
        },
    )
    return repo


async def test_add_creates_worktree_with_new_branch(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    ops = SubprocessGitWorktreeOps()
    target = tmp_path / "wt"
    await ops.add(repo, target, "feature/x")
    assert target.is_dir()
    assert (target / ".git").exists()


async def test_add_failing_branch_existing_raises(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    ops = SubprocessGitWorktreeOps()
    target = tmp_path / "wt"
    await ops.add(repo, target, "feature/x")
    target2 = tmp_path / "wt2"
    with pytest.raises(GitWorktreeError):
        await ops.add(repo, target2, "feature/x")


async def test_remove_force_removes_worktree(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    ops = SubprocessGitWorktreeOps()
    target = tmp_path / "wt"
    await ops.add(repo, target, "feature/x")
    await ops.remove(repo, target, force=True)
    assert not target.exists()


async def test_list_returns_worktree_infos(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    ops = SubprocessGitWorktreeOps()
    target = tmp_path / "wt"
    await ops.add(repo, target, "feature/x")
    infos = await ops.list(repo)
    paths = {i.path for i in infos}
    assert str(target) in paths


async def test_list_on_non_repo_raises(tmp_path: Path) -> None:
    not_a_repo = tmp_path / "nope"
    not_a_repo.mkdir()
    ops = SubprocessGitWorktreeOps()
    with pytest.raises(GitWorktreeError):
        await ops.list(not_a_repo)


def test_format_stderr_handles_none_bytes_and_str() -> None:
    err_none = subprocess.CalledProcessError(returncode=1, cmd=["git"], stderr=None)
    err_bytes = subprocess.CalledProcessError(
        returncode=1, cmd=["git"], stderr=b"boom"
    )
    err_str = subprocess.CalledProcessError(
        returncode=1, cmd=["git"], stderr="boom"
    )
    assert "git" in _format_stderr(err_none)
    assert _format_stderr(err_bytes) == "boom"
    assert _format_stderr(err_str) == "boom"


async def test_remove_without_force_on_dirty_worktree_raises(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    ops = SubprocessGitWorktreeOps()
    target = tmp_path / "wt"
    await ops.add(repo, target, "feature/x")
    (target / "dirty").write_text("uncommitted")
    with pytest.raises(GitWorktreeError):
        await ops.remove(repo, target, force=False)
    assert target.exists()
