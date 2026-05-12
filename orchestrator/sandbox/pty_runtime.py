"""F8: PTY runtime pra master session. Spawna ai-jail + claude num PTY pair."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


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
