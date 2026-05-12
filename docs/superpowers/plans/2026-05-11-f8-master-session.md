# F8 — Sessão master Claude no sidebar web (plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar uma sessão master Claude global persistente no sidebar do J-arvis (xterm.js + PTY backend) com tools MCP que manipulam o banco. Primeira fase pós-MVP.

**Architecture:** Daemon spawna 1 PTY global (`ai-jail` + `claude --dangerously-skip-permissions --resume <session-id>`) no lifespan; PtyMultiplexer faz fan-out pra N WebSockets (N tabs do browser); UI renderiza com xterm.js. Tools MCP rodam via Streamable HTTP + JSON-RPC 2.0 (SDK `mcp>=1.0`), expostos em `POST /api/mcp` com bearer auth. Persistência da conversa é delegada ao Claude CLI via `--resume` (jsonl em `~/.claude/projects/.../`).

**Tech Stack:** Python 3.13 + FastAPI + Pydantic v2 + SQLAlchemy 2 async + Alembic + `mcp>=1.0` (nova dep) + `os.openpty()`; React 19 + Vite 6 + TanStack Query + `@xterm/xterm` 5.5 + `@xterm/addon-fit` (novas deps); pytest (unit/integration/E2E Playwright host-only).

**Spec:** `docs/superpowers/specs/2026-05-11-f8-master-session-design.md`

---

## File structure

### Files to create (Python)

| Path | Responsibility |
|---|---|
| `alembic/versions/0006_master_session.py` | Migration: tabela `master_session` (singleton via CheckConstraint) |
| `orchestrator/sandbox/pty_runtime.py` | `PtyProcessOps` Protocol + `SubprocessPtyOps` impl + `MasterPtyHandle` + `MasterSessionRuntime` |
| `orchestrator/sandbox/master_settings_writer.py` | `write_master_settings` + `write_master_aijail_config` |
| `orchestrator/mcp/__init__.py` | namespace |
| `orchestrator/mcp/server.py` | MCP `Server` instance + `@list_tools` + `@call_tool` |
| `orchestrator/mcp/asgi_mount.py` | `build_mcp_app(server, state_provider, auth)` — wrapper ASGI com middleware de auth + injection |
| `orchestrator/api/master_ws.py` | `PtyMultiplexer` + `/ws/master` WebSocket bridge |
| `orchestrator/core/master_session.py` | `cleanup_orphan_master_at_startup` |
| `tests/unit/test_pty_ops.py` | `FakePtyOps` + tests do Protocol |
| `tests/unit/test_master_runtime.py` | spawn happy + failure + reuse session_id |
| `tests/unit/test_master_settings_writer.py` | settings.json + .ai-jail config válidos |
| `tests/unit/test_pty_multiplexer.py` | fan-out + overflow + shutdown |
| `tests/unit/test_master_mcp_dispatch.py` | call_tool dispatch routing |
| `tests/integration/test_pty_real_subprocess.py` | PTY smoke com `/bin/echo` |
| `tests/integration/test_api_mcp_read_tools.py` | tools/list + tools/call read-only |
| `tests/integration/test_api_mcp_write_tools.py` | create/update/discard via JSON-RPC |
| `tests/integration/test_api_master_ws.py` | WebSocket bridge + race protection |
| `tests/integration/test_master_session_persists.py` | restart reusa claude_session_id |
| `tests/integration/test_master_cleanup_orphan.py` | PID órfão morto no startup |
| `tests/integration/test_master_spawn_failure_degraded.py` | daemon sobe sem master |
| `tests/e2e/test_f8_master_creates_task.py` | E2E Playwright host-only |
| `docs/adr/0022-sessao-master-claude-no-sidebar-web.md` | ADR Nygard PT-BR |

### Files to create (UI)

| Path | Responsibility |
|---|---|
| `ui/src/components/MasterSidebar.tsx` | xterm.js + WebSocket client + `window.__masterTerm` expose |
| `ui/src/components/MasterSidebar.test.tsx` | unit tests com xterm mock |

### Files to modify

| Path | What |
|---|---|
| `pyproject.toml` | + `mcp>=1.0` dep |
| `orchestrator/store/models.py` | + `class MasterSession(Base)` |
| `orchestrator/main.py` | imports + lifespan spawn/shutdown + mount MCP + include master_ws router |
| `orchestrator/api/_deps.py` | + `resolve_master_handle`, `resolve_master_multiplexer` (graceful Nones) |
| `ui/package.json` | + `@xterm/xterm`, `@xterm/addon-fit` |
| `ui/src/index.css` | CSS pra `.master-sidebar` + `.master-term` |
| `ui/src/App.tsx` | embed `<MasterSidebar />` no layout (CSS grid: Kanban 1fr + sidebar 400px) |
| `ARCHITECTURE.md` | §11 F8 ✅ + §13 ADR-0022 |
| `docs/adr/README.md` | row pra ADR-0022 |

---

## Test fan-out

F8 adiciona kwargs novos a algumas funções core mas **não muda assinaturas existentes**. Não há migração de testes F1-F7 obrigatória. Toda nova funcionalidade vem via novos módulos.

Único ponto de atenção: `mcp_server.request_context.state` é variável global do SDK. Testes que chamam `call_tool` direto precisam de fixture que monta o context state (deps mockadas).

---

## Task F8.a — MasterSession model + migration + PtyProcessOps Protocol stub

**Files:**
- Create: `alembic/versions/0006_master_session.py`
- Modify: `orchestrator/store/models.py`
- Create: `orchestrator/sandbox/pty_runtime.py` (Protocol + dataclass apenas; impl em F8.b)
- Create: `tests/unit/test_pty_ops.py` (stub test do Protocol)

- [ ] **Step 1: Escrever migration**

Write `alembic/versions/0006_master_session.py`:

```python
"""master_session singleton

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-11
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "master_session",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("claude_session_id", sa.String(64), nullable=False),
        sa.Column("pid", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("last_active", sa.DateTime(), nullable=False),
        sa.CheckConstraint("id = 'singleton'", name="ck_master_singleton"),
    )


def downgrade() -> None:
    op.drop_table("master_session")
```

- [ ] **Step 2: Adicionar model**

Edit `orchestrator/store/models.py`. Adicionar (após o último modelo, antes do final do arquivo):

```python
class MasterSession(Base):
    """Singleton: só pode existir 1 row com id='singleton'."""
    __tablename__ = "master_session"

    id: Mapped[str] = mapped_column(String, primary_key=True, default="singleton")
    claude_session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_active: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (
        CheckConstraint("id = 'singleton'", name="ck_master_singleton"),
    )
```

Imports necessários (verificar se já existem): `from sqlalchemy import CheckConstraint, DateTime, Integer, String`.

- [ ] **Step 3: Criar PtyProcessOps Protocol + MasterPtyHandle**

Write `orchestrator/sandbox/pty_runtime.py`:

```python
"""F8: PTY runtime pra master session. Spawna ai-jail + claude num PTY pair."""
from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol


class PtyProcessOps(Protocol):
    """Abstração de PTY pair (fakeable em tests)."""

    def spawn(self, cmd: list[str], cwd: str) -> tuple[int, int]:
        """Spawn process em PTY, retorna (pid, master_fd)."""

    async def read(self, master_fd: int, n: int = 4096) -> bytes:
        """Read até `n` bytes do master_fd. Retorna b'' em EOF."""

    async def write(self, master_fd: int, data: bytes) -> None: ...

    def resize(self, master_fd: int, rows: int, cols: int) -> None: ...

    def kill(self, pid: int) -> None: ...

    def close(self, master_fd: int) -> None: ...


@dataclass(frozen=True)
class MasterPtyHandle:
    pid: int
    master_fd: int
    claude_session_id: str
    started_at: datetime
```

`MasterSessionRuntime` será adicionado em F8.b — apenas o Protocol + dataclass aqui.

- [ ] **Step 4: Stub test do Protocol**

`PtyProcessOps` precisa ser `@runtime_checkable` pra que `isinstance(impl, PtyProcessOps)` funcione nos tests. Edit em `orchestrator/sandbox/pty_runtime.py`:

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class PtyProcessOps(Protocol):
    ...
```

Write `tests/unit/test_pty_ops.py`:

```python
"""F8.a: stub tests garantem que Protocol + dataclass têm os métodos certos."""
from datetime import UTC, datetime
from typing import get_type_hints

from orchestrator.sandbox.pty_runtime import MasterPtyHandle, PtyProcessOps


def test_pty_process_ops_declares_required_methods() -> None:
    """Verifica que Protocol expõe a API esperada (spawn/read/write/resize/kill/close)."""
    required = {"spawn", "read", "write", "resize", "kill", "close"}
    actual = {name for name in dir(PtyProcessOps) if not name.startswith("_")}
    assert required.issubset(actual)


def test_master_pty_handle_constructs() -> None:
    h = MasterPtyHandle(
        pid=1234,
        master_fd=7,
        claude_session_id="abc123",
        started_at=datetime.now(UTC),
    )
    assert h.pid == 1234
    assert h.claude_session_id == "abc123"


def test_master_pty_handle_is_frozen() -> None:
    """Dataclass deve ser frozen pra imutabilidade."""
    import dataclasses
    h = MasterPtyHandle(
        pid=1, master_fd=2, claude_session_id="x", started_at=datetime.now(UTC),
    )
    with __import__("pytest").raises(dataclasses.FrozenInstanceError):
        h.pid = 999  # type: ignore[misc]
```

- [ ] **Step 5: Rodar migration localmente + smoke test do model**

```bash
cd /home/marcoslima/Documentos/projetos/J-arvs
uv run pytest tests/unit/test_pty_ops.py -v
```

Expected: 2/2 pass.

Migration smoke (opcional, validar sintaxe Alembic):

```bash
uv run alembic upgrade head --sql | tail -20
```

Expected: SQL de criação da tabela `master_session` aparece sem erro.

- [ ] **Step 6: Ruff clean**

```bash
uv run ruff check orchestrator/sandbox/pty_runtime.py orchestrator/store/models.py \
    alembic/versions/0006_master_session.py tests/unit/test_pty_ops.py
```

Expected: 0 findings.

- [ ] **Step 7: Commit**

```bash
git add alembic/versions/0006_master_session.py orchestrator/store/models.py \
        orchestrator/sandbox/pty_runtime.py tests/unit/test_pty_ops.py
