from datetime import UTC, datetime
from pathlib import Path

import pytest

from orchestrator.sandbox.aijail import (
    AiJailRuntime,
    NoTerminalFoundError,
    build_terminal_command,
    detect_terminal,
)
from orchestrator.sandbox.runtime import JailHandle


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
async def test_aijail_runtime_spawn_invokes_terminal_with_aijail_and_claude() -> None:
    ops = FakeProcessOps(pid=42)
    runtime = AiJailRuntime(
        terminal_resolver=lambda: "kitty",
        process_ops=ops,
    )

    handle = await runtime.spawn(Path("/tmp/repo"))

    assert isinstance(handle, JailHandle)
    assert handle.pid == 42
    assert handle.started_at <= datetime.now(UTC)
    assert len(ops.spawn_calls) == 1
    cmd, cwd = ops.spawn_calls[0]
    assert "kitty" in cmd
    assert "ai-jail" in cmd
    assert "claude" in cmd
    assert cwd == "/tmp/repo"


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
async def test_aijail_runtime_handle_id_is_uuid_not_pid_based() -> None:
    ops = FakeProcessOps(pid=42)
    runtime = AiJailRuntime(
        terminal_resolver=lambda: "kitty",
        process_ops=ops,
    )

    first = await runtime.spawn(Path("/tmp/a"))
    second = await runtime.spawn(Path("/tmp/b"))

    assert first.id != second.id
    assert "42" not in first.id  # PID must not leak into the handle id


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
