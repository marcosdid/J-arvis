"""F8.b: smoke real PTY via /bin/echo. Garante os.openpty() + subprocess wiring."""
import asyncio

from orchestrator.sandbox.pty_runtime import SubprocessPtyOps


async def test_subprocess_pty_ops_echo_roundtrip() -> None:
    """/bin/echo escreve no PTY; lemos via read()."""
    ops = SubprocessPtyOps()
    pid, fd = ops.spawn(["/bin/echo", "hello-pty"], cwd="/tmp")
    try:
        # echo escreve "hello-pty\n" e termina; pode precisar de multiplos reads
        chunks: list[bytes] = []
        for _ in range(5):
            try:
                chunk = await asyncio.wait_for(ops.read(fd), timeout=2.0)
            except TimeoutError:
                break
            if not chunk:
                break
            chunks.append(chunk)
        output = b"".join(chunks)
        assert b"hello-pty" in output
    finally:
        ops.kill(pid)
        ops.close(fd)