git commit -m "feat(F8.a): MasterSession model + migration 0006 + PtyProcessOps Protocol"
```

---

## Task F8.b — MasterSessionRuntime + writers + SubprocessPtyOps + PTY smoke

**Files:**
- Modify: `orchestrator/sandbox/pty_runtime.py` (adicionar `MasterSessionRuntime`, `SubprocessPtyOps`)
- Create: `orchestrator/sandbox/master_settings_writer.py`
- Create: `tests/unit/test_master_runtime.py`
- Create: `tests/unit/test_master_settings_writer.py`
- Create: `tests/integration/test_pty_real_subprocess.py`

- [ ] **Step 1: Escrever testes unit (writers — TDD)**

Write `tests/unit/test_master_settings_writer.py`:

```python
"""F8.b: writers do master settings.json + .ai-jail config."""
import json
from pathlib import Path

from orchestrator.sandbox.master_settings_writer import (
    write_master_aijail_config,
    write_master_settings,
)


def test_write_master_settings_produces_mcp_config(tmp_path: Path) -> None:
    write_master_settings(
        tmp_path, mcp_url="http://localhost:8765/api/mcp", token="testtoken123",
    )
    settings_path = tmp_path / ".claude" / "settings.json"
    assert settings_path.exists()
    data = json.loads(settings_path.read_text())
    assert "mcpServers" in data
    assert data["mcpServers"]["j-arvis-master"]["type"] == "http"
    assert data["mcpServers"]["j-arvis-master"]["url"] == "http://localhost:8765/api/mcp"
    assert data["mcpServers"]["j-arvis-master"]["headers"]["Authorization"] == "Bearer testtoken123"


def test_write_master_settings_no_hooks(tmp_path: Path) -> None:
    """Master NÃO usa F2 hooks (decisão 9)."""
    write_master_settings(tmp_path, mcp_url="http://x/mcp", token="t")
    data = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    assert "hooks" not in data


def test_write_master_aijail_config_resumes_session(tmp_path: Path) -> None:
    write_master_aijail_config(tmp_path, claude_session_id="abc123", allow_port=8765)
    config_path = tmp_path / ".ai-jail"
    assert config_path.exists()
    text = config_path.read_text()
    assert '"--dangerously-skip-permissions"' in text
    assert '"--resume"' in text
    assert '"abc123"' in text
    assert "allow_tcp_ports = [8765]" in text
```

- [ ] **Step 2: Implementar `master_settings_writer.py`**

Write `orchestrator/sandbox/master_settings_writer.py`:

```python
"""F8.b: writers pra settings.json e .ai-jail config do master session."""
import json
from pathlib import Path


def write_master_settings(cwd: Path, *, mcp_url: str, token: str) -> None:
    """Escreve <cwd>/.claude/settings.json com MCP server config.

    Sem hooks F2 (decisão 9 da spec): master é global, não tem lifecycle
    per-task semantics.
    """
    claude_dir = cwd / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    settings = {
        "mcpServers": {
            "j-arvis-master": {
                "type": "http",
                "url": mcp_url,
                "headers": {"Authorization": f"Bearer {token}"},
            }
        }
    }
    (claude_dir / "settings.json").write_text(json.dumps(settings, indent=2))


def write_master_aijail_config(
    cwd: Path, *, claude_session_id: str, allow_port: int,
) -> None:
    """Escreve <cwd>/.ai-jail. Master usa --resume <session-id> e
    --dangerously-skip-permissions. allow_tcp_ports inclui a porta do daemon
    pra Claude conseguir falar com MCP server.
    """
    command_argv = ["claude", "--dangerously-skip-permissions", "--resume", claude_session_id]
    args_json = json.dumps(command_argv)
    (cwd / ".ai-jail").write_text(
        f"command = {args_json}\n"
        "rw_maps = []\n"
        "ro_maps = []\n"
        "hide_dotdirs = []\n"
        "mask = []\n"
        f"allow_tcp_ports = [{allow_port}]\n"
    )
```

- [ ] **Step 3: Tests writers pass**

```bash
uv run pytest tests/unit/test_master_settings_writer.py -v
```

Expected: 3/3 pass.

- [ ] **Step 4: Escrever testes do runtime (TDD)**

Write `tests/unit/test_master_runtime.py`:

```python
"""F8.b: MasterSessionRuntime happy path + failures."""
from collections import deque
from pathlib import Path
from typing import Any

import pytest

from orchestrator.sandbox.pty_runtime import MasterSessionRuntime, PtyProcessOps


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


@pytest.mark.unit
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


@pytest.mark.unit
async def test_spawn_reuses_session_id_when_provided(tmp_path: Path) -> None:
    runtime = MasterSessionRuntime(FakePtyOps())
    handle = await runtime.spawn(
        cwd=tmp_path, claude_session_id="reused-id-abc",
        mcp_url="http://localhost:8765/api/mcp", token="t",
    )
    assert handle.claude_session_id == "reused-id-abc"


@pytest.mark.unit
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


@pytest.mark.unit
async def test_spawn_runs_ai_jail(tmp_path: Path) -> None:
    ops = FakePtyOps()
    runtime = MasterSessionRuntime(ops)
    await runtime.spawn(
        cwd=tmp_path, claude_session_id="x",
        mcp_url="http://localhost:8765/api/mcp", token="t",
    )
    # PTY spawnou ai-jail no cwd
    assert ops.spawns == [(["ai-jail"], str(tmp_path))]


@pytest.mark.unit
async def test_spawn_propagates_pty_failure(tmp_path: Path) -> None:
    """Se PtyOps.spawn raise (ai-jail não no PATH), runtime propaga."""
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
```

- [ ] **Step 5: Implementar `MasterSessionRuntime` + `SubprocessPtyOps`**

Edit `orchestrator/sandbox/pty_runtime.py`. Adicionar ao final:

```python
import asyncio
import os
import signal
import subprocess
from datetime import UTC
from uuid import uuid4

from orchestrator.sandbox.master_settings_writer import (
    write_master_aijail_config,
    write_master_settings,
)


class MasterSessionRuntime:
    """Spawn ai-jail + claude num PTY (sem terminal emulator wrapper).

    Diferente de AiJailRuntime (F1+): saída vai pro master_fd que será
    bridged via WebSocket ao xterm.js no browser.
    """

    def __init__(self, pty_ops: PtyProcessOps) -> None:
        self._pty = pty_ops

    async def spawn(
        self,
        *,
        cwd: Path,
        claude_session_id: str | None,
        mcp_url: str,
        token: str,
    ) -> MasterPtyHandle:
        session_id = claude_session_id or uuid4().hex
        write_master_settings(cwd, mcp_url=mcp_url, token=token)
        # allow_port extraído do mcp_url (http://host:PORT/api/mcp)
        from urllib.parse import urlparse
        allow_port = urlparse(mcp_url).port or 8765
        write_master_aijail_config(cwd, claude_session_id=session_id, allow_port=allow_port)
        pid, fd = self._pty.spawn(["ai-jail"], str(cwd))
        return MasterPtyHandle(
            pid=pid, master_fd=fd,
            claude_session_id=session_id,
            started_at=datetime.now(UTC),
        )


class SubprocessPtyOps:  # pragma: no cover
    """Production PtyProcessOps: real os.openpty() + subprocess.

    Excluded from unit coverage (requires real OS pty + subprocess). Coberto
    por tests/integration/test_pty_real_subprocess.py.
    """

    def __init__(self) -> None:
        self._procs: dict[int, subprocess.Popen[bytes]] = {}

    def spawn(self, cmd: list[str], cwd: str) -> tuple[int, int]:
        master_fd, slave_fd = os.openpty()
        proc = subprocess.Popen(
            cmd, cwd=cwd,
            stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
            start_new_session=True,
        )
        os.close(slave_fd)  # parent só usa master_fd
        self._procs[master_fd] = proc
        return (proc.pid, master_fd)

    async def read(self, master_fd: int, n: int = 4096) -> bytes:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[bytes] = loop.create_future()

        def _on_readable() -> None:
            try:
                data = os.read(master_fd, n)
                if not future.done():
                    future.set_result(data)
            except OSError:
                if not future.done():
                    future.set_result(b"")
            finally:
                loop.remove_reader(master_fd)

        loop.add_reader(master_fd, _on_readable)
        return await future

    async def write(self, master_fd: int, data: bytes) -> None:
        # write é blocking mas pty buffer aceita 4KB sem block real
        os.write(master_fd, data)

    def resize(self, master_fd: int, rows: int, cols: int) -> None:
        import fcntl
        import struct
        import termios
        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)

    def kill(self, pid: int) -> None:
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except ProcessLookupError:
            pass

    def close(self, master_fd: int) -> None:
        try:
            os.close(master_fd)
        except OSError:
            pass
        proc = self._procs.pop(master_fd, None)
        if proc is not None:
            try:
                proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                proc.kill()
```

- [ ] **Step 6: Tests runtime pass**

```bash
uv run pytest tests/unit/test_master_runtime.py -v
```

Expected: 5/5 pass.

- [ ] **Step 7: Escrever PTY integration smoke**

Write `tests/integration/test_pty_real_subprocess.py`:

```python
"""F8.b: smoke real PTY via /bin/echo. Garante os.openpty() + subprocess wiring."""
import asyncio

import pytest

from orchestrator.sandbox.pty_runtime import SubprocessPtyOps


@pytest.mark.integration
async def test_subprocess_pty_ops_echo_roundtrip() -> None:
    """/bin/echo escreve no PTY; lemos via read()."""
    ops = SubprocessPtyOps()
    pid, fd = ops.spawn(["/bin/echo", "hello-pty"], cwd="/tmp")
    # echo escreve "hello-pty\n" e termina
    try:
        # Pode precisar de múltiplos reads pra capturar todo output
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
```

- [ ] **Step 8: Integration smoke pass**

```bash
uv run pytest tests/integration/test_pty_real_subprocess.py -v
```

Expected: 1/1 pass.

- [ ] **Step 9: Coverage + ruff**

```bash
uv run pytest tests/unit/test_master_runtime.py tests/unit/test_master_settings_writer.py \
    --cov=orchestrator/sandbox/pty_runtime --cov=orchestrator/sandbox/master_settings_writer \
    --cov-report=term-missing
