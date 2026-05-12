"""F8.e: PtyMultiplexer fan-out + overflow + shutdown."""
import asyncio
from collections import deque

from orchestrator.api.master_ws import PtyMultiplexer


class _StubPtyOps:
    """Fake que retorna chunks de uma deque via read()."""

    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = deque(chunks)
        self._closed = asyncio.Event()

    async def read(self, master_fd: int, n: int = 4096) -> bytes:
        if self._chunks:
            return self._chunks.popleft()
        # Bloquear até close pra simular EOF
        await self._closed.wait()
        return b""

    def close_eof(self) -> None:
        self._closed.set()


async def test_multiplexer_fans_out_to_subscribers() -> None:
    ops = _StubPtyOps([b"hello", b"world", b""])
    mux = PtyMultiplexer(ops, master_fd=7)
    q1 = await mux.subscribe()
    q2 = await mux.subscribe()
    c1 = await asyncio.wait_for(q1.get(), timeout=1.0)
    c2 = await asyncio.wait_for(q2.get(), timeout=1.0)
    assert c1 == c2 == b"hello"
    await mux.shutdown()


async def test_multiplexer_drops_slow_subscriber() -> None:
    """Queue full → subscriber é descartado, reader continua."""
    ops = _StubPtyOps([b"a"] * 2000 + [b""])
    mux = PtyMultiplexer(ops, master_fd=7)
    slow_q = await mux.subscribe()  # nunca lê dela
    fast_q = await mux.subscribe()

    chunks_read = 0
    for _ in range(50):
        try:
            await asyncio.wait_for(fast_q.get(), timeout=0.5)
            chunks_read += 1
        except TimeoutError:
            break
    assert chunks_read > 0
    # Slow_q foi removida do subscribers
    assert slow_q not in mux._subscribers  # type: ignore[attr-defined]
    await mux.shutdown()


async def test_multiplexer_shutdown_cancels_reader() -> None:
    ops = _StubPtyOps([])
    mux = PtyMultiplexer(ops, master_fd=7)
    await mux.shutdown()
    assert mux._reader_task.done()  # type: ignore[attr-defined]
