import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from alembic.config import Config
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from alembic import command

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"


class Database:
    def __init__(self, url: str) -> None:
        self._url = url
        self._engine = create_async_engine(url, future=True)
        self._sessionmaker = async_sessionmaker(self._engine, expire_on_commit=False)
        self._migration_lock = asyncio.Lock()

    async def bootstrap(self) -> None:
        async with self._migration_lock:
            await asyncio.to_thread(self._run_migrations)

    def _run_migrations(self) -> None:
        cfg = Config(str(ALEMBIC_INI))
        cfg.set_main_option("sqlalchemy.url", self._sync_url())
        command.upgrade(cfg, "head")

    def _sync_url(self) -> str:
        return self._url.replace("sqlite+aiosqlite://", "sqlite://", 1)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self._sessionmaker() as s:
            yield s

    async def close(self) -> None:
        await self._engine.dispose()
