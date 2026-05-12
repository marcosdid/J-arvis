"""F8: PTY runtime pra master session. Spawna ai-jail + claude num PTY pair."""
from __future__ import annotations

import asyncio
import contextlib
import fcntl
import os
import signal
import struct
import subprocess
import termios
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, runtime_checkable
from urllib.parse import urlparse
from uuid import uuid4

from orchestrator.sandbox.master_settings_writer import (
    write_master_aijail_config,
    write_master_settings,
)


@runtime_checkable
class PtyProcessOps(Protocol):
    """Abstração de PTY pair (fakeable em tests)."""

    def spawn(self, cmd: list[str], cwd: str) -> tuple[int, int]:
        """Spawn process em PTY, retorna (pid, master_fd)."""

    async def read(self, master_fd: int, n: int = 4096) -> bytes:
        """Read até `n` bytes do master_fd. Retorna b'' em EOF."""

    async def write(self, master_fd: int, data: bytes) -> None: ...

    def resize(self, master_fd: int, rows: int, cols: int) -> None: ...

    def kill(self, pid: int) -> None: ...

    def close(self, master_fd: int) -> None: ...


@dataclass(frozen=True)
class MasterPtyHandle:
    pid: int
    master_fd: int
    claude_session_id: str
    started_at: datetime


class MasterSessionRuntime:
    """Spawn ai-jail + claude num PTY (sem terminal emulator wrapper).

    Diferente de AiJailRuntime (F1+): saída vai pro master_fd que será
    bridged via WebSocket ao xterm.js no browser.
    """

    def __init__(self, pty_ops: PtyProcessOps) -> None:
        self._pty = pty_ops

    async def spawn(
        self,
        *,
        cwd: Path,
        claude_session_id: str | None,
        mcp_url: str,
        token: str,
    ) -> MasterPtyHandle:
        session_id = claude_session_id or uuid4().hex
        write_master_settings(cwd, mcp_url=mcp_url, token=token)
        allow_port = urlparse(mcp_url).port or 8765
        write_master_aijail_config(cwd, claude_session_id=session_id, allow_port=allow_port)
        pid, fd = self._pty.spawn(["ai-jail"], str(cwd))
        return MasterPtyHandle(
            pid=pid, master_fd=fd,
            claude_session_id=session_id,
            started_at=datetime.now(UTC),
        )


class SubprocessPtyOps:  # pragma: no cover
    """Production PtyProcessOps: real os.openpty() + subprocess.

    Excluded from unit coverage (requires real OS pty + subprocess).
    Coberto por tests/integration/test_pty_real_subprocess.py.
    """

    def __init__(self) -> None:
        self._procs: dict[int, subprocess.Popen[bytes]] = {}

    def spawn(self, cmd: list[str], cwd: str) -> tuple[int, int]:
        master_fd, slave_fd = os.openpty()
        proc = subprocess.Popen(
            cmd, cwd=cwd,
            stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
            start_new_session=True,
        )
        os.close(slave_fd)
        self._procs[master_fd] = proc
        return (proc.pid, master_fd)

    async def read(self, master_fd: int, n: int = 4096) -> bytes:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[bytes] = loop.create_future()

        def _on_readable() -> None:
            try:
                data = os.read(master_fd, n)
                if not future.done():
                    future.set_result(data)
            except OSError:
                if not future.done():
                    future.set_result(b"")
            finally:
                loop.remove_reader(master_fd)

        loop.add_reader(master_fd, _on_readable)
        return await future

    async def write(self, master_fd: int, data: bytes) -> None:
        os.write(master_fd, data)

    def resize(self, master_fd: int, rows: int, cols: int) -> None:
        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)

    def kill(self, pid: int) -> None:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(os.getpgid(pid), signal.SIGTERM)

    def close(self, master_fd: int) -> None:
        with contextlib.suppress(OSError):
            os.close(master_fd)
        proc = self._procs.pop(master_fd, None)
        if proc is not None:
            try:
                proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                proc.kill()
