"""F8.b: MasterSessionRuntime happy path + failures."""
from pathlib import Path
from typing import Any

import pytest

from orchestrator.sandbox.pty_runtime import MasterSessionRuntime


class FakePtyOps:
    """Captura calls + retorna pid/fd deterministicamente."""

    def __init__(self) -> None:
        self.spawns: list[tuple[list[str], str]] = []
        self.writes: list[bytes] = []
        self.killed: list[int] = []

    def spawn(self, cmd: list[str], cwd: str) -> tuple[int, int]:
        self.spawns.append((cmd, cwd))
        return (12345, 7)

    async def read(self, master_fd: int, n: int = 4096) -> bytes:
        return b""

    async def write(self, master_fd: int, data: bytes) -> None:
        self.writes.append(data)

    def resize(self, master_fd: int, rows: int, cols: int) -> None: pass
    def kill(self, pid: int) -> None: self.killed.append(pid)
    def close(self, master_fd: int) -> None: pass


async def test_spawn_generates_new_session_id_when_none(tmp_path: Path) -> None:
    runtime = MasterSessionRuntime(FakePtyOps())
    handle = await runtime.spawn(
        cwd=tmp_path, claude_session_id=None,
        mcp_url="http://localhost:8765/api/mcp", token="t",
    )
    assert handle.pid == 12345
    assert handle.master_fd == 7
    # UUID hex tem 32 chars
    assert len(handle.claude_session_id) == 32


async def test_spawn_reuses_session_id_when_provided(tmp_path: Path) -> None:
    runtime = MasterSessionRuntime(FakePtyOps())
    handle = await runtime.spawn(
        cwd=tmp_path, claude_session_id="reused-id-abc",
        mcp_url="http://localhost:8765/api/mcp", token="t",
    )
    assert handle.claude_session_id == "reused-id-abc"


async def test_spawn_writes_settings_and_aijail_config(tmp_path: Path) -> None:
    runtime = MasterSessionRuntime(FakePtyOps())
    await runtime.spawn(
        cwd=tmp_path, claude_session_id="sess1",
        mcp_url="http://localhost:8765/api/mcp", token="bearer-tok",
    )
    # settings.json gravado
    assert (tmp_path / ".claude" / "settings.json").exists()
    # .ai-jail gravado com --resume <sess1>
    aijail_text = (tmp_path / ".ai-jail").read_text()
    assert '"sess1"' in aijail_text


async def test_spawn_runs_ai_jail(tmp_path: Path) -> None:
    ops = FakePtyOps()
    runtime = MasterSessionRuntime(ops)
    await runtime.spawn(
        cwd=tmp_path, claude_session_id="x",
        mcp_url="http://localhost:8765/api/mcp", token="t",
    )
    # PTY spawnou ai-jail no cwd
    assert ops.spawns == [(["ai-jail"], str(tmp_path))]


async def test_spawn_propagates_pty_failure(tmp_path: Path) -> None:
    """Se PtyOps.spawn raise (ai-jail nao no PATH), runtime propaga."""
    class _FailingOps:
        def spawn(self, cmd: list[str], cwd: str) -> tuple[int, int]:
            raise FileNotFoundError("ai-jail not found")
        async def read(self, *a: Any, **kw: Any) -> bytes: return b""
        async def write(self, *a: Any, **kw: Any) -> None: pass
        def resize(self, *a: Any, **kw: Any) -> None: pass
        def kill(self, pid: int) -> None: pass
        def close(self, master_fd: int) -> None: pass

    runtime = MasterSessionRuntime(_FailingOps())
    with pytest.raises(FileNotFoundError):
        await runtime.spawn(
            cwd=tmp_path, claude_session_id=None,
            mcp_url="http://x/mcp", token="t",
        )
