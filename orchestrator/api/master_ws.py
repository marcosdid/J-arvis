"""F8.e: WebSocket bridge entre browser e PTY do master session."""
from __future__ import annotations

import asyncio
import contextlib
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from orchestrator.sandbox.pty_runtime import MasterPtyHandle, PtyProcessOps

logger = logging.getLogger(__name__)


class PtyMultiplexer:
    """Fan-out: 1 reader no master_fd → N subscriber queues."""

    def __init__(self, pty_ops: PtyProcessOps, master_fd: int) -> None:
        self._pty = pty_ops
        self._master_fd = master_fd
        self._subscribers: set[asyncio.Queue[bytes]] = set()
        self._reader_task = asyncio.create_task(self._read_loop())

    async def _read_loop(self) -> None:
        while True:
            chunk = await self._pty.read(self._master_fd, 4096)
            if not chunk:
                return  # EOF (PTY morreu)
            for q in list(self._subscribers):
                try:
                    q.put_nowait(chunk)
                except asyncio.QueueFull:
                    # Decisão 10: drop slow subscriber, mantém reader vivo
                    self._subscribers.discard(q)
                    logger.warning("dropped slow master WS subscriber")

    async def subscribe(self) -> asyncio.Queue[bytes]:
        q: asyncio.Queue[bytes] = asyncio.Queue(maxsize=1024)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[bytes]) -> None:
        self._subscribers.discard(q)

    async def shutdown(self) -> None:
        """Cancela reader + drena subscribers com sentinel EOF (b'').

        Subscribers que estavam aguardando ``queue.get()`` recebem ``b''`` (EOF)
        e podem sair do loop graciosamente — sem isso, re-spawn pelo watchdog
        deixaria WS connections existentes penduradas pra sempre no multiplexer
        morto.
        """
        self._reader_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._reader_task
        for q in list(self._subscribers):
            # Queue cheia → subscriber já vai detectar disconnect na próxima get
            with contextlib.suppress(asyncio.QueueFull):
                q.put_nowait(b"")
        self._subscribers.clear()


router = APIRouter()


@router.websocket("/ws/master")
async def master_ws(websocket: WebSocket) -> None:
    """Bridge bidirectional entre browser e PTY do master session."""
    handle: MasterPtyHandle | None = getattr(websocket.app.state, "master_handle", None)
    mux: PtyMultiplexer | None = getattr(websocket.app.state, "master_multiplexer", None)

    if handle is None or mux is None:
        await websocket.accept()
        await websocket.send_json({
            "type": "system", "level": "error",
            "message": "master session not available",
        })
        await websocket.close(code=1011, reason="master_not_ready")
        return

    await websocket.accept()
    pty_ops: PtyProcessOps = websocket.app.state.master_pty_ops
    write_lock: asyncio.Lock = websocket.app.state.master_write_lock
    queue = await mux.subscribe()

    async def browser_to_pty() -> None:
        async for msg in websocket.iter_json():
            if msg["type"] == "input":
                async with write_lock:
                    await pty_ops.write(handle.master_fd, msg["data"].encode())
            elif msg["type"] == "resize":  # pragma: no branch
                pty_ops.resize(handle.master_fd, msg["rows"], msg["cols"])

    async def pty_to_browser() -> None:
        while True:
            chunk = await queue.get()
            if not chunk:
                # Multiplexer shutdown OR PTY EOF — terminate this side
                return
            await websocket.send_json({
                "type": "output",
                "data": chunk.decode("utf-8", errors="replace"),
            })

    tasks = [
        asyncio.create_task(browser_to_pty()),
        asyncio.create_task(pty_to_browser()),
    ]
    try:
        # Quando QUALQUER lado termina (WS close, EOF, etc.), cancela o outro
        # — senão pty_to_browser fica esperando queue.get() pra sempre.
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
        for t in pending:
            with contextlib.suppress(asyncio.CancelledError, WebSocketDisconnect):
                await t
        for t in done:
            with contextlib.suppress(WebSocketDisconnect):
                t.result()
    finally:
        mux.unsubscribe(queue)
        # Garantia: se saímos por EOF do mux (shutdown/PTY died), feche o WS
        # explicitamente — Starlette não fecha sozinho quando o handler retorna.
        with contextlib.suppress(RuntimeError, WebSocketDisconnect):
            await websocket.close(code=1011, reason="master_pty_unavailable")