uv run ruff check orchestrator/sandbox/pty_runtime.py orchestrator/sandbox/master_settings_writer.py \
    tests/unit/test_master_runtime.py tests/unit/test_master_settings_writer.py \
    tests/integration/test_pty_real_subprocess.py
```

Expected: 100% coverage no código novo (SubprocessPtyOps tem `# pragma: no cover`); ruff clean.

- [ ] **Step 10: Commit**

```bash
git add orchestrator/sandbox/pty_runtime.py orchestrator/sandbox/master_settings_writer.py \
        tests/unit/test_master_runtime.py tests/unit/test_master_settings_writer.py \
        tests/integration/test_pty_real_subprocess.py
git commit -m "feat(F8.b): MasterSessionRuntime + writers + SubprocessPtyOps + PTY smoke"
```

---

## Task F8.c — MCP server module + read-only tools + ASGI mount

**Files:**
- Modify: `pyproject.toml` + `uv.lock` (adicionar `mcp` dep)
- Modify: `orchestrator/core/projects.py` (adicionar `get_project` + `ProjectNotFoundError`)
- Create: `orchestrator/mcp/__init__.py`
- Create: `orchestrator/mcp/server.py`
- Create: `orchestrator/mcp/asgi_mount.py`
- Modify: `orchestrator/main.py` (mount MCP em `/api/mcp` + token)
- Create: `tests/unit/test_master_mcp_dispatch.py`
- Create: `tests/integration/test_api_mcp_read_tools.py`

- [ ] **Step 0: Spike MCP SDK API (PRÉ-REQUISITO)**

A spec do plan usa nomes especulativos (`StreamableHttpServerTransport`, `server.run_in_request_context`, `transport.handle_asgi`). Pin a API real ANTES de escrever código.

```bash
cd /home/marcoslima/Documentos/projetos/J-arvs
uv add mcp
```

Depois rode esses spike checks (use o que está disponível na sua sessão; se context7 não estiver acessível, leia direto do package):

```bash
uv run python -c "
import mcp.server
import mcp.server.streamable_http as sh
print('Server class:', dir(mcp.server.Server))
print('streamable_http exports:', dir(sh))
"
```

**Output esperado** (a confirmar):
- `Server` em `mcp.server` com métodos `list_tools()` e `call_tool()` decorators
- Algum tipo de `SessionManager` ou `Transport` em `mcp.server.streamable_http`
- Mecanismo de context state (`request_context`, `lifespan`, ou kwarg)

**Documente o resultado neste arquivo (F8.c Step 0)** antes de prosseguir. Se a API divergir significativamente do plano (ex: API requer `stateless=True`, ou usa `session_manager.handle_request` ao invés de `transport.handle_asgi`), reescreva o `asgi_mount.py` no Step 3 com a API correta.

**Se a SDK não estiver instalável (network issue, package yanked, etc.)**: escalar pra usuário. Não improvisar.

- [ ] **Step 1: Confirmar dep instalada**

`uv add mcp` no Step 0 já adicionou `mcp` ao `pyproject.toml` (range padrão `mcp>=X.Y,<Z.0`) e atualizou `uv.lock`. Verificar:

```bash
grep "mcp" pyproject.toml
uv pip list | grep mcp
```

Expected: `mcp` aparece em `pyproject.toml dependencies` + instalado.

- [ ] **Step 2: Criar namespace + Server**

Write `orchestrator/mcp/__init__.py`:

```python
"""F8: MCP server pra exposição de tools ao Claude master session."""
```

Write `orchestrator/mcp/server.py`:

```python
"""F8.c: MCP server com tools que manipulam o banco do J-arvis."""
from __future__ import annotations

import json
from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool

mcp_server: Server = Server("j-arvis-master")


@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="list_projects",
            description="List all projects with their ids, names, and paths.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_project",
            description="Get a project by id.",
            inputSchema={
                "type": "object",
                "required": ["project_id"],
                "properties": {"project_id": {"type": "string"}},
            },
        ),
        Tool(
            name="list_tasks",
            description="List tasks, optionally filtered by project and/or state.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "state": {
                        "type": "string",
                        "enum": [
                            "idea", "ready", "in_progress",
                            "review", "done", "discarded",
                        ],
                    },
                },
            },
        ),
        Tool(
            name="get_task",
            description="Get a task by id.",
            inputSchema={
                "type": "object",
                "required": ["task_id"],
                "properties": {"task_id": {"type": "string"}},
            },
        ),
    ]


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Dispatch JSON-RPC tool calls. Deps vêm de request_context.state."""
    from orchestrator.core.projects import get_project, list_projects
    from orchestrator.core.tasks import get_task, list_tasks

    ctx = mcp_server.request_context
    db = ctx.state["db"]

    if name == "list_projects":
        rows = await list_projects(db)
        return [TextContent(type="text", text=json.dumps([_serialize_project(r) for r in rows]))]
    if name == "get_project":
        row = await get_project(db, arguments["project_id"])
        return [TextContent(type="text", text=json.dumps(_serialize_project(row)))]
    if name == "list_tasks":
        rows = await list_tasks(
            db,
            project_ids=[arguments["project_id"]] if "project_id" in arguments else None,
        )
        if "state" in arguments:
            rows = [r for r in rows if r.state == arguments["state"]]
        return [TextContent(type="text", text=json.dumps([_serialize_task(r) for r in rows]))]
    if name == "get_task":
        row = await get_task(db, arguments["task_id"])
        return [TextContent(type="text", text=json.dumps(_serialize_task(row)))]
    raise ValueError(f"unknown tool {name!r}")


def _serialize_project(p: Any) -> dict[str, Any]:
    return {"id": p.id, "name": p.name, "path": p.path}


def _serialize_task(t: Any) -> dict[str, Any]:
    return {
        "id": t.id, "project_id": t.project_id, "title": t.title,
        "description": t.description, "state": t.state, "branch": t.branch,
        "template": t.template, "permission_profile": t.permission_profile,
    }
```

`list_projects`/`list_tasks` em `core/projects.py` e `core/tasks.py` já existem (F1-F7). `get_project` **NÃO** existe — precisa ser criado. Vai como passo explícito a seguir.

- [ ] **Step 2b: Criar `get_project` em `core/projects.py`**

Edit `orchestrator/core/projects.py`. Verificar se `ProjectNotFoundError` já existe (search:`class ProjectNotFoundError`). Se não existir, adicionar perto das outras `*Error` no topo:

```python
class ProjectNotFoundError(Exception):
    def __init__(self, project_id: str) -> None:
        super().__init__(f"project {project_id!r} not found")
        self.project_id = project_id
```

Adicionar a função helper (após `list_projects`):

```python
async def get_project(db: AsyncSession, project_id: str) -> Project:
    proj = await db.get(Project, project_id)
    if proj is None:
        raise ProjectNotFoundError(project_id)
    return proj
```

Smoke test (criar `tests/unit/test_projects_get_project.py` mínimo):

```python
"""F8.c: get_project helper."""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.core.projects import (
    ProjectNotFoundError,
    get_project,
)
from orchestrator.store.models import Project


async def test_get_project_returns_existing(db_session: AsyncSession) -> None:
    db_session.add(Project(id="p1", name="p", path="/tmp/p"))
    await db_session.commit()
    p = await get_project(db_session, "p1")
    assert p.name == "p"


async def test_get_project_missing_raises(db_session: AsyncSession) -> None:
    with pytest.raises(ProjectNotFoundError):
        await get_project(db_session, "ghost")
```

Run:

```bash
uv run pytest tests/unit/test_projects_get_project.py -v
```

Expected: 2/2 pass.

- [ ] **Step 3: Criar ASGI mount wrapper**

Write `orchestrator/mcp/asgi_mount.py`:

```python
"""F8.c: wrapper ASGI pro MCP server.

Embrulha o StreamableHttpServerTransport com:
- Middleware de auth (Bearer token)
- Injection de deps no mcp_server.request_context.state
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import HTTPException, Request
from mcp.server import Server
from mcp.server.streamable_http import StreamableHttpServerTransport


def build_mcp_app(
    server: Server,
    state_provider: Callable[[Request], dict[str, Any]],
    auth: Callable[[Request], Awaitable[None]],
) -> Any:
    """Returns ASGI app que monta o MCP server com auth + state injection."""
    transport = StreamableHttpServerTransport()

    async def app(scope: dict[str, Any], receive: Callable, send: Callable) -> None:
        if scope["type"] != "http":
            await send({"type": "http.response.start", "status": 400, "headers": []})
            await send({"type": "http.response.body", "body": b"http only"})
            return

        # Constrói Request pra usar middleware fastapi-style
        request = Request(scope, receive=receive)

        # Auth
        try:
            await auth(request)
        except HTTPException as exc:
            await send({
                "type": "http.response.start",
                "status": exc.status_code,
                "headers": [(b"content-type", b"application/json")],
            })
            await send({
                "type": "http.response.body",
                "body": f'{{"error":"{exc.detail}"}}'.encode(),
            })
            return

        # Inject state no request_context do server
        state = state_provider(request)
        # SDK MCP expõe request_context via contextvar — set state pre-dispatch
        async with server.run_in_request_context(state=state):
            await transport.handle_asgi(scope, receive, send, server)

    return app
```

Nota: a API exata do `mcp` SDK pra request_context state injection pode variar — implementador deve verificar `mcp` SDK docs no momento de F8.c. Se o método correto for diferente, ajustar o wrapper. O contrato funcional permanece: cada request injeta `state` que `call_tool` lê via `ctx.state`.

- [ ] **Step 4: Modificar main.py — mount MCP**

Edit `orchestrator/main.py`:

1. Adicionar imports (alongside outros `orchestrator.*`):

```python
import secrets

from fastapi import HTTPException

from orchestrator.mcp.asgi_mount import build_mcp_app
from orchestrator.mcp.server import mcp_server
```

2. Em `create_app`, **depois** dos `app.state.*` assignments e **antes** dos `include_router` calls, adicionar:

