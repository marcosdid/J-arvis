"""F8.e: WebSocket /ws/master + race protection + happy path bridge."""
import asyncio
import os
import time
from collections import deque
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from orchestrator.main import create_app
from orchestrator.sandbox.pty_runtime import MasterPtyHandle
from orchestrator.store.database import Database
from tests.integration.conftest import FakeSessionRuntime


class _StubPtyOps:
    """Fake PtyProcessOps que registra writes/resizes e produz reads scriptados.

    Reads são bloqueantes até `feed()` ser chamado, evitando race com subscribe.
    """

    def __init__(self) -> None:
        self._chunks: deque[bytes] = deque()
        self._chunk_available = asyncio.Event()
        self._closed = asyncio.Event()
        self.writes: list[bytes] = []
        self.resizes: list[tuple[int, int]] = []

    def feed(self, chunk: bytes) -> None:
        self._chunks.append(chunk)
        self._chunk_available.set()

    async def read(self, master_fd: int, n: int = 4096) -> bytes:
        while not self._chunks:
            self._chunk_available.clear()
            done, _ = await asyncio.wait(
                [
                    asyncio.create_task(self._chunk_available.wait()),
                    asyncio.create_task(self._closed.wait()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )
            if self._closed.is_set() and not self._chunks:
                return b""
            for t in done:
                if not t.done():
                    t.cancel()
        return self._chunks.popleft()

    async def write(self, master_fd: int, data: bytes) -> None:
        self.writes.append(data)

    def resize(self, master_fd: int, rows: int, cols: int) -> None:
        self.resizes.append((rows, cols))

    def kill(self, pid: int) -> None:
        pass

    def close(self, master_fd: int) -> None:
        self._closed.set()


@pytest.mark.integration
async def test_ws_master_not_ready_closes_1011(
    db: Database, runtime: FakeSessionRuntime,
) -> None:
    """master_handle=None (spawn failure) → WS connect retorna system error + close 1011."""
    with patch(
        "orchestrator.sandbox.pty_runtime.MasterSessionRuntime.spawn",
        side_effect=FileNotFoundError("forced"),
    ):
        app = create_app(database=db, runtime=runtime, ui_dist=None)
        with TestClient(app) as client:
            assert app.state.master_handle is None
            with client.websocket_connect("/ws/master") as ws:
                msg = ws.receive_json()
                assert msg["type"] == "system"
                assert msg["level"] == "error"
                assert "not available" in msg["message"].lower()
                with pytest.raises(WebSocketDisconnect) as exc_info:
                    ws.receive_json()
                assert exc_info.value.code == 1011


def _fake_spawn_factory(stub_ops: _StubPtyOps) -> object:
    """Retorna replacement de MasterSessionRuntime.spawn que devolve handle previsível.
    Usa os.getpid() pra que o watchdog (os.kill(pid, 0)) não dispare re-spawn.
    """
    async def _fake_spawn(self: object, **kwargs: object) -> MasterPtyHandle:
        return MasterPtyHandle(
            pid=os.getpid(), master_fd=7,
            claude_session_id="sess-x",
            started_at=datetime.now(UTC),
        )
    return _fake_spawn


@pytest.mark.integration
def test_ws_master_bridges_pty_output_and_input(
    db: Database, runtime: FakeSessionRuntime,
) -> None:
    """Happy path: PTY chunk → WS output; WS input → PTY write; WS resize → PTY resize."""
    stub_ops = _StubPtyOps()

    with patch(
        "orchestrator.main.SubprocessPtyOps",
        return_value=stub_ops,
    ), patch(
        "orchestrator.sandbox.pty_runtime.MasterSessionRuntime.spawn",
        new=_fake_spawn_factory(stub_ops),
    ), patch(
        "orchestrator.main.Path.mkdir",  # bypass read-only fs
    ):
        app = create_app(database=db, runtime=runtime, ui_dist=None)
        with TestClient(app) as client:
            assert app.state.master_handle is not None
            assert app.state.master_multiplexer is not None
            with client.websocket_connect("/ws/master") as ws:
                # Dá tempo do handler chamar mux.subscribe() antes de emitir chunk.
                # Feed APÓS subscribe garante que o chunk vai pra queue.
                time.sleep(0.1)
                stub_ops.feed(b"hello-pty")
                out = ws.receive_json()
                assert out["type"] == "output"
                assert out["data"] == "hello-pty"
                ws.send_json({"type": "input", "data": "ls\n"})
                ws.send_json({"type": "resize", "rows": 30, "cols": 120})
                for _ in range(40):
                    if stub_ops.writes and stub_ops.resizes:
                        break
                    time.sleep(0.05)
                assert b"ls\n" in stub_ops.writes
                assert (30, 120) in stub_ops.resizes


@pytest.mark.integration
def test_ws_pty_to_browser_exits_on_multiplexer_shutdown(
    db: Database, runtime: FakeSessionRuntime,
) -> None:
    """Quando multiplexer.shutdown() é chamado (ex: watchdog re-spawn), WS
    connections existentes recebem sentinel EOF via queue e o lado
    pty_to_browser termina sem ficar pendurado em queue.get() pra sempre.

    Verificado via: shutdown limpa subscribers, e o handler async sai do
    loop (não fica eternamente bloqueado em queue.get).
    """
    stub_ops = _StubPtyOps()
    with patch(
        "orchestrator.main.SubprocessPtyOps",
        return_value=stub_ops,
    ), patch(
        "orchestrator.sandbox.pty_runtime.MasterSessionRuntime.spawn",
        new=_fake_spawn_factory(stub_ops),
    ), patch(
        "orchestrator.main.Path.mkdir",
    ):
        app = create_app(database=db, runtime=runtime, ui_dist=None)
        with TestClient(app) as client:
            mux = app.state.master_multiplexer
            assert mux is not None
            with client.websocket_connect("/ws/master") as ws:
                # Espera subscribe acontecer no handler async
                for _ in range(40):
                    if len(mux._subscribers) == 1:  # type: ignore[attr-defined]
                        break
                    time.sleep(0.05)
                assert len(mux._subscribers) == 1  # type: ignore[attr-defined]

                # Dispara shutdown do mux no event loop do app via portal do WS
                ws.portal.call(mux.shutdown)

                # Shutdown drenou subscribers via sentinel + clear()
                assert len(mux._subscribers) == 0  # type: ignore[attr-defined]

                # pty_to_browser detectou b"" e retornou; asyncio.wait disparou
                # cancel em browser_to_pty; handler async caminha pro finally
                # e o WS é fechado pelo Starlette. Recebe disconnect limpo.
                with pytest.raises(WebSocketDisconnect):
                    ws.receive_json()


@pytest.mark.integration
def test_ws_master_unsubscribe_on_disconnect(
    db: Database, runtime: FakeSessionRuntime,
) -> None:
    """Quando WS desconecta, mux.unsubscribe é chamado (queue removida)."""
    stub_ops = _StubPtyOps()
    with patch(
        "orchestrator.main.SubprocessPtyOps",
        return_value=stub_ops,
    ), patch(
        "orchestrator.sandbox.pty_runtime.MasterSessionRuntime.spawn",
        new=_fake_spawn_factory(stub_ops),
    ), patch(
        "orchestrator.main.Path.mkdir",
    ):
        app = create_app(database=db, runtime=runtime, ui_dist=None)
        with TestClient(app) as client:
            mux = app.state.master_multiplexer
            with client.websocket_connect("/ws/master"):
                for _ in range(40):
                    if len(mux._subscribers) == 1:  # type: ignore[attr-defined]
                        break
                    time.sleep(0.05)
                assert len(mux._subscribers) == 1  # type: ignore[attr-defined]
            for _ in range(40):
                if len(mux._subscribers) == 0:  # type: ignore[attr-defined]
                    break
                time.sleep(0.05)
            assert len(mux._subscribers) == 0  # type: ignore[attr-defined]
