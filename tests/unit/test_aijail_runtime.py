from datetime import UTC, datetime
from pathlib import Path

import pytest

from orchestrator.core.catalog import Catalog
from orchestrator.sandbox.aijail import (
    AiJailRuntime,
    NoTerminalFoundError,
    _discover_git_dirs,
    build_terminal_command,
    detect_terminal,
    write_aijail_config,
)
from orchestrator.sandbox.runtime import JailHandle
from orchestrator.sandbox.settings_writer import write_settings_into_jail


class FakeProcessOps:
    def __init__(self, pid: int = 12345) -> None:
        self.return_pid = pid
        self.spawn_calls: list[tuple[list[str], str]] = []
        self.kill_calls: list[int] = []
        self.kill_raises: type[BaseException] | None = None

    def spawn(self, cmd: list[str], cwd: str) -> int:
        self.spawn_calls.append((cmd, cwd))
        return self.return_pid

    def kill(self, pid: int) -> None:
        self.kill_calls.append(pid)
        if self.kill_raises is not None:
            raise self.kill_raises()


@pytest.mark.unit
def test_build_terminal_command_gnome_terminal() -> None:
    assert build_terminal_command("gnome-terminal", ["ai-jail", "run", "claude"]) == [
        "gnome-terminal",
        "--",
        "ai-jail",
        "run",
        "claude",
    ]


@pytest.mark.unit
def test_build_terminal_command_konsole() -> None:
    assert build_terminal_command("konsole", ["ai-jail"]) == ["konsole", "-e", "ai-jail"]


@pytest.mark.unit
def test_build_terminal_command_kitty_no_separator() -> None:
    assert build_terminal_command("kitty", ["ai-jail", "run"]) == ["kitty", "ai-jail", "run"]


@pytest.mark.unit
def test_build_terminal_command_alacritty() -> None:
    assert build_terminal_command("alacritty", ["ai-jail"]) == ["alacritty", "-e", "ai-jail"]


@pytest.mark.unit
def test_build_terminal_command_xterm() -> None:
    assert build_terminal_command("xterm", ["ai-jail", "run"]) == [
        "xterm",
        "-e",
        "ai-jail",
        "run",
    ]


@pytest.mark.unit
def test_build_terminal_command_tilix_uses_argv_passthrough() -> None:
    # tilix's `-e` wraps the rest in a shell, dropping all but the first arg.
    # Argv passthrough via `--` is correct for argv preservation.
    assert build_terminal_command("tilix", ["ai-jail", "run", "claude"]) == [
        "tilix",
        "--",
        "ai-jail",
        "run",
        "claude",
    ]


@pytest.mark.unit
def test_build_terminal_command_unknown_raises() -> None:
    with pytest.raises(KeyError):
        build_terminal_command("nonsense-term", ["x"])


@pytest.mark.unit
def test_detect_terminal_prefers_env_var() -> None:
    env = {"JARVIS_TERMINAL": "kitty"}
    assert detect_terminal(env=env, which=lambda _: None) == "kitty"


@pytest.mark.unit
def test_detect_terminal_scans_path_when_no_override() -> None:
    found = {"konsole": "/usr/bin/konsole"}
    assert detect_terminal(env={}, which=found.get) == "konsole"


@pytest.mark.unit
def test_detect_terminal_raises_when_nothing_found() -> None:
    with pytest.raises(NoTerminalFoundError):
        detect_terminal(env={}, which=lambda _: None)


@pytest.mark.unit
def test_detect_terminal_rejects_unsupported_env_override() -> None:
    with pytest.raises(NoTerminalFoundError):
        detect_terminal(env={"JARVIS_TERMINAL": "wezterm"}, which=lambda _: None)


@pytest.mark.unit
async def test_aijail_runtime_spawn_invokes_terminal_with_aijail_no_run_subcommand(
    tmp_path: Path, catalog: Catalog,
) -> None:
    """v0.10+ ai-jail CLI: no `run` subcommand; argv is just `["ai-jail"]`
    and command is read from `<cwd>/.ai-jail`. See gotcha #16."""
    ops = FakeProcessOps(pid=42)
    runtime = AiJailRuntime(
        terminal_resolver=lambda: "kitty",
        process_ops=ops,
    )

    handle = await runtime.spawn(
        tmp_path, permission_profile=None, catalog=catalog,
    )

    assert isinstance(handle, JailHandle)
    assert handle.pid == 42
    assert handle.started_at <= datetime.now(UTC)
    assert len(ops.spawn_calls) == 1
    cmd, cwd = ops.spawn_calls[0]
    assert cmd == ["kitty", "ai-jail"]
    assert cwd == str(tmp_path)
    # .ai-jail is written so ai-jail (no args) finds the command on read.
    # permission_profile=None resolves to catalog fallback ("yolo").
    config = (tmp_path / ".ai-jail").read_text()
    assert 'command = ["claude", "--dangerously-skip-permissions"]' in config


