"""AiJail-backed SessionRuntime.

Spawns Claude Code inside `ai-jail` running under the user's native terminal
emulator (per ADR-0008). Production wiring picks the terminal via
``JARVIS_TERMINAL`` env var or by scanning ``$PATH``; tests inject fakes for
all I/O boundaries.
"""

import os
import shutil
import signal
import subprocess
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from orchestrator.sandbox.runtime import JailHandle
from orchestrator.sandbox.settings_writer import (
    ensure_gitignore_entry,
    remove_settings_from_jail,
    write_settings_into_jail,
)

# Order matters: first found in PATH wins when JARVIS_TERMINAL is unset.
_TERMINAL_PRIORITY: tuple[str, ...] = (
    "gnome-terminal",
    "konsole",
    "xfce4-terminal",
    "kitty",
    "alacritty",
    "foot",
    "tilix",
    "terminator",
    "xterm",
)

# Each entry returns the argv prefix (everything before the inner cmd).
_TERMINAL_PREFIXES: dict[str, list[str]] = {
    "gnome-terminal": ["gnome-terminal", "--"],
    "konsole": ["konsole", "-e"],
    "xfce4-terminal": ["xfce4-terminal", "-x"],
    "kitty": ["kitty"],
    "alacritty": ["alacritty", "-e"],
    "foot": ["foot"],
    # tilix's `-e` wraps remainder in /bin/sh -c, dropping argv tail; use
    # argv passthrough via `--`.
    "tilix": ["tilix", "--"],
    "terminator": ["terminator", "-x"],
    "xterm": ["xterm", "-e"],
}


class NoTerminalFoundError(Exception):
    pass


class ProcessOps(Protocol):
    def spawn(self, cmd: list[str], cwd: str) -> int: ...

    def kill(self, pid: int) -> None: ...


def build_terminal_command(terminal: str, inner_cmd: list[str]) -> list[str]:
    return [*_TERMINAL_PREFIXES[terminal], *inner_cmd]


def detect_terminal(
    env: Mapping[str, str] | None = None,
    which: Callable[[str], str | None] = shutil.which,
) -> str:
    env_map = os.environ if env is None else env
    override = env_map.get("JARVIS_TERMINAL")
    if override:
        if override not in _TERMINAL_PREFIXES:
            raise NoTerminalFoundError(
                f"JARVIS_TERMINAL={override!r} is not a supported terminal; "
                f"choose one of: {', '.join(_TERMINAL_PREFIXES)}"
            )
        return override
    for name in _TERMINAL_PRIORITY:
        if which(name):
            return name
    raise NoTerminalFoundError(
        "no supported terminal emulator found in PATH; "
        f"set JARVIS_TERMINAL or install one of: {', '.join(_TERMINAL_PRIORITY)}"
    )


class AiJailRuntime:
    """Spawns Claude Code inside ai-jail in the user's native terminal."""

    def __init__(
        self,
        terminal_resolver: Callable[[], str],
        process_ops: ProcessOps,
    ) -> None:
        self._terminal_resolver = terminal_resolver
        self._process_ops = process_ops

    async def spawn(
        self,
        worktree: Path,
        *,
        token: str | None = None,
        base_url: str | None = None,
    ) -> JailHandle:
        if token is not None and base_url is not None:
            write_settings_into_jail(worktree, token=token, base_url=base_url)
            ensure_gitignore_entry(worktree)
        terminal = self._terminal_resolver()
        inner = ["ai-jail", "run", "--", "claude"]
        cmd = build_terminal_command(terminal, inner)
        # Popen returns immediately; no need to offload to a thread.
        pid = self._process_ops.spawn(cmd, str(worktree))
        return JailHandle(id=uuid4().hex, pid=pid, started_at=datetime.now(UTC))

    async def kill(self, handle: JailHandle, *, worktree: Path | None = None) -> None:
        # os.kill is a non-blocking syscall; no need to offload to a thread.
        try:  # noqa: SIM105 — explicit branch keeps process-already-gone path obvious
            self._process_ops.kill(handle.pid)
        except ProcessLookupError:
            pass  # process already gone — idempotent
        if worktree is not None:
            remove_settings_from_jail(worktree)


class SubprocessProcessOps:  # pragma: no cover
    """Production ProcessOps: real subprocess + signal.

    Excluded from coverage: tested manually (requires a real terminal emulator
    and ai-jail installed; both are system-level dependencies). All branching
    logic lives in ``AiJailRuntime`` which has full unit coverage.
    """

    def spawn(self, cmd: list[str], cwd: str) -> int:
        process = subprocess.Popen(cmd, cwd=cwd)
        return process.pid

    def kill(self, pid: int) -> None:
        os.kill(pid, signal.SIGTERM)
