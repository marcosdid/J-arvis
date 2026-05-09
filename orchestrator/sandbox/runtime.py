from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class JailHandle:
    """Opaque handle returned by ``SessionRuntime.spawn``.

    ``id`` is the runtime-specific identifier (e.g., ai-jail session name).
    ``pid`` is the OS process id of the jailed process. ``started_at`` is when
    the spawn returned successfully.
    """

    id: str
    pid: int
    started_at: datetime


class SessionRuntime(Protocol):
    """Abstraction over how a Claude Code session is launched and stopped.

    Production implementation: ``AiJailRuntime`` (F1.e) shells out to
    ``ai-jail`` and a native terminal emulator (ADR-0008).

    Test implementation: ``FakeSessionRuntime`` in ``tests/integration/conftest.py``
    tracks state in memory.
    """

    async def spawn(self, worktree: Path) -> JailHandle: ...

    async def kill(self, handle: JailHandle) -> None: ...
