"""F9.2: /ws/master responds to ping with matching pong."""
import asyncio
import os
import time
from collections import deque
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from orchestrator.main import create_app
from orchestrator.sandbox.pty_runtime import MasterPtyHandle
from orchestrator.store.database import Database
from tests.integration.conftest import FakeSessionRuntime


class _StubPtyOps:
    """Fake PtyProcessOps: produces no reads and records nothing (pong needs no PTY)."""

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


def _fake_spawn_factory(stub_ops: _StubPtyOps) -> object:
    async def _fake_spawn(self: object, **kwargs: object) -> MasterPtyHandle:
        return MasterPtyHandle(
            pid=os.getpid(), master_fd=7,
            claude_session_id="sess-x",
            started_at=datetime.now(UTC),
        )
    return _fake_spawn


@pytest.mark.integration
def test_ws_master_pong_matches_ping_ts(
    db: Database, runtime: FakeSessionRuntime,
) -> None:
    """Sending a ping message returns a pong with the same ts."""
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
            assert app.state.master_handle is not None
            with client.websocket_connect("/ws/master") as ws:
                time.sleep(0.1)
                ws.send_json({"type": "ping", "ts": 1700000000123})
                msg = ws.receive_json()
                assert msg == {"type": "pong", "ts": 1700000000123}


@pytest.mark.integration
def test_ws_master_unknown_message_type_is_ignored(
    db: Database, runtime: FakeSessionRuntime,
) -> None:
    """Sending an unknown message type is silently ignored (no crash, no response)."""
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
            assert app.state.master_handle is not None
            with client.websocket_connect("/ws/master") as ws:
                time.sleep(0.1)
                ws.send_json({"type": "unknown"})
                # Then send a ping to confirm the handler is still alive
                ws.send_json({"type": "ping", "ts": 42})
                msg = ws.receive_json()
                assert msg == {"type": "pong", "ts": 42}
