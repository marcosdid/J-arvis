import pytest

from orchestrator.core.git import WorktreeInfo, parse_worktree_list


@pytest.mark.unit
def test_parses_single_worktree_with_branch() -> None:
    output = (
        "worktree /home/user/repo\n"
        "HEAD abcdef0123456789\n"
        "branch refs/heads/main\n"
        "\n"
    )
    result = parse_worktree_list(output)
    assert result == [WorktreeInfo(path="/home/user/repo", branch="main")]


@pytest.mark.unit
def test_parses_multiple_worktrees() -> None:
    output = (
        "worktree /home/user/repo\n"
        "HEAD aaa\n"
        "branch refs/heads/main\n"
        "\n"
        "worktree /home/user/feature\n"
        "HEAD bbb\n"
        "branch refs/heads/feature/x\n"
        "\n"
    )
    result = parse_worktree_list(output)
    assert result == [
        WorktreeInfo(path="/home/user/repo", branch="main"),
        WorktreeInfo(path="/home/user/feature", branch="feature/x"),
    ]


@pytest.mark.unit
def test_parses_detached_worktree() -> None:
    output = (
        "worktree /home/user/detached\n"
        "HEAD ccc\n"
        "detached\n"
        "\n"
    )
    result = parse_worktree_list(output)
    assert result == [WorktreeInfo(path="/home/user/detached", branch=None)]


@pytest.mark.unit
def test_parses_empty_output() -> None:
    assert parse_worktree_list("") == []


@pytest.mark.unit
def test_skips_block_without_worktree_line() -> None:
    output = (
        "noise: not a worktree block\n"
        "more noise\n"
        "\n"
        "worktree /home/user/x\n"
        "HEAD a\n"
        "branch refs/heads/main\n"
    )
    assert parse_worktree_list(output) == [WorktreeInfo(path="/home/user/x", branch="main")]


@pytest.mark.unit
def test_skips_bare_repository_marker() -> None:
    output = (
        "worktree /home/user/bare\n"
        "bare\n"
        "\n"
        "worktree /home/user/work\n"
        "HEAD ddd\n"
        "branch refs/heads/main\n"
        "\n"
    )
    result = parse_worktree_list(output)
    assert result == [
        WorktreeInfo(path="/home/user/bare", branch=None),
        WorktreeInfo(path="/home/user/work", branch="main"),
    ]
