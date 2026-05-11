from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.core.catalog import Catalog
from orchestrator.core.git import GitWorktreeOps
from orchestrator.core.port_allocator import PortAllocator
from orchestrator.events.broadcaster import WsBroadcaster
from orchestrator.hooks.tokens import TokenRegistry
from orchestrator.notifications.sink import NotifierSink
from orchestrator.sandbox.docker_ops import DockerOps
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


def resolve_git_ops(request: Request) -> GitWorktreeOps:
    git: GitWorktreeOps | None = request.app.state.git_ops
    if git is None:  # pragma: no cover
        raise RuntimeError("git_ops not configured in app.state")
    return git


def resolve_docker_ops(request: Request) -> "DockerOps":
    docker: DockerOps | None = request.app.state.docker_ops
    if docker is None:  # pragma: no cover
        raise RuntimeError("docker_ops not configured in app.state")
    return docker


def resolve_port_allocator(request: Request) -> "PortAllocator":
    alloc: PortAllocator | None = request.app.state.port_allocator
    if alloc is None:  # pragma: no cover
        raise RuntimeError("port_allocator not configured in app.state")
    return alloc


def resolve_catalog(request: Request) -> Catalog:
    cat: Catalog | None = request.app.state.catalog
    if cat is None:  # pragma: no cover
        raise RuntimeError("catalog not configured in app.state")
    return cat