@pytest.mark.unit
async def test_aijail_runtime_kill_sends_signal() -> None:
    ops = FakeProcessOps()
    runtime = AiJailRuntime(
        terminal_resolver=lambda: "kitty",
        process_ops=ops,
    )

    await runtime.kill(JailHandle(id="x", pid=99, started_at=datetime.now(UTC)))

    assert ops.kill_calls == [99]


@pytest.mark.unit
async def test_aijail_runtime_handle_id_is_uuid_not_pid_based(
    tmp_path: Path, catalog: Catalog,
) -> None:
    ops = FakeProcessOps(pid=42)
    runtime = AiJailRuntime(
        terminal_resolver=lambda: "kitty",
        process_ops=ops,
    )
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()

    first = await runtime.spawn(a, permission_profile=None, catalog=catalog)
    second = await runtime.spawn(b, permission_profile=None, catalog=catalog)

    # Structural check: handle.id is a uuid4().hex — 32 lowercase hex chars,
    # independent of PID. Two spawns must yield distinct ids.
    assert first.id != second.id
    assert len(first.id) == 32
    assert all(c in "0123456789abcdef" for c in first.id)


@pytest.mark.unit
async def test_aijail_runtime_kill_swallows_process_lookup_error() -> None:
    ops = FakeProcessOps()
    ops.kill_raises = ProcessLookupError
    runtime = AiJailRuntime(
        terminal_resolver=lambda: "kitty",
        process_ops=ops,
    )

    await runtime.kill(JailHandle(id="x", pid=99, started_at=datetime.now(UTC)))

    assert ops.kill_calls == [99]


@pytest.mark.unit
async def test_aijail_runtime_spawn_writes_settings_when_token_and_base_url_provided(
    tmp_path: Path, catalog: Catalog,
) -> None:
    ops = FakeProcessOps()
    runtime = AiJailRuntime(terminal_resolver=lambda: "kitty", process_ops=ops)

    await runtime.spawn(
        tmp_path,
        permission_profile=None, catalog=catalog,
        token="tok-x", base_url="http://h:1",
    )

    assert (tmp_path / ".claude" / "settings.json").is_file()
    assert ".claude/settings.json" in (tmp_path / ".gitignore").read_text()


@pytest.mark.unit
async def test_aijail_runtime_kill_removes_settings_when_worktree_provided(
    tmp_path: Path,
) -> None:
    write_settings_into_jail(tmp_path, token="tok-x", base_url="http://h:1")
    assert (tmp_path / ".claude" / "settings.json").is_file()

    ops = FakeProcessOps()
    runtime = AiJailRuntime(terminal_resolver=lambda: "kitty", process_ops=ops)

    await runtime.kill(
        JailHandle(id="x", pid=99, started_at=datetime.now(UTC)),
        worktree=tmp_path,
    )

    assert not (tmp_path / ".claude" / "settings.json").exists()


# === .ai-jail config / git-dir discovery (F5.0) ===========================


@pytest.mark.unit
def test_discover_git_dirs_with_no_git_returns_empty(tmp_path: Path) -> None:
    """Empty cwd or one without any `.git` returns an empty list — used
    by NullSessionRuntime tests / non-git scratch dirs."""
    assert _discover_git_dirs(tmp_path) == []


@pytest.mark.unit
def test_discover_git_dirs_on_nonexistent_cwd_returns_empty(tmp_path: Path) -> None:
    """Defensive: cwd doesn't exist (e.g. spawn race vs cleanup) → empty,
    no crash. Covers the `is_dir()` short-circuit branch."""
    assert _discover_git_dirs(tmp_path / "does-not-exist") == []


@pytest.mark.unit
def test_discover_git_dirs_with_local_git_dir_returns_it(tmp_path: Path) -> None:
    """Primary checkout: `cwd/.git` is a real dir → returned as-is."""
    (tmp_path / ".git").mkdir()
    assert _discover_git_dirs(tmp_path) == [tmp_path / ".git"]


