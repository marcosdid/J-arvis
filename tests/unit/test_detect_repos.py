from pathlib import Path

import pytest

from orchestrator.core.repositories import (
    NoGitReposError,
    RepoSpec,
    detect_repos,
)


def _git_init(d: Path) -> None:
    import subprocess
    subprocess.run(["git", "-C", str(d), "init", "-b", "main"], check=True, capture_output=True)


def test_monorepo_returns_single_dot(tmp_path: Path) -> None:
    _git_init(tmp_path)
    result = detect_repos(tmp_path)
    assert result == [RepoSpec(name=tmp_path.name, sub_path=".")]


def test_multi_repo_lists_subdirs_alphabetically(tmp_path: Path) -> None:
    base = tmp_path / "multi"
    base.mkdir()
    for sub in ["frontend", "backend", "docs"]:
        d = base / sub
        d.mkdir()
        _git_init(d)
    result = detect_repos(base)
    assert result == [
        RepoSpec(name="backend", sub_path="backend"),
        RepoSpec(name="docs", sub_path="docs"),
        RepoSpec(name="frontend", sub_path="frontend"),
    ]


def test_no_repos_raises(tmp_path: Path) -> None:
    base = tmp_path / "empty"
    base.mkdir()
    with pytest.raises(NoGitReposError):
        detect_repos(base)


def test_path_does_not_exist_raises(tmp_path: Path) -> None:
    with pytest.raises(NoGitReposError):
        detect_repos(tmp_path / "nope")


def test_submodule_dot_git_as_file_is_ignored(tmp_path: Path) -> None:
    base = tmp_path / "with_submod"
    base.mkdir()
    sub = base / "submod"
    sub.mkdir()
    # .git as file (submodule pattern)
    (sub / ".git").write_text("gitdir: ../.git/modules/submod", encoding="utf-8")
    with pytest.raises(NoGitReposError):
        detect_repos(base)


def test_dot_git_at_root_takes_precedence_over_subdirs(tmp_path: Path) -> None:
    """If both base/.git/ AND base/sub/.git/ exist, base wins (monorepo)."""
    _git_init(tmp_path)
    sub = tmp_path / "embedded"
    sub.mkdir()
    _git_init(sub)
    result = detect_repos(tmp_path)
    assert result == [RepoSpec(name=tmp_path.name, sub_path=".")]