```python
    # F8: MCP server (master session tools)
    app.state.master_mcp_token = getattr(
        app.state, "master_mcp_token", None,
    ) or secrets.token_urlsafe(32)

    async def _verify_mcp_auth(request: Request) -> None:
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(401, "missing bearer token")
        if auth_header[7:] != request.app.state.master_mcp_token:
            raise HTTPException(401, "invalid MCP token")

    def _state_provider(req: Request) -> dict[str, object]:
        return {
            "db": req.app.state.database,
            "catalog": req.app.state.catalog,
            "broadcaster": req.app.state.ws_broadcaster,
            "git_ops": req.app.state.git_ops,
        }

    mcp_asgi = build_mcp_app(
        server=mcp_server,
        state_provider=_state_provider,
        auth=_verify_mcp_auth,
    )
    app.mount("/api/mcp", mcp_asgi)
```

- [ ] **Step 5: Escrever unit test do dispatch**

Write `tests/unit/test_master_mcp_dispatch.py`:

```python
"""F8.c: dispatch routing do call_tool com state injection mockado."""
import json
from contextlib import contextmanager
from typing import Any

import pytest

from orchestrator.mcp.server import call_tool, list_tools


class _FakeDb:
    pass


@pytest.mark.unit
async def test_list_tools_returns_4_read_only_tools() -> None:
    tools = await list_tools()
    names = [t.name for t in tools]
    assert set(names) == {"list_projects", "get_project", "list_tasks", "get_task"}


@pytest.mark.unit
async def test_call_tool_unknown_raises() -> None:
    # Mockar request_context.state — depende da API real do SDK mcp
    # Se SDK não permitir mock direto, usar monkeypatch em mcp_server.request_context
    import orchestrator.mcp.server as mod

    class _FakeCtx:
        state = {"db": _FakeDb()}

    mod.mcp_server.request_context = _FakeCtx()  # type: ignore[assignment]
    with pytest.raises(ValueError, match="unknown tool"):
        await call_tool("definitely_not_a_tool", {})
```

Nota: a maneira de mockar `request_context` depende da API exata do SDK. Implementador ajusta no F8.c se necessário. O importante é cobrir: lista de tools correta + dispatch de unknown raise.

- [ ] **Step 6: Tests unit pass**

```bash
uv run pytest tests/unit/test_master_mcp_dispatch.py -v
```

Expected: 2/2 pass.

- [ ] **Step 7: Escrever integration test (read-only tools)**

Write `tests/integration/test_api_mcp_read_tools.py`:

```python
"""F8.c: GET /api/mcp via JSON-RPC tools/list e tools/call (read-only)."""
import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.main import create_app
from orchestrator.store.database import Database
from tests.integration.conftest import FakeSessionRuntime


_MCP_HEADERS_BASE = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "MCP-Protocol-Version": "2025-11-25",
}


def _headers(token: str) -> dict[str, str]:
    return {**_MCP_HEADERS_BASE, "Authorization": f"Bearer {token}"}


@pytest.mark.integration
async def test_tools_list_returns_read_tools(
    db: Database, runtime: FakeSessionRuntime,
) -> None:
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    token = app.state.master_mcp_token
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(
            "/api/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            headers=_headers(token),
        )
    assert r.status_code == 200
    body = r.json()
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "list_projects" in tool_names
    assert "get_task" in tool_names


@pytest.mark.integration
async def test_tools_call_list_projects_empty(
    db: Database, runtime: FakeSessionRuntime,
) -> None:
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    token = app.state.master_mcp_token
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(
            "/api/mcp",
            json={
                "jsonrpc": "2.0", "id": 1,
                "method": "tools/call",
                "params": {"name": "list_projects", "arguments": {}},
            },
            headers=_headers(token),
        )
    assert r.status_code == 200
    body = r.json()
    content = body["result"]["content"]
    import json as _json
    parsed = _json.loads(content[0]["text"])
    assert parsed == []  # nenhum projeto criado


@pytest.mark.integration
async def test_tools_call_missing_auth_401(
    db: Database, runtime: FakeSessionRuntime,
) -> None:
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(
            "/api/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            headers=_MCP_HEADERS_BASE,  # sem Authorization
        )
    assert r.status_code == 401


@pytest.mark.integration
async def test_tools_call_invalid_token_401(
    db: Database, runtime: FakeSessionRuntime,
) -> None:
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(
            "/api/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            headers=_headers("wrong-token"),
        )
    assert r.status_code == 401
```

- [ ] **Step 8: Integration tests pass**

```bash
uv run pytest tests/integration/test_api_mcp_read_tools.py -v
```

Expected: 4/4 pass.

Se algum teste falhar com erro de protocolo MCP (ex: handshake `initialize` required), ajustar adicionando passo de inicialização. SDK MCP pode exigir `initialize` antes de `tools/list`/`tools/call`.

- [ ] **Step 9: Suite completa não regrediu**

```bash
uv run pytest tests/unit tests/integration --no-header 2>&1 | tail -10
```

Expected: green; F0-F7 + F8.a + F8.b + F8.c novos passing.

- [ ] **Step 10: Coverage + ruff**

```bash
uv run pytest tests/unit/test_master_mcp_dispatch.py tests/integration/test_api_mcp_read_tools.py \
    --cov=orchestrator/mcp --cov-report=term-missing
uv run ruff check orchestrator/mcp/ tests/unit/test_master_mcp_dispatch.py \
    tests/integration/test_api_mcp_read_tools.py orchestrator/main.py
```

Expected: 100% coverage no `orchestrator/mcp/`; ruff clean.

- [ ] **Step 11: Commit**

```bash
git add pyproject.toml uv.lock orchestrator/mcp/ orchestrator/main.py \
        orchestrator/core/projects.py \
        tests/unit/test_master_mcp_dispatch.py tests/integration/test_api_mcp_read_tools.py
git commit -m "feat(F8.c): MCP server + read-only tools + ASGI mount em /api/mcp"
```

---

## Task F8.d — MCP write tools (create/update/discard) + WS broadcast

**Files:**
- Modify: `orchestrator/mcp/server.py` (adicionar write tools)
- Create: `tests/integration/test_api_mcp_write_tools.py`

- [ ] **Step 1: Adicionar write tools ao schema list_tools**

Edit `orchestrator/mcp/server.py`. Estender o `return` de `list_tools` com:

```python
        Tool(
            name="create_task",
            description="Create a new task. Optionally with a template (frontend/backend/refactor/bugfix) which auto-derives permission_profile and branch prefix.",
            inputSchema={
                "type": "object",
                "required": ["project_id", "title"],
                "properties": {
                    "project_id": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "template": {
                        "type": "string",
                        "enum": ["frontend", "backend", "refactor", "bugfix"],
                    },
                    "branch": {"type": "string"},
                },
            },
        ),
        Tool(
            name="update_task",
            description="Update task fields. State transitions follow F4 state machine. NOTE: template é snapshot-at-create (F7) — não editável aqui.",
            inputSchema={
                "type": "object",
                "required": ["task_id"],
                "properties": {
                    "task_id": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "state": {"type": "string"},
                    "branch": {"type": "string"},
                    # template intencionalmente ausente: F7 decisão de snapshot-at-create
                },
            },
        ),
        Tool(
            name="discard_task",
            description="Move task to discarded state.",
            inputSchema={
                "type": "object",
                "required": ["task_id"],
                "properties": {"task_id": {"type": "string"}},
            },
        ),
```

- [ ] **Step 2: Adicionar handlers do call_tool**

Edit `orchestrator/mcp/server.py`. Adicionar imports:

```python
from orchestrator.core.tasks import (
    InvalidTemplateError, create_task, update_task,
)
from orchestrator.events.envelope import WsEvent
```

Estender `call_tool` com branches:

```python
    if name == "create_task":
        catalog = ctx.state["catalog"]
        broadcaster = ctx.state["broadcaster"]
        try:
            task = await create_task(db, catalog=catalog, **arguments)
        except InvalidTemplateError as exc:
            raise ValueError(
                f"template_not_in_catalog: valid={exc.valid_templates}"
            ) from exc
        if broadcaster is not None:
            await broadcaster.publish(WsEvent.task_created(
                task_id=task.id, project_id=task.project_id,
                title=task.title, state=task.state,
            ))
        return [TextContent(type="text", text=json.dumps(_serialize_task(task)))]

    if name == "update_task":
        broadcaster = ctx.state["broadcaster"]
        task_id = arguments.pop("task_id")
        # update_task em core/tasks.py NÃO aceita `catalog` nem `template`.
        # Assinatura confirmada: (db, task_id, *, title?, description?, state?, branch?)
        task, prev_state = await update_task(db, task_id, **arguments)
        if broadcaster is not None:
            await broadcaster.publish(WsEvent.task_updated(
                task_id=task.id, project_id=task.project_id,
                title=task.title, new_state=task.state,
                previous_state=prev_state or task.state,
            ))
        return [TextContent(type="text", text=json.dumps(_serialize_task(task)))]

    if name == "discard_task":
        broadcaster = ctx.state["broadcaster"]
        task, prev_state = await update_task(db, arguments["task_id"], state="discarded")
        if broadcaster is not None:
            await broadcaster.publish(WsEvent.task_updated(
                task_id=task.id, project_id=task.project_id,
                title=task.title, new_state=task.state,
                previous_state=prev_state or task.state,
            ))
        return [TextContent(type="text", text=json.dumps(_serialize_task(task)))]
```

**Confirmado:** `update_task` em `core/tasks.py` retorna `tuple[Task, str | None]` (task + previous_state). Aceita apenas: `title`, `description`, `state`, `branch`. NÃO aceita `template` nem `catalog` (decisão F7: template é snapshot-at-create). Schema do tool exclui esses dois fields.

- [ ] **Step 3: Escrever integration tests**

Write `tests/integration/test_api_mcp_write_tools.py`:

