"""No-op SessionRuntime for environments without a graphical display.

Used in E2E containers (no X server, no terminal emulator) and as a dry-run
mode. Records nothing; production-grade no-op. The matching test fake lives in
``tests/integration/conftest.py`` and additionally records calls for
assertions.
"""

from datetime import UTC, datetime
from itertools import count
from pathlib import Path
from uuid import uuid4

from orchestrator.sandbox.runtime import JailHandle


class NullSessionRuntime:
    def __init__(self) -> None:
        self._pid_counter = count(start=30001)

    async def spawn(self, _worktree: Path) -> JailHandle:
        return JailHandle(
            id=uuid4().hex,
            pid=next(self._pid_counter),
            started_at=datetime.now(UTC),
        )

    async def kill(self, handle: JailHandle) -> None:
        return None
