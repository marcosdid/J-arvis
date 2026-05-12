"""F8.e: cleanup de master session órfã no startup."""
import contextlib
import os
import signal

from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.store.models import MasterSession


async def cleanup_orphan_master_at_startup(s: AsyncSession) -> None:
    """Se daemon caiu sem matar PTY, tenta SIGKILL do PID antigo."""
    master = await s.get(MasterSession, "singleton")
    if master and master.pid is not None:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(os.getpgid(master.pid), signal.SIGKILL)
        master.pid = None
        await s.commit()