```python
"""F8.d: create/update/discard_task via JSON-RPC."""
import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.main import create_app
from orchestrator.store.database import Database
from tests.integration.conftest import FakeSessionRuntime, _make_repo


_MCP_HEADERS_BASE = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "MCP-Protocol-Version": "2025-11-25",
}


def _headers(token: str) -> dict[str, str]:
    return {**_MCP_HEADERS_BASE, "Authorization": f"Bearer {token}"}


async def _call_tool(c: AsyncClient, headers: dict, name: str, args: dict) -> dict:
    r = await c.post(
        "/api/mcp",
        json={
            "jsonrpc": "2.0", "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": args},
        },
        headers=headers,
    )
    return r.json()


@pytest.mark.integration
async def test_create_task_via_mcp_basic(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    token = app.state.master_mcp_token
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        proj = (await c.post(
            "/api/projects",
            json={"name": "p", "path": str(repo)},
        )).json()
        result = await _call_tool(c, _headers(token), "create_task", {
            "project_id": proj["id"], "title": "from MCP",
        })
    parsed = json.loads(result["result"]["content"][0]["text"])
    assert parsed["title"] == "from MCP"
    assert parsed["project_id"] == proj["id"]


@pytest.mark.integration
async def test_create_task_with_template(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    token = app.state.master_mcp_token
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        proj = (await c.post(
            "/api/projects", json={"name": "p", "path": str(repo)},
        )).json()
        result = await _call_tool(c, _headers(token), "create_task", {
            "project_id": proj["id"],
            "title": "Add dark mode",
            "template": "frontend",
        })
    parsed = json.loads(result["result"]["content"][0]["text"])
    assert parsed["template"] == "frontend"
    assert parsed["permission_profile"] == "yolo"
    # Branch usa prefix do template + slug do title. Weak assert pra
    # tolerar variações no slugify_for_branch entre versões.
    assert parsed["branch"].startswith("feat-ui/")
    assert "dark" in parsed["branch"] and "mode" in parsed["branch"]


@pytest.mark.integration
async def test_create_task_invalid_template_jsonrpc_error(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    token = app.state.master_mcp_token
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        proj = (await c.post(
            "/api/projects", json={"name": "p", "path": str(repo)},
        )).json()
        result = await _call_tool(c, _headers(token), "create_task", {
            "project_id": proj["id"], "title": "t", "template": "ghost",
        })
    # JSON-RPC error response shape
    assert "error" in result or "isError" in result.get("result", {})


@pytest.mark.integration
async def test_update_task_state(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    token = app.state.master_mcp_token
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        proj = (await c.post(
            "/api/projects", json={"name": "p", "path": str(repo)},
        )).json()
        task = (await c.post(
            "/api/tasks", json={"project_id": proj["id"], "title": "t"},
        )).json()
        result = await _call_tool(c, _headers(token), "update_task", {
            "task_id": task["id"], "state": "ready",
        })
    parsed = json.loads(result["result"]["content"][0]["text"])
    assert parsed["state"] == "ready"


@pytest.mark.integration
async def test_discard_task(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    token = app.state.master_mcp_token
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        proj = (await c.post(
            "/api/projects", json={"name": "p", "path": str(repo)},
        )).json()
        task = (await c.post(
            "/api/tasks", json={"project_id": proj["id"], "title": "t"},
        )).json()
        result = await _call_tool(c, _headers(token), "discard_task", {
            "task_id": task["id"],
        })
    parsed = json.loads(result["result"]["content"][0]["text"])
    assert parsed["state"] == "discarded"
```

- [ ] **Step 4: Tests pass**

```bash
uv run pytest tests/integration/test_api_mcp_write_tools.py -v
```

Expected: 5/5 pass.

Se `update_task` ou state transitions falharem por causa do state machine (idea→ready é direto; idea→done não é), ajustar testes pra usar transitions válidas.

- [ ] **Step 5: Suite + coverage + ruff**

```bash
uv run pytest tests/unit tests/integration --no-header 2>&1 | tail -10
uv run pytest tests/integration/test_api_mcp_write_tools.py \
    --cov=orchestrator/mcp/server --cov-report=term-missing
uv run ruff check orchestrator/mcp/server.py tests/integration/test_api_mcp_write_tools.py
```

Expected: suite verde; cobertura 100% novo código; ruff clean.

- [ ] **Step 6: Commit**

```bash
git add orchestrator/mcp/server.py tests/integration/test_api_mcp_write_tools.py
git commit -m "feat(F8.d): MCP write tools (create/update/discard) + WS broadcast pra Kanban"
```

---

## Task F8.e — WebSocket `/ws/master` + PtyMultiplexer + lifespan + cleanup_orphan

**Files:**
- Create: `orchestrator/api/master_ws.py`
- Create: `orchestrator/core/master_session.py`
- Modify: `orchestrator/main.py` (lifespan spawn + shutdown + include_router)
- Create: `tests/unit/test_pty_multiplexer.py`
- Create: `tests/integration/test_api_master_ws.py`
- Create: `tests/integration/test_master_session_persists.py`
- Create: `tests/integration/test_master_cleanup_orphan.py`
- Create: `tests/integration/test_master_spawn_failure_degraded.py`

- [ ] **Step 1: Escrever testes do PtyMultiplexer (TDD)**

Write `tests/unit/test_pty_multiplexer.py`:

```python
"""F8.e: PtyMultiplexer fan-out + overflow + shutdown."""
import asyncio
from collections import deque

import pytest

from orchestrator.api.master_ws import PtyMultiplexer


class _StubPtyOps:
    """Fake que retorna chunks de uma deque via read()."""

    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = deque(chunks)
        self._closed = asyncio.Event()

    async def read(self, master_fd: int, n: int = 4096) -> bytes:
        if self._chunks:
            chunk = self._chunks.popleft()
            return chunk
        # Bloquear até close pra simular EOF
        await self._closed.wait()
        return b""

    def close_eof(self) -> None:
        self._closed.set()


@pytest.mark.unit
async def test_multiplexer_fans_out_to_subscribers() -> None:
    ops = _StubPtyOps([b"hello", b"world", b""])
    mux = PtyMultiplexer(ops, master_fd=7)
    q1 = await mux.subscribe()
    q2 = await mux.subscribe()
    # Lê dos 2 queues
    c1 = await asyncio.wait_for(q1.get(), timeout=1.0)
    c2 = await asyncio.wait_for(q2.get(), timeout=1.0)
    assert c1 == c2 == b"hello"
    await mux.shutdown()


@pytest.mark.unit
async def test_multiplexer_drops_slow_subscriber() -> None:
    """Queue full → subscriber é descartado, reader continua."""
    ops = _StubPtyOps([b"a"] * 2000 + [b""])
    mux = PtyMultiplexer(ops, master_fd=7)
    slow_q = await mux.subscribe()  # nunca lê dela
    fast_q = await mux.subscribe()

    # Lê só do fast — slow vai encher e ser descartado
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


@pytest.mark.unit
async def test_multiplexer_shutdown_cancels_reader() -> None:
    ops = _StubPtyOps([])
    mux = PtyMultiplexer(ops, master_fd=7)
    await mux.shutdown()
    assert mux._reader_task.done()  # type: ignore[attr-defined]
```

- [ ] **Step 2: Implementar PtyMultiplexer + WebSocket endpoint**

Write `orchestrator/api/master_ws.py`:

```python
"""F8.e: WebSocket bridge entre browser e PTY do master session.

PtyMultiplexer: single reader on master_fd, fan-out pra N queues (cada
queue serve uma WebSocket connection / browser tab).
"""
from __future__ import annotations

import asyncio
import contextlib
import logging

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect

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
        self._reader_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._reader_task


router = APIRouter()


@router.websocket("/ws/master")
async def master_ws(websocket: WebSocket) -> None:
    """Bridge bidirectional entre browser e PTY do master session.

    Múltiplas tabs do browser fazem multiplex no MESMO PTY (decisão 7).
    """
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
            elif msg["type"] == "resize":
                pty_ops.resize(handle.master_fd, msg["rows"], msg["cols"])

    async def pty_to_browser() -> None:
        while True:
            chunk = await queue.get()
            await websocket.send_json({
                "type": "output",
                "data": chunk.decode("utf-8", errors="replace"),
            })

    try:
        await asyncio.gather(browser_to_pty(), pty_to_browser())
    except WebSocketDisconnect:
        pass
    finally:
        mux.unsubscribe(queue)
```

- [ ] **Step 3: Tests do multiplexer pass**

```bash
uv run pytest tests/unit/test_pty_multiplexer.py -v
```

Expected: 3/3 pass.

- [ ] **Step 4: Criar cleanup_orphan_master**

Write `orchestrator/core/master_session.py`:

```python
"""F8.e: cleanup de master session órfã no startup."""
import os
import signal

from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.store.models import MasterSession


async def cleanup_orphan_master_at_startup(s: AsyncSession) -> None:
    """Se daemon caiu sem matar PTY, tenta SIGKILL do PID antigo."""
    master = await s.get(MasterSession, "singleton")
    if master and master.pid is not None:
        try:
            os.killpg(os.getpgid(master.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass  # já morreu
        master.pid = None
        await s.commit()
```

- [ ] **Step 5: Modificar main.py — lifespan integration**

Edit `orchestrator/main.py`. Adicionar imports:

```python
import asyncio
import logging
from datetime import UTC, datetime

from orchestrator.api.master_ws import PtyMultiplexer
from orchestrator.api.master_ws import router as master_ws_router
from orchestrator.core.master_session import cleanup_orphan_master_at_startup
from orchestrator.sandbox.pty_runtime import (
    MasterSessionRuntime,
    SubprocessPtyOps,
)
from orchestrator.store.models import MasterSession

logger = logging.getLogger(__name__)
```

No `lifespan`, substituir/estender:

```python
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if database is not None:
            await database.bootstrap()
            async with database.session() as s:
                await cleanup_orphan_runs_at_startup(
                    s, _app.state.docker_ops, _app.state.port_allocator,
                )
                await cleanup_orphan_master_at_startup(s)

            # F8: spawn master session
            async with database.session() as s:
                master = await s.get(MasterSession, "singleton")
                session_id_to_resume = master.claude_session_id if master else None

            pty_ops = SubprocessPtyOps()
            master_runtime = MasterSessionRuntime(pty_ops)
            master_cwd = Path.home() / ".local" / "share" / "j-arvis" / "master"
            master_cwd.mkdir(parents=True, exist_ok=True)
            port = 8765  # TODO: source from Settings
            # Inicializa state SEMPRE — independente de spawn ter sucesso ou não.
            # /ws/master handler usa estes attrs; sem init eles raise AttributeError
            # quando handle/multiplexer == None (estado degradado).
            _app.state.master_pty_ops = pty_ops
            _app.state.master_write_lock = asyncio.Lock()
            _app.state.master_handle = None
            _app.state.master_multiplexer = None

            try:
                handle = await master_runtime.spawn(
                    cwd=master_cwd,
                    claude_session_id=session_id_to_resume,
                    mcp_url=f"http://localhost:{port}/api/mcp",
                    token=_app.state.master_mcp_token,
                )
            except (FileNotFoundError, OSError) as exc:
                logger.error("master session spawn failed: %s", exc)
                _app.state.master_handle = None
                _app.state.master_multiplexer = None
            else:
                _app.state.master_handle = handle
                _app.state.master_multiplexer = PtyMultiplexer(pty_ops, handle.master_fd)
                async with database.session() as s:
                    await s.merge(MasterSession(
                        id="singleton",
                        claude_session_id=handle.claude_session_id,
                        pid=handle.pid,
                        started_at=handle.started_at,
                        last_active=datetime.now(UTC),
                    ))
                    await s.commit()

                # Watchdog: se `claude --resume <id>` falha (jsonl corrompido),
                # PTY morre em <1s. Detecta via task background que monitora
                # se proc ainda vive 2s após spawn. Se morto, re-spawn com
                # session_id=None (nova session) + broadcast system warning.
                async def _resume_watchdog() -> None:
                    await asyncio.sleep(2.0)
                    try:
                        os.kill(handle.pid, 0)  # signal 0 = check alive
                    except ProcessLookupError:
                        # PTY morreu — possible --resume failure
                        logger.warning(
                            "master PTY died <2s after spawn; --resume may have failed. "
                            "Re-spawning fresh."
                        )
                        # Broadcast system message via multiplexer pseudo-event
                        # (subscribers ainda não conectaram; mensagem fica perdida.
                        # Mitigação: novo spawn vira a fonte de verdade)
                        try:
                            new_handle = await master_runtime.spawn(
                                cwd=master_cwd,
                                claude_session_id=None,  # nova session
                                mcp_url=f"http://localhost:{port}/api/mcp",
                                token=_app.state.master_mcp_token,
                            )
                        except (FileNotFoundError, OSError) as exc:
                            logger.error("re-spawn failed: %s", exc)
                            return
                        _app.state.master_handle = new_handle
                        await _app.state.master_multiplexer.shutdown()
                        _app.state.master_multiplexer = PtyMultiplexer(
                            pty_ops, new_handle.master_fd,
                        )
                        async with database.session() as s:
                            await s.merge(MasterSession(
                                id="singleton",
                                claude_session_id=new_handle.claude_session_id,
                                pid=new_handle.pid,
                                started_at=new_handle.started_at,
                                last_active=datetime.now(UTC),
                            ))
                            await s.commit()

                # Dispara watchdog (não awaitamos — fica em background)
                _app.state._master_watchdog = asyncio.create_task(_resume_watchdog())

        yield

        # Shutdown
        if getattr(_app.state, "master_multiplexer", None):
            await _app.state.master_multiplexer.shutdown()
        if getattr(_app.state, "master_handle", None):
            try:
                _app.state.master_pty_ops.kill(_app.state.master_handle.pid)
            except ProcessLookupError:
                pass
            if database is not None:
                async with database.session() as s:
                    master = await s.get(MasterSession, "singleton")
                    if master:
                        master.pid = None
                        await s.commit()
```

E adicionar `app.include_router(master_ws_router)` na lista de routers (sem prefix, igual ao `ws_router` existente).

- [ ] **Step 6: Escrever integration tests**

Write `tests/integration/test_api_master_ws.py`:

```python
"""F8.e: WebSocket /ws/master + race protection."""
import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.main import create_app
from orchestrator.store.database import Database
from tests.integration.conftest import FakeSessionRuntime


@pytest.mark.integration
async def test_ws_master_not_ready_closes_1011(
    db: Database, runtime: FakeSessionRuntime,
) -> None:
    """master_handle=None (spawn failure) → WS connect retorna system error + close 1011.

    Força spawn failure via patch pra ter teste determinístico.
    """
    from unittest.mock import patch

    from fastapi.testclient import TestClient

    with patch(
        "orchestrator.sandbox.pty_runtime.MasterSessionRuntime.spawn",
        side_effect=FileNotFoundError("forced"),
    ):
        app = create_app(database=db, runtime=runtime, ui_dist=None)
        with TestClient(app) as client:
            # lifespan rodou, spawn falhou, app.state.master_handle = None
            assert app.state.master_handle is None
            with client.websocket_connect("/ws/master") as ws:
                msg = ws.receive_json()
                assert msg["type"] == "system"
                assert msg["level"] == "error"
                assert "not available" in msg["message"].lower()
                # Close imediato depois da system message
                with pytest.raises(Exception):  # WebSocketDisconnect ou similar
                    ws.receive_json(timeout=1.0)
```

Write `tests/integration/test_master_session_persists.py`:

```python
"""F8.e: restart simulado preserva claude_session_id."""
from datetime import UTC, datetime

import pytest

from orchestrator.store.database import Database
from orchestrator.store.models import MasterSession


@pytest.mark.integration
async def test_master_session_id_persists_across_simulated_restart(
    db: Database,
) -> None:
    """Boot 1: persist sess-id. Boot 2: read e reusa."""
    async with db.session() as s:
        s.add(MasterSession(
            id="singleton",
            claude_session_id="boot1-session-uuid",
            pid=12345,
            started_at=datetime.now(UTC),
            last_active=datetime.now(UTC),
        ))
        await s.commit()

    # Simula boot 2: read
    async with db.session() as s:
        master = await s.get(MasterSession, "singleton")
        assert master is not None
        assert master.claude_session_id == "boot1-session-uuid"
```

Write `tests/integration/test_master_cleanup_orphan.py`:

```python
"""F8.e: cleanup_orphan_master_at_startup mata PID antigo."""
import os
import signal
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from orchestrator.core.master_session import cleanup_orphan_master_at_startup
from orchestrator.store.database import Database
from orchestrator.store.models import MasterSession


@pytest.mark.integration
async def test_cleanup_kills_orphan_pid(db: Database) -> None:
    async with db.session() as s:
        s.add(MasterSession(
            id="singleton", claude_session_id="x", pid=99999,
            started_at=datetime.now(UTC), last_active=datetime.now(UTC),
        ))
        await s.commit()

    # Mock killpg pra observar o call sem matar processos reais
    with patch("orchestrator.core.master_session.os.killpg") as mock_kill, \
         patch("orchestrator.core.master_session.os.getpgid", return_value=99999):
        async with db.session() as s:
            await cleanup_orphan_master_at_startup(s)
        mock_kill.assert_called_with(99999, signal.SIGKILL)

    async with db.session() as s:
        master = await s.get(MasterSession, "singleton")
        assert master.pid is None


@pytest.mark.integration
async def test_cleanup_handles_already_dead_pid(db: Database) -> None:
    async with db.session() as s:
        s.add(MasterSession(
            id="singleton", claude_session_id="x", pid=99999,
            started_at=datetime.now(UTC), last_active=datetime.now(UTC),
        ))
        await s.commit()

    with patch(
        "orchestrator.core.master_session.os.killpg",
        side_effect=ProcessLookupError(),
    ), patch("orchestrator.core.master_session.os.getpgid", return_value=99999):
        async with db.session() as s:
            await cleanup_orphan_master_at_startup(s)

    # pid deve ter sido limpo mesmo com PLE
    async with db.session() as s:
        master = await s.get(MasterSession, "singleton")
        assert master.pid is None
```

Write `tests/integration/test_master_spawn_failure_degraded.py`:

```python
"""F8.e: spawn failure → daemon sobe sem master (estado degradado)."""
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.main import create_app
from orchestrator.store.database import Database
from tests.integration.conftest import FakeSessionRuntime


@pytest.mark.integration
async def test_daemon_boots_without_master_on_spawn_failure(
    db: Database, runtime: FakeSessionRuntime,
) -> None:
    """ai-jail não no PATH → MasterSessionRuntime.spawn raise FileNotFoundError.
    Daemon sobe; resto da API funciona."""
    with patch(
        "orchestrator.sandbox.pty_runtime.MasterSessionRuntime.spawn",
        side_effect=FileNotFoundError("ai-jail not found"),
    ):
        app = create_app(database=db, runtime=runtime, ui_dist=None)
        # lifespan roda no first request
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r = await c.get("/health")
        assert r.status_code == 200
        # master_handle deve ser None
        assert getattr(app.state, "master_handle", "missing") is None
```

- [ ] **Step 7: Tests pass**

```bash
uv run pytest tests/integration/test_api_master_ws.py \
    tests/integration/test_master_session_persists.py \
    tests/integration/test_master_cleanup_orphan.py \
    tests/integration/test_master_spawn_failure_degraded.py -v
```

Expected: 5/5 pass.

- [ ] **Step 8: Suite + coverage + ruff**

```bash
uv run pytest tests/unit tests/integration --no-header 2>&1 | tail -10
uv run pytest tests/integration --cov=orchestrator/api/master_ws \
    --cov=orchestrator/core/master_session --cov-report=term-missing
uv run ruff check orchestrator/api/master_ws.py orchestrator/core/master_session.py \
    orchestrator/main.py tests/unit/test_pty_multiplexer.py \
    tests/integration/test_api_master_ws.py tests/integration/test_master_session_persists.py \
    tests/integration/test_master_cleanup_orphan.py \
    tests/integration/test_master_spawn_failure_degraded.py
```

Expected: suite verde; 100% coverage no novo código; ruff clean.

- [ ] **Step 9: Commit**

```bash
git add orchestrator/api/master_ws.py orchestrator/core/master_session.py \
        orchestrator/main.py \
        tests/unit/test_pty_multiplexer.py \
        tests/integration/test_api_master_ws.py \
        tests/integration/test_master_session_persists.py \
        tests/integration/test_master_cleanup_orphan.py \
        tests/integration/test_master_spawn_failure_degraded.py
git commit -m "feat(F8.e): WebSocket /ws/master + PtyMultiplexer + lifespan + cleanup_orphan"
```

---

## Task F8.f — UI MasterSidebar + xterm.js + WebSocket client

**Files:**
- Modify: `ui/package.json` (deps xterm)
- Create: `ui/src/components/MasterSidebar.tsx`
- Create: `ui/src/components/MasterSidebar.test.tsx`
- Modify: `ui/src/index.css`
- Modify: `ui/src/App.tsx` (embed sidebar)

- [ ] **Step 1: Adicionar deps xterm + smoke render gate**

Edit `ui/package.json`. Em `dependencies`:

```json
"@xterm/xterm": "^5.5.0",
"@xterm/addon-fit": "^0.10.0"
```