@pytest.mark.unit
def test_discover_git_dirs_resolves_worktree_pointer_file(tmp_path: Path) -> None:
    """Secondary worktree (mono): `.git` is a *file* containing
    `gitdir: <project>/.git/worktrees/<name>`; we return `<project>/.git`."""
    project = tmp_path / "proj"
    (project / ".git" / "worktrees" / "feat").mkdir(parents=True)
    cwd = tmp_path / "proj--feat"
    cwd.mkdir()
    (cwd / ".git").write_text(f"gitdir: {project / '.git' / 'worktrees' / 'feat'}\n")
    assert _discover_git_dirs(cwd) == [project / ".git"]


@pytest.mark.unit
def test_discover_git_dirs_multi_repo_scans_immediate_children(tmp_path: Path) -> None:
    """Multi-repo: cwd has subdirs (backend/, frontend/), each with `.git`
    pointer; both originals are returned, sorted."""
    project = tmp_path / "multi"
    for sub in ("backend", "frontend"):
        (project / sub / ".git" / "worktrees" / "feat").mkdir(parents=True)
    cwd = tmp_path / "multi--feat"
    for sub in ("backend", "frontend"):
        (cwd / sub).mkdir(parents=True)
        (cwd / sub / ".git").write_text(
            f"gitdir: {project / sub / '.git' / 'worktrees' / 'feat'}\n"
        )
    expected = [project / "backend" / ".git", project / "frontend" / ".git"]
    assert _discover_git_dirs(cwd) == expected


@pytest.mark.unit
def test_discover_git_dirs_skips_malformed_pointer(tmp_path: Path) -> None:
    """Pointer file that doesn't match `gitdir: ...` is silently skipped
    (graceful: no broken worktree blocks spawn)."""
    cwd = tmp_path / "wt"
    cwd.mkdir()
    (cwd / ".git").write_text("garbage no gitdir prefix\n")
    assert _discover_git_dirs(cwd) == []


@pytest.mark.unit
def test_discover_git_dirs_skips_pointer_with_unexpected_layout(tmp_path: Path) -> None:
    """Pointer to non-worktrees path (e.g. submodule) is skipped — only
    `.../<repo>/.git/worktrees/<name>` layout is recognized."""
    cwd = tmp_path / "wt"
    cwd.mkdir()
    (cwd / ".git").write_text("gitdir: /some/odd/path\n")
    assert _discover_git_dirs(cwd) == []


@pytest.mark.unit
def test_discover_git_dirs_handles_unreadable_pointer(tmp_path: Path) -> None:
    """OSError on read is swallowed (e.g. permission denied on a race);
    we just skip that candidate and continue with the rest."""
    cwd = tmp_path / "wt"
    cwd.mkdir()
    bad = cwd / ".git"
    bad.write_text("gitdir: /x/.git/worktrees/y\n")
    bad.chmod(0o000)
    try:
        # Should not raise even though we cannot read this pointer.
        result = _discover_git_dirs(cwd)
    finally:
        bad.chmod(0o644)
    assert result == []


@pytest.mark.unit
def test_write_aijail_config_with_no_git_uses_empty_rw_maps(tmp_path: Path) -> None:
    write_aijail_config(tmp_path, claude_args=["--dangerously-skip-permissions"])
    content = (tmp_path / ".ai-jail").read_text()
    assert 'command = ["claude", "--dangerously-skip-permissions"]' in content
    assert "rw_maps = []" in content


@pytest.mark.unit
def test_write_aijail_config_with_git_pointer_emits_rw_maps(tmp_path: Path) -> None:
    """Worktree pointer must end up in rw_maps so `git status` resolves
    inside the jail (F5.0 confirmed this is required by ai-jail bwrap)."""
    project = tmp_path / "proj"
    (project / ".git" / "worktrees" / "feat").mkdir(parents=True)
    cwd = tmp_path / "proj--feat"
    cwd.mkdir()
    (cwd / ".git").write_text(f"gitdir: {project / '.git' / 'worktrees' / 'feat'}\n")
    write_aijail_config(cwd, claude_args=[])
    content = (cwd / ".ai-jail").read_text()
    assert f'"{project / ".git"}"' in content
    assert "ro_maps = []" in content
    assert "hide_dotdirs = []" in content


@pytest.mark.unit
async def test_aijail_runtime_spawn_writes_aijail_config_before_invoking(
    tmp_path: Path, catalog: Catalog,
) -> None:
    """spawn always writes `.ai-jail` (even without token/base_url) since
    ai-jail v0.10+ needs the config to know what `command` to exec."""
    ops = FakeProcessOps()
    runtime = AiJailRuntime(terminal_resolver=lambda: "kitty", process_ops=ops)

    await runtime.spawn(tmp_path, permission_profile=None, catalog=catalog)

    assert (tmp_path / ".ai-jail").is_file()
    assert 'command = ["claude"' in (tmp_path / ".ai-jail").read_text()
