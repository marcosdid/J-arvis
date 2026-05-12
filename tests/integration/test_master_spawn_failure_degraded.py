"""F8.e: spawn failure → daemon sobe sem master (estado degradado)."""
import asyncio
import os
from collections import deque
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator import main as _main
from orchestrator.main import create_app
from orchestrator.sandbox.pty_runtime import MasterPtyHandle
from orchestrator.store.database import Database
from tests.integration.conftest import FakeSessionRuntime


class _StubPtyOps:
    def __init__(self) -> None:
        self._closed = asyncio.Event()
        self._chunks: deque[bytes] = deque()
        self._evt = asyncio.Event()

    async def read(self, master_fd: int, n: int = 4096) -> bytes:
        await self._closed.wait()
        return b""

    async def write(self, master_fd: int, data: bytes) -> None:
        pass

    def resize(self, master_fd: int, rows: int, cols: int) -> None:
        pass

    def kill(self, pid: int) -> None:
        pass

    def close(self, master_fd: int) -> None:
        self._closed.set()


@pytest.mark.integration
async def test_daemon_boots_without_master_on_spawn_failure(
    db: Database, runtime: FakeSessionRuntime,
) -> None:
    """ai-jail não no PATH → spawn raise FileNotFoundError.
    Daemon sobe; resto da API funciona."""
    with patch(
        "orchestrator.sandbox.pty_runtime.MasterSessionRuntime.spawn",
        side_effect=FileNotFoundError("ai-jail not found"),
    ):
        app = create_app(database=db, runtime=runtime, ui_dist=None)
        async with app.router.lifespan_context(app), AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t",
        ) as c:
            r = await c.get("/health")
            assert r.status_code == 200
            assert getattr(app.state, "master_handle", "missing") is None


@pytest.mark.integration
async def test_watchdog_runs_alive_check_on_success(
    db: Database, runtime: FakeSessionRuntime,
) -> None:
    """Watchdog dorme 2s, faz os.kill(pid, 0) — se PID alive, segue.
    Patch sleep pra zerar e usa os.getpid() pra alive succeed.
    """
    stub_ops = _StubPtyOps()

    async def _fake_spawn(self: object, **kwargs: object) -> MasterPtyHandle:
        return MasterPtyHandle(
            pid=os.getpid(), master_fd=7,
            claude_session_id="sess-x",
            started_at=datetime.now(UTC),
        )

    real_sleep = asyncio.sleep

    async def _zero_sleep(_t: float) -> None:
        await real_sleep(0)

    with patch(
        "orchestrator.main.SubprocessPtyOps",
        return_value=stub_ops,
    ), patch(
        "orchestrator.sandbox.pty_runtime.MasterSessionRuntime.spawn",
        new=_fake_spawn,
    ), patch(
        "orchestrator.main.Path.mkdir",
    ), patch(
        "orchestrator.main.asyncio.sleep",
        new=_zero_sleep,
    ):
        app = create_app(database=db, runtime=runtime, ui_dist=None)
        async with app.router.lifespan_context(app):
            assert app.state.master_handle is not None
            # Aguarda watchdog terminar (PID alive → no-op)
            watchdog = app.state._master_watchdog
            await asyncio.wait_for(watchdog, timeout=2.0)
            # Watchdog terminou sem re-spawn — handle inalterado
            assert app.state.master_handle is not None


@pytest.mark.integration
async def test_watchdog_logs_warning_when_pid_dead(
    db: Database, runtime: FakeSessionRuntime,
) -> None:
    """Watchdog: os.kill(pid, 0) raise ProcessLookupError → logger.warning.
    Re-spawn cobre via E2E em F8.g; aqui só validamos que a branch detect roda.
    """
    stub_ops = _StubPtyOps()

    async def _fake_spawn(self: object, **kwargs: object) -> MasterPtyHandle:
        return MasterPtyHandle(
            pid=99999, master_fd=7,
            claude_session_id="sess-x",
            started_at=datetime.now(UTC),
        )

    real_sleep = asyncio.sleep

    async def _zero_sleep(_t: float) -> None:
        await real_sleep(0)

    # Captura todos os warning calls do logger do main
    warning_calls: list[str] = []
    orig_warning = _main.logger.warning

    def _capture(msg: str, *args: object, **kw: object) -> None:
        warning_calls.append(msg % args if args else msg)
        orig_warning(msg, *args, **kw)

    with patch(
        "orchestrator.main.SubprocessPtyOps",
        return_value=stub_ops,
    ), patch(
        "orchestrator.sandbox.pty_runtime.MasterSessionRuntime.spawn",
        new=_fake_spawn,
    ), patch(
        "orchestrator.main.Path.mkdir",
    ), patch(
        "orchestrator.main.asyncio.sleep",
        new=_zero_sleep,
    ), patch(
        "orchestrator.main.os.kill",
        side_effect=ProcessLookupError(),
    ), patch.object(_main.logger, "warning", side_effect=_capture):
        app = create_app(database=db, runtime=runtime, ui_dist=None)
        async with app.router.lifespan_context(app):
            watchdog = app.state._master_watchdog
            await asyncio.wait_for(watchdog, timeout=2.0)
    assert any("--resume may have failed" in m for m in warning_calls)