Run:

```bash
cd ui && npm install
```

**Gate de compat React 19 (real)**: o problema real não é `require()` funcionar (xterm é framework-agnostic) mas sim **renderização no StrictMode do React 19**, que double-mounts. Cria um smoke render real:

Write `ui/src/components/__xterm_smoke.test.tsx` (temporário, será removido após gate):

```typescript
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { StrictMode } from 'react';
import { Terminal } from '@xterm/xterm';
import '@xterm/xterm/css/xterm.css';

describe('xterm.js compat smoke', () => {
  it('Terminal constructs + opens in jsdom without throwing', () => {
    // Render dentro de StrictMode pra cobrir double-mount do React 19
    const Container = () => {
      const div = document.createElement('div');
      document.body.appendChild(div);
      const term = new Terminal({ rows: 24, cols: 80 });
      term.open(div);
      term.dispose();
      return null;
    };
    expect(() => {
      render(<StrictMode><Container /></StrictMode>);
    }).not.toThrow();
  });
});
```

Run:

```bash
cd ui && npx vitest run src/components/__xterm_smoke.test.tsx
```

Expected: 1/1 pass.

**Se falhar:**
1. Inspecionar erro. Common: peer dep React mismatch, `term.open` requer document, etc.
2. Tentar `npm install --legacy-peer-deps`
3. Downgrade pra `@xterm/xterm@5.4.0` se React 19 não for compatível
4. Bloqueador → escalar pra usuário; F8 fica pendente

Remova o smoke test após passar (será coberto pelos tests reais em Step 2-3).

- [ ] **Step 2: Escrever testes do component (TDD)**

Write `ui/src/components/MasterSidebar.test.tsx`:

```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MasterSidebar } from './MasterSidebar';

// Mock @xterm/xterm — não queremos renderizar xterm real em tests
vi.mock('@xterm/xterm', () => {
  return {
    Terminal: vi.fn().mockImplementation(() => ({
      loadAddon: vi.fn(),
      open: vi.fn(),
      onData: vi.fn(),
      onResize: vi.fn(),
      write: vi.fn(),
      dispose: vi.fn(),
    })),
  };
});

vi.mock('@xterm/addon-fit', () => {
  return {
    FitAddon: vi.fn().mockImplementation(() => ({
      fit: vi.fn(),
    })),
  };
});

class MockWebSocket {
  static OPEN = 1;
  onopen: ((ev: Event) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  readyState = 0;
  url: string;
  sentMessages: string[] = [];
  constructor(url: string) {
    this.url = url;
    setTimeout(() => {
      this.readyState = 1;
      this.onopen?.(new Event('open'));
    }, 0);
  }
  send(data: string) { this.sentMessages.push(data); }
  close() {}
}

describe('MasterSidebar', () => {
  let originalWs: typeof WebSocket;
  beforeEach(() => {
    originalWs = globalThis.WebSocket;
    // @ts-expect-error mock
    globalThis.WebSocket = MockWebSocket;
  });
  afterEach(() => {
    globalThis.WebSocket = originalWs;
  });

  it('renders sidebar with terminal container', () => {
    render(<MasterSidebar />);
    expect(screen.getByLabelText('master-session')).toBeInTheDocument();
    expect(screen.getByText('Claude master')).toBeInTheDocument();
  });

  it('opens WebSocket to /ws/master', () => {
    render(<MasterSidebar />);
    // Mock construtor de WebSocket foi chamado
    // (verificar via vi.spyOn em outro setup, ou via instância)
  });

  it('renders system error banner when WS sends type=system level=error', async () => {
    let wsInstance: MockWebSocket | null = null;
    const origCtor = globalThis.WebSocket;
    // @ts-expect-error capture
    globalThis.WebSocket = class extends MockWebSocket {
      constructor(url: string) {
        super(url);
        wsInstance = this as unknown as MockWebSocket;
      }
    };
    render(<MasterSidebar />);
    // Wait for WS to "open"
    await new Promise((r) => setTimeout(r, 10));
    expect(wsInstance).not.toBeNull();
    // Simula daemon enviando system error
    wsInstance!.onmessage?.(new MessageEvent('message', {
      data: JSON.stringify({
        type: 'system', level: 'error',
        message: 'master session not available',
      }),
    }));
    // Banner aparece
    await new Promise((r) => setTimeout(r, 10));
    const banner = await screen.findByLabelText('system-msg');
    expect(banner).toHaveTextContent('master session not available');
    expect(banner.className).toContain('error');
    globalThis.WebSocket = origCtor;
  });
});
```

- [ ] **Step 3: Implementar MasterSidebar**

Write `ui/src/components/MasterSidebar.tsx`:

```tsx
import { useEffect, useRef, useState } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';

type SystemMsg = { level: 'warn' | 'error'; message: string } | null;

export function MasterSidebar() {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const [systemMsg, setSystemMsg] = useState<SystemMsg>(null);

  useEffect(() => {
    const term = new Terminal({
      fontSize: 13,
      fontFamily: 'monospace',
      theme: { background: '#1e293b', foreground: '#e2e8f0' },
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    if (containerRef.current) {
      term.open(containerRef.current);
      fit.fit();
    }

    // Expose pra E2E (não-prod only)
    if (import.meta.env.MODE !== 'production') {
      (window as unknown as { __masterTerm?: Terminal }).__masterTerm = term;
    }

    const wsUrl = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/master`;
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === 'output') {
          term.write(msg.data);
        } else if (msg.type === 'system') {
          setSystemMsg({ level: msg.level, message: msg.message });
        }
      } catch {
        // ignore parse errors
      }
    };

    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'input', data }));
      }
    });
    term.onResize(({ rows, cols }) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'resize', rows, cols }));
      }
    });

    termRef.current = term;
    wsRef.current = ws;

    return () => {
      ws.close();
      term.dispose();
    };
  }, []);

  return (
    <aside className="master-sidebar" aria-label="master-session">
      <header>
        <h3>Claude master</h3>
        <span className="hint">compartilhado entre abas</span>
      </header>
      {systemMsg && (
        <div className={`system-msg ${systemMsg.level}`} aria-label="system-msg">
          {systemMsg.message}
        </div>
      )}
      <div ref={containerRef} className="master-term" />
    </aside>
  );
}
```

- [ ] **Step 4: Adicionar CSS**

Edit `ui/src/index.css`. Append:

```css
.master-sidebar {
  display: flex;
  flex-direction: column;
  width: 400px;
  height: 100vh;
  background: #1e293b;
  color: #e2e8f0;
  border-left: 1px solid #334155;
}

.master-sidebar header {
  display: flex;
  flex-direction: column;
  padding: 8px 12px;
  background: #0f172a;
}

.master-sidebar header h3 {
  margin: 0;
  font-size: 0.875rem;
}

.master-sidebar header .hint {
  font-size: 0.75rem;
  color: #94a3b8;
}

.master-term {
  flex: 1;
  padding: 4px;
}

.system-msg {
  padding: 6px 12px;
  font-size: 0.8rem;
}

