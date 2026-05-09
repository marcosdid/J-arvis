import asyncio
import logging
from typing import Protocol

_log = logging.getLogger(__name__)


class CommandRunner(Protocol):
    async def run(self, argv: list[str]) -> None: ...


class SubprocessRunner:  # pragma: no cover
    """Production runner. Excluded from coverage: needs notify-send + libnotify
    on the host. Behaviour is exercised manually."""
    async def run(self, argv: list[str]) -> None:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()


class NotifySendNotifier:
    def __init__(self, *, runner: CommandRunner | None = None) -> None:
        self._runner = runner or SubprocessRunner()
        self._warned = False

    async def notify(self, *, summary: str, body: str, icon: str) -> None:
        argv = ["notify-send", f"--icon={icon}", summary, body]
        try:
            await self._runner.run(argv)
        except FileNotFoundError:
            if not self._warned:
                _log.warning(
                    "notify-send not found; desktop notifications will keep being "
                    "attempted but warnings are silenced after this one"
                )
                self._warned = True


class NoopNotifier:
    async def notify(self, *, summary: str, body: str, icon: str) -> None:
        return None
