from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.events.broadcaster import WsBroadcaster
from orchestrator.hooks.tokens import TokenRegistry
from orchestrator.notifications.sink import NotifierSink
from orchestrator.sandbox.runtime import SessionRuntime
from orchestrator.store.database import Database


def resolve_database(request: Request) -> Database:
    db: Database | None = request.app.state.database
    if db is None:  # pragma: no cover
        raise RuntimeError("router mounted without a database")
    return db


def resolve_runtime(request: Request) -> SessionRuntime:
    runtime: SessionRuntime | None = request.app.state.runtime
    if runtime is None:  # pragma: no cover
        raise RuntimeError("router mounted without a runtime")
    return runtime


async def get_db_session(
    database: Annotated[Database, Depends(resolve_database)],
) -> AsyncIterator[AsyncSession]:
    async with database.session() as s:
        yield s


def resolve_token_registry(request: Request) -> TokenRegistry:
    reg: TokenRegistry | None = request.app.state.token_registry
    if reg is None:  # pragma: no cover
        raise RuntimeError("router mounted without token registry")
    return reg


def resolve_broadcaster(request: Request) -> WsBroadcaster:
    bc: WsBroadcaster | None = request.app.state.ws_broadcaster
    if bc is None:  # pragma: no cover
        raise RuntimeError("router mounted without broadcaster")
    return bc


def resolve_notifier(request: Request) -> NotifierSink:
    n: NotifierSink | None = request.app.state.notifier
    if n is None:  # pragma: no cover
        raise RuntimeError("router mounted without notifier")
    return n