.system-msg.warn { background: #78350f; color: #fef3c7; }
.system-msg.error { background: #7f1d1d; color: #fee2e2; }
```

- [ ] **Step 5: Embed no App.tsx**

Edit `ui/src/App.tsx`. Adicionar import:

```tsx
import { MasterSidebar } from './components/MasterSidebar';
```

Adaptar o layout wrapper pra CSS grid (find existing root div, wrap):

```tsx
<div className="app-layout">
  <main className="app-main">
    {/* ... existing Kanban + drawer etc ... */}
  </main>
  <MasterSidebar />
</div>
```

CSS para layout (em `index.css`):

```css
.app-layout {
  display: grid;
  grid-template-columns: 1fr 400px;
  height: 100vh;
}

.app-main {
  overflow: auto;
}
```

- [ ] **Step 6: Tests UI pass**

```bash
cd ui && npx vitest run src/components/MasterSidebar.test.tsx
```

Expected: pass. Coverage no `MasterSidebar.tsx`: 100% statements/branches (system error banner test cobre o ramo do `systemMsg`); xterm internals em `node_modules/@xterm` ficam excluded via vitest config (já é default por path).

- [ ] **Step 7: Build + type-check**

```bash
cd ui && npx tsc -b --noEmit
cd ui && npm run build
```

Expected: 0 errors; build succeeds.

- [ ] **Step 8: Smoke manual (host-only, opcional)**

Subir daemon + UI dev server, abrir browser em `http://localhost:5173`. Verificar:
- Sidebar aparece à direita
- xterm.js renderiza (área escura)
- Se daemon spawnou master: prompt do Claude aparece após segundos
- Digitar no terminal funciona (echo da Claude CLI)

Em sandbox: skip; documenta no commit message.

- [ ] **Step 9: Commit**

```bash
git add ui/package.json ui/package-lock.json \
        ui/src/components/MasterSidebar.tsx ui/src/components/MasterSidebar.test.tsx \
        ui/src/index.css ui/src/App.tsx
git commit -m "feat(F8.f): MasterSidebar UI com xterm.js + WebSocket client"
```

---

## Task F8.g — ADR-0022 + ARCHITECTURE F8 ✅ + E2E skeleton + closure

**Files:**
- Create: `docs/adr/0022-sessao-master-claude-no-sidebar-web.md`
- Create: `tests/e2e/test_f8_master_creates_task.py`
- Modify: `docs/adr/README.md`
- Modify: `ARCHITECTURE.md`

- [ ] **Step 1: Escrever ADR-0022**

Write `docs/adr/0022-sessao-master-claude-no-sidebar-web.md`:

```markdown
# ADR-0022: Sessão master Claude no sidebar web

**Status:** Accepted — 2026-05-11
**Decisores:** marcosdid + Claude
**Contexto:** F8 (primeira fase pós-MVP)

## Contexto

ARCHITECTURE.md §11 originalmente definia F8 como "Planner meta-agente —
usuário cola épico → preview de subtasks → backlog. Sessão efêmera, tela
de preview, bulk insert."

Durante brainstorm, a feature foi reformulada pra uma ambição maior:
uma **sessão master Claude global, persistente, renderizada num sidebar
web** que gerencia o app inteiro via tools que mexem no banco do J-arvis.
O caso de uso "decompor épico em subtasks" continua coberto, mas agora
como uma das interações possíveis com o master (você pede via chat,
Claude usa o tool `create_task` N vezes), não como UI dedicada.

Decidir:
1. Se F8 substitui o original ou coexiste
2. Onde a UI vive (browser sidebar vs terminal nativo)
3. Como o daemon "fala" com Claude headless
4. Quais ações o master pode executar
5. Como persistir conversas através de restart
6. Escopo (global vs per-project)

## Decisão

- **F8 substitui o original**. Decompor épico vira tool no chat genérico.
- **UI: sidebar web no J-arvis com xterm.js + PTY backend**. Tecnologia
  igual VSCode terminals (xterm.js + node-pty / os.openpty()).
- **Tech: mesma de F1+** — ai-jail + `claude --dangerously-skip-permissions`,
  porém em PTY pair (não terminal emulator nativo). Reusa toda a infra
  de F1+.
- **Tool surface ampla**: list/get/create/update/discard tasks + projetos.
  Fora de scope inicial: start_session, start_run, manage worktrees.
- **Persistência via Claude CLI `--resume <session-id>`**. Daemon grava
  `claude_session_id` no banco; restart spawna `claude --resume <id>` →
  Claude lembra naturalmente do jsonl que ele mesmo persiste.
- **Uma sessão global** (não per-project, não múltiplas conversas).
- **MCP protocol**: Streamable HTTP + JSON-RPC 2.0 via SDK oficial `mcp>=1.0`.
  Endpoint único `POST /api/mcp`. Auth via `Authorization: Bearer <token>`
  com token rotativo a cada boot.
- **Hooks F2 NÃO participam** no master (decisão 9 da spec): settings.json
  do master tem só `mcpServers` config + token, não hooks.

## Alternativas consideradas

- **Manter F8 original (planner épico) + adicionar master como F9**:
  rejeitado — master subsume o épico via tool.
- **Anthropic API direta**: rejeitado — diverge do padrão "tudo via Claude
  CLI" estabelecido em F1-F7.
- **REST endpoints per-tool em `/api/mcp/<tool>`**: rejeitado durante
  reviews — não é o protocolo MCP real (real é JSON-RPC).
- **Múltiplas conversas paralelas (estilo Cursor)**: rejeitado pra primeira
  iteração — YAGNI.

## Consequências

**Positivas:**
- Sem trabalho custom de persistência de conversa (Claude `--resume`).
- Reusa infra completa de F1+ (ai-jail, Claude CLI).
- Tool surface bem definida com schemas JSON validados.
- Daemon sobe mesmo se master falha (estado degradado).
- Master integra naturalmente com F7 (create_task com template via tool).

**Negativas:**
- Adiciona dep `mcp>=1.0` Python + xterm.js + addon-fit no UI.
- Múltiplas tabs compartilham mesma sessão (typo numa = todas veem). Mitigado
  por hint visível.
- Master é privilegiado (sem ai-jail isolation pra tools); risco maior se
  daemon for comprometido — token rotativo + scope reduzido (sem start_session)
  mitigam.
- `loop.add_reader` é Linux/macOS only; Windows out of scope.

## Referências

- Spec: `docs/superpowers/specs/2026-05-11-f8-master-session-design.md`
- Plan: `docs/superpowers/plans/2026-05-11-f8-master-session.md`
- ARCHITECTURE.md §11 (roadmap), §13 (decisões)
- Código: `orchestrator/mcp/`, `orchestrator/sandbox/pty_runtime.py`,
  `orchestrator/api/master_ws.py`
```

- [ ] **Step 2: Atualizar docs/adr/README.md**

Edit `docs/adr/README.md`. Append a row (após 0021):

```markdown
| [0022](0022-sessao-master-claude-no-sidebar-web.md) | Sessão master Claude no sidebar web (F8) | Accepted | 2026-05-11 |
```

- [ ] **Step 3: Atualizar ARCHITECTURE.md**

Edit `ARCHITECTURE.md`:

1. **§11 (roadmap):** substituir a linha F8 atual:

```markdown
| **F8 — Sessão master no sidebar** ✅ | Sessão Claude persistente global no sidebar web do J-arvis (xterm.js + PTY); manipula tasks via MCP tools (list/create/update/discard); persiste via `claude --resume` | `MasterSession` singleton + migration 0006; `MasterSessionRuntime` em PTY; MCP server JSON-RPC 2.0 via SDK `mcp`; WebSocket bridge com PtyMultiplexer fan-out; xterm.js + `@xterm/addon-fit` no UI |
```

2. **§13 (decisões registradas):** adicionar row:

```markdown
| F8 master session | [0022](docs/adr/0022-sessao-master-claude-no-sidebar-web.md) | xterm.js + PTY + MCP via Streamable HTTP | Reusa Claude CLI; tools no banco; persistência via `--resume` |
```

- [ ] **Step 4: Escrever E2E skeleton (host-only)**

Write `tests/e2e/test_f8_master_creates_task.py`:

```python
"""F8 E2E: master cria task via chat no sidebar.

⚠️ Cannot run from inside ai-jail (gotcha #9). Host-only:
    uv run --group test-e2e pytest tests/e2e/test_f8_master_creates_task.py -v

Flow:
1. Abrir UI; MasterSidebar conecta WebSocket
2. Aguardar prompt do Claude master aparecer no xterm
3. Digitar "Crie task 'Demo F8' no projeto X com template frontend" via xterm
4. Aguardar Claude responder + executar create_task MCP tool
5. Verificar task apareceu no Kanban
"""
import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
def test_f8_master_creates_task_via_chat(
    page: Page,
    orchestrator_with_repo: tuple[str, str],
) -> None:
    url, repo_path = orchestrator_with_repo

    page.goto(url)

    # Sidebar aparece
    expect(page.locator('[aria-label="master-session"]')).to_be_visible()
    expect(page.get_by_text("Claude master")).to_be_visible()

    # Cria projeto via drawer
    page.get_by_role("button", name="Projetos ▾").click()
    page.get_by_label("project-name").fill("demo")
    page.get_by_label("project-path").fill(repo_path)
    page.get_by_role("button", name="Adicionar projeto").click()
    page.get_by_label("close-drawer").click()

    # Espera o terminal renderizar prompt do Claude (até 30s)
    page.wait_for_function(
        """() => {
            const term = window.__masterTerm;
            if (!term) return false;
            const buffer = term.buffer.active;
            for (let i = 0; i < buffer.length; i++) {
                const line = buffer.getLine(i)?.translateToString();
                if (line && line.includes('claude')) return true;
            }
            return false;
        }""",
        timeout=30_000,
    )

    # Skeleton — passos detalhados de "type + assert task" ficam pra implementação
    # quando o E2E rodar host-side e o behavior real do Claude master estiver verificado
```

- [ ] **Step 5: Rodar suite completa**

```bash
uv run pytest tests/unit tests/integration --no-header 2>&1 | tail -10
cd ui && npx vitest run 2>&1 | tail -10
```

Expected: tudo verde. E2E skipped no sandbox (sem Playwright server / sem `ai-jail` real).

- [ ] **Step 6: Coverage gates finais**

```bash
uv run pytest tests/unit tests/integration --cov=orchestrator --cov-report=term-missing 2>&1 | tail -30
cd ui && npx vitest run --coverage 2>&1 | tail -10
```

Expected: 100% backend mantido (modulo `# pragma: no cover` em SubprocessPtyOps); 100% UI mantido (modulo xterm.js internals excluded).

- [ ] **Step 7: Ruff final**

```bash
uv run ruff check orchestrator tests
```

Expected: apenas findings pre-existentes (PLC0415 em core/tasks.py); nada novo.

- [ ] **Step 8: Commit closure**

```bash
git add docs/adr/0022-sessao-master-claude-no-sidebar-web.md \
        docs/adr/README.md ARCHITECTURE.md \
        tests/e2e/test_f8_master_creates_task.py
git commit -m "feat(F8.g): ADR-0022 + ARCHITECTURE F8 ✅ + E2E skeleton

Fecha F8 (primeira pós-MVP). Sessão master Claude persistente no sidebar
web com tools MCP. Reusa Claude CLI via --resume. Daemon sobe gracefully
sem master se spawn falha (estado degradado)."
```

---

## Pós-implementação: verificação final

- [ ] **Suite full backend**: `uv run pytest tests/unit tests/integration -v --no-header` — verde
- [ ] **Suite full UI**: `cd ui && npx vitest run` — verde
- [ ] **Coverage backend**: 100% em F8 (modulo SubprocessPtyOps pragma)
- [ ] **Coverage UI**: 100% mantido (xterm.js internals excluded)
- [ ] **Lint backend**: `uv run ruff check orchestrator tests` — clean (modulo pre-existing)
- [ ] **Type-check UI**: `cd ui && npx tsc -b --noEmit` — 0 errors
- [ ] **Build UI**: `cd ui && npm run build` — sucesso
- [ ] **Migration aplicável**: `uv run alembic upgrade head --sql` — gera SQL válido
- [ ] **Manual smoke (host)**: abrir UI, ver sidebar, ver Claude responder, criar task via chat, ver task aparecer no Kanban

## Notas pra implementador

- **TDD obrigatório**: cada step "Write test" antes do step "Implement". Não invertam.
- **Commits granulares por sub-task**: 7 commits no total (F8.a → F8.g). Não squash.
- **Reviewer antes de cada commit**: dispatch `code-reviewer` ou `superpowers:code-reviewer` no diff staged (CLAUDE.md `Pre-commit code review`). Conserta findings antes do commit final.
- **Não amenda commits**: se hook falha, conserta + novo commit.
- **MCP SDK API verification**: o protocolo MCP é estável (2025-11-25) mas a API exata do Python SDK `mcp>=1.0` pode ter ajustes finos (especialmente `request_context.state` injection). Verificar docs/exemplos do SDK no momento de F8.c — se a API divergir do plan, ajustar wrapper `build_mcp_app` sem mudar contrato funcional.
- **xterm.js + React 19 compat**: F8.f step 1 tem gate de smoke. Se falhar, escalar pra usuário antes de prosseguir.
- **Linux/macOS only**: `loop.add_reader` não funciona no Windows. Documentado em decisão 8 da spec.
- **`master_runtime` é não-deterministic em testes**: tests que dependem do real ai-jail+claude rodando são E2E only. Unit/integration usam FakePtyOps + mocks.
