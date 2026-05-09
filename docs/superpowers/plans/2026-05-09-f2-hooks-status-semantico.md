# F2 — Hooks + Status Semântico Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar 3 endpoints de hooks (`/api/hooks/Notification|PreToolUse|Stop/{token}`), parser de eventos, broadcast via WebSocket único e notificações nativas (`notify-send`) — para que a UI mostre status semântico em tempo real sem reload.

**Architecture:** Hooks recebem payload do Claude Code dentro da jaula via curl (settings.json injetado no `<worktree>/.claude/`). Acoplamento direto: handler chama parser → repo.update_status → ws_broadcaster → notifier. WS único em `/ws` com envelope tipado `{type, session_id, payload, at}`. Token UUID por sessão na URL para correlação. F2 só usa `AWAITING_RESPONSE`, `IDLE` semanticamente; `AWAITING_APPROVAL` reservado pra F3.

**Tech Stack:** Python 3.13 + FastAPI + SQLAlchemy 2 async + Alembic + pytest/asyncio + httpx + testcontainers / React 19 + Vite + TanStack Query + Vitest + Playwright.

**Spec:** `docs/superpowers/specs/2026-05-09-f2-hooks-status-semantico-design.md`

---

## File Structure

### Backend (novos)

| Path | Responsabilidade |
|---|---|
| `orchestrator/hooks/parser.py` | Funções puras `parse_notification`, `parse_pretooluse`, `parse_stop`. |
| `orchestrator/hooks/tokens.py` | `TokenRegistry` (in-memory dict[token, session_id]) + `generate_token`. |
| `orchestrator/hooks/router.py` | FastAPI router com 3 endpoints `POST /api/hooks/<event>/{token}`. |
| `orchestrator/events/__init__.py` | Vazio (marca pacote). |
| `orchestrator/events/envelope.py` | Dataclass `WsEvent` + factories. |
| `orchestrator/events/broadcaster.py` | Protocol `WsBroadcaster` + `InMemoryWsBroadcaster`. |
| `orchestrator/notifications/__init__.py` | Vazio. |
| `orchestrator/notifications/sink.py` | Protocol `NotifierSink` + função `should_notify(prev, new)`. |
| `orchestrator/notifications/notify_send.py` | `NotifySendNotifier` (subprocess) + `NoopNotifier`. |
| `orchestrator/sandbox/settings_writer.py` | `build_settings_json`, `write_settings_into_jail`, `ensure_gitignore_entry`, `remove_settings_from_jail`. |
| `orchestrator/api/ws.py` | FastAPI WebSocket endpoint `GET /ws`. |
| `alembic/versions/0002_hook_columns.py` | Migration aditiva: `hook_token`, `last_hook_at`. |
| `docs/adr/0009-hooks-via-settings-no-jail.md` | ADR. |
| `docs/adr/0010-websocket-canal-unico-envelope-tipado.md` | ADR. |

### Backend (modificados)

| Path | Mudança |
|---|---|
| `orchestrator/store/models.py` | `ClaudeSession.hook_token`, `last_hook_at`. |
| `orchestrator/core/sessions.py` | + `update_status()` idempotente; `start_session` aceita `token_registry`+`base_url`; `stop_session` revoga token. |
| `orchestrator/sandbox/aijail.py` | `spawn` aceita `token+base_url`; chama `settings_writer`; `kill` ganha kwarg `worktree` e remove o settings.json. |
| `orchestrator/sandbox/runtime.py` | Protocol `SessionRuntime.spawn` ganha kwargs opcionais `token`, `base_url`; `kill` ganha kwarg `worktree`. |
| `orchestrator/sandbox/null.py` | Mesma assinatura ampliada (no-op). |
| `orchestrator/api/_deps.py` | + `resolve_token_registry`, `resolve_broadcaster`, `resolve_notifier`. |
| `orchestrator/api/sessions.py` | Handlers passam registry+base_url pro core. |
| `orchestrator/main.py` | Registra `hooks_router`, `ws_router`; injeta broadcaster + notifier + token registry. |
| `orchestrator/config.py` | + `port: int = 8765`, `notify: Literal["on","off"]`, `hook_base_url: str | None`. |
| `docs/adr/README.md` | Index das ADRs novas. |
| `ARCHITECTURE.md` | §4 + §13 atualizados. |

### Frontend (novos)

| Path | Responsabilidade |
|---|---|
| `ui/src/lib/ws.ts` | `connectWs(onEvent)` com reconnect+backoff exponencial; expõe `disconnect()`. |
| `ui/src/lib/events.ts` | Tipo `WsEvent` + dispatcher por `type`. |
| `ui/src/hooks/useSessionEvents.ts` | Hook que invalida `queryKeys.sessions` ao receber `session.status` ou `session.stopped`. |

### Frontend (modificados)

| Path | Mudança |
|---|---|
| `ui/src/App.tsx` | Monta `useSessionEvents()` no nível raiz. |

### Tests

| Camada | Path |
|---|---|
| Unit | `tests/unit/test_hooks_parser.py`, `test_token_registry.py`, `test_session_update_status.py`, `test_ws_envelope.py`, `test_notifier_sink.py`, `test_aijail_settings_writer.py`, `test_in_memory_broadcaster.py`, `test_notify_send_notifier.py`. |
| Integration | `tests/integration/test_hooks_routes.py`, `test_hooks_concurrency.py`, `test_ws_endpoint.py`, `test_session_lifecycle_with_hooks.py`. |
| E2E | `tests/e2e/test_hooks_e2e_flow.py`. |
| Vitest | `ui/src/lib/ws.test.ts`, `events.test.ts`, `ui/src/hooks/useSessionEvents.test.ts`. |

---

## Disciplina

- **TDD strict** (RED → GREEN → REFACTOR → COMMIT). Não escrever produção sem teste falhando.
- **`# pragma: no cover`** apenas em: defesa de plataforma para `notify-send` ausente; `SubprocessRunner` real; registro de novos routers em `_build_production_app`; debug endpoint condicional usado só em E2E.
- **Code-review subagent antes de cada commit** (per global CLAUDE.md). Dispatch via `Agent(subagent_type="superpowers:code-reviewer", ...)` ou `feature-dev:code-reviewer`.
- Cada `git commit` usa HEREDOC, sem `--no-verify`. Hook signing já desligado neste repo.
- Comandos pytest sempre via `uv run pytest ...`. Vitest via `pnpm --dir ui test ...`.

---

## Task 1 — F2.a: HookEvent parser (pure domain)

**Files:**
- Modify: `orchestrator/hooks/__init__.py` (já existe vazio — manter)
- Create: `orchestrator/hooks/parser.py`
- Create: `tests/unit/test_hooks_parser.py`

- [ ] **Step 1: Escrever teste falhando — `parse_notification`**

```python
# tests/unit/test_hooks_parser.py
import pytest

from orchestrator.core.sessions import SessionStatus
from orchestrator.hooks.parser import (
    InvalidHookPayloadError,
    parse_notification,
    parse_pretooluse,
    parse_stop,
)


def test_parse_notification_returns_awaiting_response() -> None:
    payload = {"message": "Claude needs your input"}
    assert parse_notification(payload) == SessionStatus.AWAITING_RESPONSE


def test_parse_notification_missing_message_raises() -> None:
    with pytest.raises(InvalidHookPayloadError):
        parse_notification({})


def test_parse_stop_returns_idle() -> None:
    assert parse_stop({"reason": "turn-end"}) == SessionStatus.IDLE


def test_parse_pretooluse_returns_tool_name() -> None:
    payload = {"tool_name": "Bash", "tool_input": {"command": "ls"}}
    assert parse_pretooluse(payload) == "Bash"


def test_parse_pretooluse_missing_tool_name_raises() -> None:
    with pytest.raises(InvalidHookPayloadError):
        parse_pretooluse({})
```

- [ ] **Step 2: Rodar e confirmar RED**

Run: `uv run pytest tests/unit/test_hooks_parser.py -v`
Expected: `ImportError` ou `ModuleNotFoundError` em `orchestrator.hooks.parser`.

- [ ] **Step 3: Implementação mínima**

```python
# orchestrator/hooks/parser.py
"""Pure functions that translate hook payloads into domain decisions."""

from typing import Any

from orchestrator.core.sessions import SessionStatus


class InvalidHookPayloadError(Exception):
    pass


def parse_notification(payload: dict[str, Any]) -> SessionStatus:
    if "message" not in payload:
        raise InvalidHookPayloadError("Notification payload missing 'message'")
    return SessionStatus.AWAITING_RESPONSE


def parse_stop(_payload: dict[str, Any]) -> SessionStatus:
    return SessionStatus.IDLE


def parse_pretooluse(payload: dict[str, Any]) -> str:
    tool = payload.get("tool_name")
    if not isinstance(tool, str) or not tool:
        raise InvalidHookPayloadError("PreToolUse payload missing 'tool_name'")
    return tool
```

- [ ] **Step 4: Rodar e confirmar GREEN**

Run: `uv run pytest tests/unit/test_hooks_parser.py -v`
Expected: 5 passed.

- [ ] **Step 5: Coverage check**

Run: `uv run pytest tests/unit/test_hooks_parser.py --cov=orchestrator.hooks.parser --cov-report=term-missing`
Expected: 100%.

- [ ] **Step 6: Code review subagent**

Dispatch `superpowers:code-reviewer` (ou equivalente) com prompt: "Review the staged diff for `orchestrator/hooks/parser.py` and `tests/unit/test_hooks_parser.py` against the plan in `docs/superpowers/plans/2026-05-09-f2-hooks-status-semantico.md` (Task 1) and the spec §6. Flag SOLID/YAGNI violations, missing edge cases, weak assertions."

Aplicar findings antes do commit.

- [ ] **Step 7: Commit**

```bash
git add orchestrator/hooks/parser.py tests/unit/test_hooks_parser.py
git commit -m "$(cat <<'EOF'
feat(F2.a): hook payload parser (pure domain)

- parse_notification → AWAITING_RESPONSE
- parse_stop → IDLE
- parse_pretooluse → tool_name (audit-only em F2)
- InvalidHookPayloadError em payloads malformados
EOF
)"
```

---

## Task 2 — F2.b: TokenRegistry (pure)

**Files:**
- Create: `orchestrator/hooks/tokens.py`
- Create: `tests/unit/test_token_registry.py`

- [ ] **Step 1: Teste falhando**

```python
# tests/unit/test_token_registry.py
from orchestrator.hooks.tokens import TokenRegistry, generate_token


def test_generate_token_is_unique_hex() -> None:
    a, b = generate_token(), generate_token()
    assert a != b
    assert len(a) == 32
    assert all(c in "0123456789abcdef" for c in a)


def test_register_then_resolve_returns_session_id() -> None:
    reg = TokenRegistry()
    token = generate_token()
    reg.register(token, "sess-1")
    assert reg.resolve(token) == "sess-1"


def test_resolve_unknown_returns_none() -> None:
    assert TokenRegistry().resolve("nope") is None


def test_revoke_removes_token() -> None:
    reg = TokenRegistry()
    token = generate_token()
    reg.register(token, "sess-1")
    reg.revoke(token)
    assert reg.resolve(token) is None


def test_revoke_unknown_is_noop() -> None:
    TokenRegistry().revoke("never-registered")  # must not raise
```

- [ ] **Step 2: RED**

Run: `uv run pytest tests/unit/test_token_registry.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implementação**

```python
# orchestrator/hooks/tokens.py
"""Per-session opaque tokens correlating hook calls with ClaudeSession rows.

In-memory dict is the source of truth at runtime. The DB column
``ClaudeSession.hook_token`` mirrors it for audit/diagnostic; we do
NOT rebuild the registry from the DB on daemon boot (daemon is
on-demand and restart kills sessions, per ARCHITECTURE.md §1.4).
"""

from uuid import uuid4


def generate_token() -> str:
    return uuid4().hex


class TokenRegistry:
    def __init__(self) -> None:
        self._map: dict[str, str] = {}

    def register(self, token: str, session_id: str) -> None:
        self._map[token] = session_id

    def resolve(self, token: str) -> str | None:
        return self._map.get(token)

    def revoke(self, token: str) -> None:
        self._map.pop(token, None)
```

- [ ] **Step 4: GREEN**

Run: `uv run pytest tests/unit/test_token_registry.py -v`
Expected: 5 passed.

- [ ] **Step 5: Coverage**

Run: `uv run pytest tests/unit/test_token_registry.py --cov=orchestrator.hooks.tokens --cov-report=term-missing`
Expected: 100%.

- [ ] **Step 6: Code review subagent** (mesmo padrão do Task 1).

- [ ] **Step 7: Commit**

```bash
git add orchestrator/hooks/tokens.py tests/unit/test_token_registry.py
git commit -m "$(cat <<'EOF'
feat(F2.b): TokenRegistry in-memory + generate_token

In-memory é source-of-truth em runtime; DB column é audit only.
Daemon on-demand não rebuilda registry no boot (spec §2 row 7).
EOF
)"
```

---

## Task 3 — F2.c: WS envelope + Notifier sink (pure)

**Files:**
- Create: `orchestrator/events/__init__.py` (vazio)
- Create: `orchestrator/events/envelope.py`
- Create: `orchestrator/notifications/__init__.py` (vazio)
- Create: `orchestrator/notifications/sink.py`
- Create: `tests/unit/test_ws_envelope.py`
- Create: `tests/unit/test_notifier_sink.py`

- [ ] **Step 1: Teste do envelope**

```python
# tests/unit/test_ws_envelope.py
from datetime import datetime

from orchestrator.events.envelope import WsEvent


def test_session_status_event_serialisation() -> None:
    event = WsEvent.session_status(
        session_id="sess-1",
        new_status="awaiting_response",
        previous_status="executing",
    )
    serialised = event.to_dict()
    assert serialised["type"] == "session.status"
    assert serialised["session_id"] == "sess-1"
    assert serialised["payload"] == {
        "status": "awaiting_response",
        "previous": "executing",
    }
    datetime.fromisoformat(serialised["at"])


def test_session_tool_use_event() -> None:
    event = WsEvent.session_tool_use(session_id="sess-1", tool="Bash")
    assert event.to_dict()["type"] == "session.tool_use"
    assert event.to_dict()["payload"] == {"tool": "Bash"}


def test_session_stopped_event_payload_empty() -> None:
    event = WsEvent.session_stopped(session_id="sess-1")
    assert event.to_dict()["type"] == "session.stopped"
    assert event.to_dict()["payload"] == {}


def test_at_is_timezone_aware() -> None:
    event = WsEvent.session_stopped(session_id="x")
    parsed = datetime.fromisoformat(event.to_dict()["at"])
    assert parsed.tzinfo is not None
```

- [ ] **Step 2: RED**

Run: `uv run pytest tests/unit/test_ws_envelope.py -v`

- [ ] **Step 3: Implementação envelope**

```python
# orchestrator/events/envelope.py
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class WsEvent:
    type: str
    session_id: str
    payload: dict[str, Any]
    at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "session_id": self.session_id,
            "payload": self.payload,
            "at": self.at,
        }

    @classmethod
    def session_status(
        cls, *, session_id: str, new_status: str, previous_status: str
    ) -> "WsEvent":
        return cls(
            type="session.status",
            session_id=session_id,
            payload={"status": new_status, "previous": previous_status},
        )

    @classmethod
    def session_tool_use(cls, *, session_id: str, tool: str) -> "WsEvent":
        return cls(
            type="session.tool_use",
            session_id=session_id,
            payload={"tool": tool},
        )

    @classmethod
    def session_stopped(cls, *, session_id: str) -> "WsEvent":
        return cls(type="session.stopped", session_id=session_id, payload={})
```

- [ ] **Step 4: GREEN envelope**

Run: `uv run pytest tests/unit/test_ws_envelope.py -v`
Expected: 4 passed.

- [ ] **Step 5: Teste do notifier sink**

```python
# tests/unit/test_notifier_sink.py
import pytest

from orchestrator.core.sessions import SessionStatus
from orchestrator.notifications.sink import should_notify


@pytest.mark.parametrize("prev", [SessionStatus.EXECUTING, SessionStatus.IDLE])
def test_should_notify_when_transitioning_to_awaiting_response(prev: SessionStatus) -> None:
    assert should_notify(prev, SessionStatus.AWAITING_RESPONSE) is True


@pytest.mark.parametrize("prev", [SessionStatus.EXECUTING, SessionStatus.AWAITING_RESPONSE])
def test_should_notify_when_transitioning_to_idle(prev: SessionStatus) -> None:
    assert should_notify(prev, SessionStatus.IDLE) is True


@pytest.mark.parametrize("new", [SessionStatus.EXECUTING, SessionStatus.DONE, SessionStatus.ERROR])
def test_should_not_notify_for_other_targets(new: SessionStatus) -> None:
    assert should_notify(SessionStatus.IDLE, new) is False


def test_should_not_notify_on_idempotent_transition() -> None:
    assert should_notify(SessionStatus.IDLE, SessionStatus.IDLE) is False
    assert should_notify(SessionStatus.AWAITING_RESPONSE, SessionStatus.AWAITING_RESPONSE) is False
```

- [ ] **Step 6: RED**

Run: `uv run pytest tests/unit/test_notifier_sink.py -v`

- [ ] **Step 7: Implementação sink**

```python
# orchestrator/notifications/sink.py
"""Notification policy + Protocol."""

from typing import Protocol

from orchestrator.core.sessions import SessionStatus

_NOTIFY_TARGETS = frozenset({SessionStatus.AWAITING_RESPONSE, SessionStatus.IDLE})


def should_notify(previous: SessionStatus, new: SessionStatus) -> bool:
    if previous == new:
        return False
    return new in _NOTIFY_TARGETS


class NotifierSink(Protocol):
    async def notify(self, *, summary: str, body: str, icon: str) -> None: ...
```

- [ ] **Step 8: GREEN**

Run: `uv run pytest tests/unit/test_notifier_sink.py -v`

- [ ] **Step 9: Coverage**

Run: `uv run pytest tests/unit/test_ws_envelope.py tests/unit/test_notifier_sink.py --cov=orchestrator.events --cov=orchestrator.notifications --cov-report=term-missing`
Expected: 100%.

- [ ] **Step 10: Code review** subagent.

- [ ] **Step 11: Commit**

```bash
git add orchestrator/events/ orchestrator/notifications/ tests/unit/test_ws_envelope.py tests/unit/test_notifier_sink.py
git commit -m "$(cat <<'EOF'
feat(F2.c): WsEvent envelope + NotifierSink policy (pure)

- WsEvent dataclass + factories (session.status / session.tool_use / session.stopped)
- should_notify(): apenas em * → AWAITING_RESPONSE e * → IDLE (spec §6)
- NotifierSink Protocol; impls reais ficam pra Task 6
EOF
)"
```

---

## Task 4 — F2.d: Schema delta + `update_status` idempotente

**Files:**
- Modify: `orchestrator/store/models.py`
- Create: `alembic/versions/0002_hook_columns.py`
- Modify: `orchestrator/core/sessions.py` (+ `update_status`)
- Create: `tests/unit/test_session_update_status.py`

- [ ] **Step 1: Teste do `update_status`**

```python
# tests/unit/test_session_update_status.py
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from orchestrator.core.sessions import (
    SessionNotFoundError,
    SessionStatus,
    update_status,
)
from orchestrator.store.database import Database
from orchestrator.store.models import ClaudeSession, Project, Worktree


@pytest.fixture
async def db(tmp_path: Path) -> AsyncIterator[Database]:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    await database.bootstrap()
    try:
        yield database
    finally:
        await database.close()


async def _seed_session(database: Database, status: SessionStatus) -> str:
    async with database.session() as s:
        proj = Project(name="p", path="/tmp/p")
        s.add(proj); await s.commit(); await s.refresh(proj)
        wt = Worktree(project_id=proj.id, path="/tmp/p/wt", branch="main")
        s.add(wt); await s.commit(); await s.refresh(wt)
        row = ClaudeSession(
            worktree_id=wt.id,
            status=status,
            pid=1,
            jail_id="j-1",
            started_at=datetime.now(UTC),
        )
        s.add(row); await s.commit(); await s.refresh(row)
        return row.id


@pytest.mark.asyncio
async def test_update_status_changes_row_and_returns_pair(db: Database) -> None:
    sid = await _seed_session(db, SessionStatus.EXECUTING)
    async with db.session() as s:
        prev, new = await update_status(s, sid, SessionStatus.AWAITING_RESPONSE)
    assert (prev, new) == (SessionStatus.EXECUTING, SessionStatus.AWAITING_RESPONSE)
    async with db.session() as s:
        fresh = await s.get(ClaudeSession, sid)
        assert fresh is not None
        assert fresh.status == SessionStatus.AWAITING_RESPONSE
        assert fresh.last_hook_at is not None


@pytest.mark.asyncio
async def test_update_status_is_idempotent_no_change(db: Database) -> None:
    sid = await _seed_session(db, SessionStatus.IDLE)
    async with db.session() as s:
        prev, new = await update_status(s, sid, SessionStatus.IDLE)
    assert prev == new == SessionStatus.IDLE


@pytest.mark.asyncio
async def test_update_status_terminal_blocks_change(db: Database) -> None:
    sid = await _seed_session(db, SessionStatus.DONE)
    async with db.session() as s:
        prev, new = await update_status(s, sid, SessionStatus.AWAITING_RESPONSE)
    assert prev == new == SessionStatus.DONE


@pytest.mark.asyncio
async def test_update_status_unknown_session_raises(db: Database) -> None:
    async with db.session() as s:
        with pytest.raises(SessionNotFoundError):
            await update_status(s, "no-such-id", SessionStatus.IDLE)


@pytest.mark.asyncio
async def test_update_status_bumps_last_hook_at_even_when_idempotent(db: Database) -> None:
    sid = await _seed_session(db, SessionStatus.IDLE)
    async with db.session() as s:
        await update_status(s, sid, SessionStatus.IDLE)
    async with db.session() as s:
        fresh = await s.get(ClaudeSession, sid)
        assert fresh is not None and fresh.last_hook_at is not None


@pytest.mark.asyncio
async def test_bump_last_hook_at_updates_only_timestamp(db: Database) -> None:
    from orchestrator.core.sessions import bump_last_hook_at
    sid = await _seed_session(db, SessionStatus.EXECUTING)
    async with db.session() as s:
        await bump_last_hook_at(s, sid)
    async with db.session() as s:
        row = await s.get(ClaudeSession, sid)
        assert row is not None
        assert row.status == SessionStatus.EXECUTING  # unchanged
        assert row.last_hook_at is not None


@pytest.mark.asyncio
async def test_bump_last_hook_at_unknown_raises(db: Database) -> None:
    from orchestrator.core.sessions import bump_last_hook_at
    async with db.session() as s:
        with pytest.raises(SessionNotFoundError):
            await bump_last_hook_at(s, "no-such-id")
```

- [ ] **Step 2: RED**

Run: `uv run pytest tests/unit/test_session_update_status.py -v`
Expected: import errors / `last_hook_at` missing / `update_status` undefined.

- [ ] **Step 3: Modificar `models.py`**

Edit `orchestrator/store/models.py` para o `ClaudeSession` — adicionar 2 colunas no fim:

```python
    hook_token: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True)
    last_hook_at: Mapped[datetime | None] = mapped_column(nullable=True)
```

- [ ] **Step 4: Criar migration `0002_hook_columns.py`**

```python
# alembic/versions/0002_hook_columns.py
"""hook columns

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-09

"""
import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sessions") as batch:
        batch.add_column(sa.Column("hook_token", sa.String(32), nullable=True))
        batch.add_column(sa.Column("last_hook_at", sa.DateTime(), nullable=True))
        batch.create_index(
            "ix_sessions_hook_token",
            ["hook_token"],
            unique=True,
            sqlite_where=sa.text("hook_token IS NOT NULL"),
        )


def downgrade() -> None:
    with op.batch_alter_table("sessions") as batch:
        batch.drop_index("ix_sessions_hook_token")
        batch.drop_column("last_hook_at")
        batch.drop_column("hook_token")
```

- [ ] **Step 5: Adicionar `update_status` em `core/sessions.py`**

Append ao `orchestrator/core/sessions.py`:

```python
async def update_status(
    session: AsyncSession,
    session_id: str,
    new_status: SessionStatus,
) -> tuple[SessionStatus, SessionStatus]:
    """Idempotent status mutation. Returns (previous, new).

    `session.refresh(row)` is intentional (per spec §7): when multiple hook
    handlers share the same `AsyncSession`, the in-identity-map row may be
    stale from a sibling write. SQLite serialises writes; refresh bridges
    reads cleanly. Postgres migration will revisit.
    """
    row = await session.get(ClaudeSession, session_id)
    if row is None:
        raise SessionNotFoundError(f"session not found: {session_id}")
    await session.refresh(row)
    previous = SessionStatus(row.status)
    row.last_hook_at = datetime.now(UTC)
    if previous in _TERMINAL_STATUSES or previous == new_status:
        await session.commit()
        return previous, previous
    row.status = new_status
    await session.commit()
    return previous, new_status


async def bump_last_hook_at(session: AsyncSession, session_id: str) -> None:
    """Update only ``last_hook_at`` without touching status.

    Used by audit-only hooks (``PreToolUse``) where we don't want a status
    transition but still want to record that the session is alive.
    """
    row = await session.get(ClaudeSession, session_id)
    if row is None:
        raise SessionNotFoundError(f"session not found: {session_id}")
    await session.refresh(row)
    row.last_hook_at = datetime.now(UTC)
    await session.commit()
```

- [ ] **Step 6: GREEN**

Run: `uv run pytest tests/unit/test_session_update_status.py -v`
Expected: 5 passed.

- [ ] **Step 7: Verificar migration aplicável + roundtrip**

```bash
rm -f /tmp/jarvis-test.db
JARVIS_DATABASE_URL="sqlite:////tmp/jarvis-test.db" uv run alembic upgrade head
sqlite3 /tmp/jarvis-test.db "PRAGMA table_info(sessions);"
JARVIS_DATABASE_URL="sqlite:////tmp/jarvis-test.db" uv run alembic downgrade -1
JARVIS_DATABASE_URL="sqlite:////tmp/jarvis-test.db" uv run alembic upgrade head
sqlite3 /tmp/jarvis-test.db "PRAGMA table_info(sessions);"
```

Expected: 9 colunas após upgrade (incluindo `hook_token`, `last_hook_at`); 7 colunas após downgrade; 9 de novo após upgrade. `batch_alter_table` em SQLite recria a tabela — confirmar que dados não somem (com tabela vazia o teste é ok; com dados, F1 já cobre via `test_db_roundtrip.py`).

- [ ] **Step 8: Coverage delta**

Run: `uv run pytest tests/unit/test_session_update_status.py --cov=orchestrator.core.sessions --cov-report=term-missing`
Expected: 100% sobre `update_status`.

- [ ] **Step 9: Suite completa pra confirmar não regrediu**

Run: `uv run pytest tests/unit tests/integration -m 'not e2e' -v`
Expected: tudo verde, 30+ unit + 19+ integration tests.

- [ ] **Step 10: Code review** subagent.

- [ ] **Step 11: Commit**

```bash
git add orchestrator/store/models.py orchestrator/core/sessions.py alembic/versions/0002_hook_columns.py tests/unit/test_session_update_status.py
git commit -m "$(cat <<'EOF'
feat(F2.d): ClaudeSession ganha hook_token + last_hook_at; update_status idempotente

- Migration 0002 aditiva (batch_alter_table p/ SQLite)
- update_status: terminal absorvente, no-change = no-op (mas sempre bumps last_hook_at)
- Tests cobrem 5 cenários (mudança, idempotência, terminal, unknown, last_hook_at)
EOF
)"
```

---

## Task 5 — F2.e: Settings writer + AiJailRuntime integration

**Files:**
- Create: `orchestrator/sandbox/settings_writer.py`
- Modify: `orchestrator/sandbox/aijail.py`, `runtime.py`, `null.py`
- Modify: `orchestrator/core/sessions.py`
- Create: `tests/unit/test_aijail_settings_writer.py`
- Modify: `tests/integration/conftest.py` (FakeSessionRuntime ganha kwargs)

- [ ] **Step 1: Teste do settings_writer**

```python
# tests/unit/test_aijail_settings_writer.py
import json
from pathlib import Path

from orchestrator.sandbox.settings_writer import (
    build_settings_json,
    ensure_gitignore_entry,
    remove_settings_from_jail,
    write_settings_into_jail,
)


def test_build_settings_json_has_three_hooks() -> None:
    payload = build_settings_json(token="tok-abc", base_url="http://localhost:8765")
    parsed = json.loads(payload)
    assert set(parsed["hooks"]) == {"Notification", "PreToolUse", "Stop"}


def test_build_settings_json_embeds_token_and_base_url() -> None:
    payload = build_settings_json(token="tok-xyz", base_url="http://h:9000")
    cmd = json.loads(payload)["hooks"]["Notification"][0]["hooks"][0]["command"]
    assert "tok-xyz" in cmd
    assert "http://h:9000/api/hooks/Notification/tok-xyz" in cmd


def test_pretooluse_command_never_blocks() -> None:
    payload = build_settings_json(token="t", base_url="http://h:1")
    cmd = json.loads(payload)["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert cmd.endswith("; exit 0")


def test_write_settings_creates_file_inside_claude_dir(tmp_path: Path) -> None:
    write_settings_into_jail(tmp_path, token="t", base_url="http://h:1")
    settings = tmp_path / ".claude" / "settings.json"
    assert settings.is_file()
    parsed = json.loads(settings.read_text(encoding="utf-8"))
    assert "hooks" in parsed


def test_write_settings_overwrites_existing(tmp_path: Path) -> None:
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text("stale", encoding="utf-8")
    write_settings_into_jail(tmp_path, token="t", base_url="http://h:1")
    parsed = json.loads(settings.read_text(encoding="utf-8"))
    assert "hooks" in parsed


def test_ensure_gitignore_entry_appends_when_missing(tmp_path: Path) -> None:
    ensure_gitignore_entry(tmp_path)
    content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert ".claude/settings.json" in content


def test_ensure_gitignore_entry_idempotent(tmp_path: Path) -> None:
    ensure_gitignore_entry(tmp_path)
    ensure_gitignore_entry(tmp_path)
    content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert content.count(".claude/settings.json") == 1


def test_ensure_gitignore_creates_file_when_absent(tmp_path: Path) -> None:
    assert not (tmp_path / ".gitignore").exists()
    ensure_gitignore_entry(tmp_path)
    assert (tmp_path / ".gitignore").is_file()


def test_remove_settings_silently_ok_when_absent(tmp_path: Path) -> None:
    remove_settings_from_jail(tmp_path)


def test_remove_settings_removes_file_when_present(tmp_path: Path) -> None:
    write_settings_into_jail(tmp_path, token="t", base_url="http://h:1")
    remove_settings_from_jail(tmp_path)
    assert not (tmp_path / ".claude" / "settings.json").exists()
```

- [ ] **Step 2: RED**

Run: `uv run pytest tests/unit/test_aijail_settings_writer.py -v`
Expected: ImportError.

- [ ] **Step 3: Implementação `settings_writer.py`**

```python
# orchestrator/sandbox/settings_writer.py
"""Writes ``.claude/settings.json`` into the worktree before ``ai-jail run``."""

import json
from pathlib import Path

_GITIGNORE_LINE = ".claude/settings.json"


def build_settings_json(*, token: str, base_url: str) -> str:
    def hook(event: str, *, terminator: str = "") -> dict[str, object]:
        return {
            "matcher": "*",
            "hooks": [
                {
                    "type": "command",
                    "command": (
                        f"curl -sS -X POST '{base_url}/api/hooks/{event}/{token}' "
                        f"--data-binary @-{terminator}"
                    ),
                }
            ],
        }

    payload = {
        "hooks": {
            "Notification": [hook("Notification")],
            "PreToolUse": [hook("PreToolUse", terminator="; exit 0")],
            "Stop": [hook("Stop")],
        }
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def write_settings_into_jail(worktree: Path, *, token: str, base_url: str) -> None:
    target = worktree / ".claude" / "settings.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build_settings_json(token=token, base_url=base_url), encoding="utf-8")
    target.chmod(0o644)


def remove_settings_from_jail(worktree: Path) -> None:
    target = worktree / ".claude" / "settings.json"
    target.unlink(missing_ok=True)


def ensure_gitignore_entry(worktree: Path) -> None:
    path = worktree / ".gitignore"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = existing.splitlines()
    if _GITIGNORE_LINE in lines:
        return
    suffix = "" if existing.endswith("\n") or not existing else "\n"
    path.write_text(existing + suffix + _GITIGNORE_LINE + "\n", encoding="utf-8")
```

- [ ] **Step 4: GREEN settings_writer**

Run: `uv run pytest tests/unit/test_aijail_settings_writer.py -v`
Expected: 10 passed.

- [ ] **Step 5: Atualizar `runtime.py` Protocol**

```python
# orchestrator/sandbox/runtime.py
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class JailHandle:
    id: str
    pid: int
    started_at: datetime


class SessionRuntime(Protocol):
    async def spawn(
        self,
        worktree: Path,
        *,
        token: str | None = None,
        base_url: str | None = None,
    ) -> JailHandle: ...

    async def kill(self, handle: JailHandle, *, worktree: Path | None = None) -> None: ...
```

- [ ] **Step 6: Atualizar `AiJailRuntime`**

Em `orchestrator/sandbox/aijail.py`, mudar `spawn` e `kill`:

```python
    async def spawn(
        self,
        worktree: Path,
        *,
        token: str | None = None,
        base_url: str | None = None,
    ) -> JailHandle:
        if token is not None and base_url is not None:
            from orchestrator.sandbox.settings_writer import (
                ensure_gitignore_entry,
                write_settings_into_jail,
            )
            write_settings_into_jail(worktree, token=token, base_url=base_url)
            ensure_gitignore_entry(worktree)
        terminal = self._terminal_resolver()
        inner = ["ai-jail", "run", "--", "claude"]
        cmd = build_terminal_command(terminal, inner)
        pid = self._process_ops.spawn(cmd, str(worktree))
        return JailHandle(id=uuid4().hex, pid=pid, started_at=datetime.now(UTC))

    async def kill(self, handle: JailHandle, *, worktree: Path | None = None) -> None:
        try:
            self._process_ops.kill(handle.pid)
        except ProcessLookupError:
            pass
        if worktree is not None:
            from orchestrator.sandbox.settings_writer import remove_settings_from_jail
            remove_settings_from_jail(worktree)
```

- [ ] **Step 7: Atualizar `NullSessionRuntime` pra Protocol compat**

```python
# orchestrator/sandbox/null.py — assinatura ampliada (kwargs ignorados)
class NullSessionRuntime:
    async def spawn(
        self, worktree: Path, *, token: str | None = None, base_url: str | None = None
    ) -> JailHandle:
        return JailHandle(id=uuid4().hex, pid=0, started_at=datetime.now(UTC))

    async def kill(self, handle: JailHandle, *, worktree: Path | None = None) -> None:
        return None
```

- [ ] **Step 8: Atualizar `start_session`/`stop_session` em `core/sessions.py`**

```python
from orchestrator.hooks.tokens import TokenRegistry, generate_token


async def start_session(
    session: AsyncSession,
    runtime: SessionRuntime,
    worktree_id: str,
    *,
    token_registry: TokenRegistry | None = None,
    base_url: str | None = None,
) -> ClaudeSession:
    worktree = await session.get(Worktree, worktree_id)
    if worktree is None:
        raise WorktreeNotFoundError(f"worktree not found: {worktree_id}")
    token = generate_token() if token_registry is not None else None
    handle = await runtime.spawn(Path(worktree.path), token=token, base_url=base_url)
    row = ClaudeSession(
        worktree_id=worktree_id,
        status=SessionStatus.EXECUTING,
        pid=handle.pid,
        jail_id=handle.id,
        started_at=handle.started_at,
        hook_token=token,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    if token_registry is not None and token is not None:
        token_registry.register(token, row.id)
    return row


async def stop_session(
    session: AsyncSession,
    runtime: SessionRuntime,
    session_id: str,
    *,
    token_registry: TokenRegistry | None = None,
) -> None:
    row = await session.get(ClaudeSession, session_id)
    if row is None:
        raise SessionNotFoundError(f"session not found: {session_id}")
    if row.status in _TERMINAL_STATUSES:
        return
    handle = _rehydrate_handle(row)
    worktree_row = await session.get(Worktree, row.worktree_id)
    worktree_path = Path(worktree_row.path) if worktree_row else None
    await runtime.kill(handle, worktree=worktree_path)
    row.status = SessionStatus.DONE
    row.ended_at = datetime.now(UTC)
    await session.commit()
    if token_registry is not None and row.hook_token is not None:
        token_registry.revoke(row.hook_token)
```

- [ ] **Step 8.5: Enumerar call sites de `runtime.spawned`/`runtime.killed` antes do refactor**

Run: `grep -rn 'runtime.spawned\|runtime.killed' tests/`
Expected: lista das ocorrências em `tests/integration/test_sessions_api.py`. Anotar cada `runtime.spawned[i]` que vira `runtime.spawned[i][0]` (primeiro elemento da tupla).

- [ ] **Step 9: Atualizar `FakeSessionRuntime` em `tests/integration/conftest.py`**

```python
class FakeSessionRuntime:
    def __init__(self) -> None:
        self.spawned: list[tuple[JailHandle, str | None, str | None]] = []
        self.killed: list[JailHandle] = []
        self._next_pid = 10000

    async def spawn(
        self, worktree: Path, *, token: str | None = None, base_url: str | None = None
    ) -> JailHandle:
        self._next_pid += 1
        handle = JailHandle(
            id=f"fake-{self._next_pid}",
            pid=self._next_pid,
            started_at=datetime.now(UTC),
        )
        self.spawned.append((handle, token, base_url))
        return handle

    async def kill(self, handle: JailHandle, *, worktree: Path | None = None) -> None:
        self.killed.append(handle)
```

E atualizar referências em tests integration que dependem de `runtime.spawned[0].pid` → `runtime.spawned[0][0].pid`. Procurar com:

```bash
grep -rn 'runtime.spawned\[' tests/integration
```

E ajustar conforme necessário.

- [ ] **Step 10: Suite completa pra confirmar não regrediu**

Run: `uv run pytest tests/unit tests/integration -m 'not e2e' -v`
Expected: tudo verde.

- [ ] **Step 11: Coverage**

Run: `uv run pytest tests/unit/test_aijail_settings_writer.py --cov=orchestrator.sandbox.settings_writer --cov-report=term-missing`
Expected: 100%.

Run: `uv run pytest tests/unit tests/integration -m 'not e2e' --cov=orchestrator --cov-report=term-missing`
Expected: 100% global.

- [ ] **Step 12: Code review** subagent.

- [ ] **Step 13: Commit**

```bash
git add orchestrator/sandbox/settings_writer.py orchestrator/sandbox/aijail.py orchestrator/sandbox/runtime.py orchestrator/sandbox/null.py orchestrator/core/sessions.py tests/unit/test_aijail_settings_writer.py tests/integration/conftest.py tests/integration/
git commit -m "$(cat <<'EOF'
feat(F2.e): settings.json injection + start/stop_session integram TokenRegistry

- settings_writer: build_settings_json, write/remove + ensure_gitignore_entry idempotente
- AiJailRuntime.spawn aceita token+base_url; kill remove settings.json
- start_session gera token e registra; stop_session revoga
- NullSessionRuntime mantém Protocol compat
EOF
)"
```

---

## Task 6 — F2.f: Production WsBroadcaster + Notifiers

**Files:**
- Create: `orchestrator/events/broadcaster.py`
- Create: `orchestrator/notifications/notify_send.py`
- Create: `tests/unit/test_in_memory_broadcaster.py`
- Create: `tests/unit/test_notify_send_notifier.py`

- [ ] **Step 1: Teste do broadcaster**

```python
# tests/unit/test_in_memory_broadcaster.py
import pytest

from orchestrator.events.broadcaster import InMemoryWsBroadcaster
from orchestrator.events.envelope import WsEvent


class FakeWebSocket:
    def __init__(self, *, fail: bool = False) -> None:
        self.received: list[dict[str, object]] = []
        self._fail = fail

    async def send_json(self, data: dict[str, object]) -> None:
        if self._fail:
            raise RuntimeError("client gone")
        self.received.append(data)


@pytest.mark.asyncio
async def test_publish_to_no_clients_is_noop() -> None:
    bc = InMemoryWsBroadcaster()
    await bc.publish(WsEvent.session_stopped(session_id="x"))


@pytest.mark.asyncio
async def test_publish_fans_out_to_all_subscribers() -> None:
    bc = InMemoryWsBroadcaster()
    a, b = FakeWebSocket(), FakeWebSocket()
    bc.subscribe(a); bc.subscribe(b)
    await bc.publish(WsEvent.session_stopped(session_id="x"))
    assert len(a.received) == 1 and len(b.received) == 1


@pytest.mark.asyncio
async def test_failing_subscriber_is_dropped() -> None:
    bc = InMemoryWsBroadcaster()
    bad = FakeWebSocket(fail=True)
    good = FakeWebSocket()
    bc.subscribe(bad); bc.subscribe(good)
    await bc.publish(WsEvent.session_stopped(session_id="x"))
    assert len(good.received) == 1
    assert bad not in bc.subscribers


@pytest.mark.asyncio
async def test_unsubscribe_removes_client() -> None:
    bc = InMemoryWsBroadcaster()
    a = FakeWebSocket()
    bc.subscribe(a)
    bc.unsubscribe(a)
    await bc.publish(WsEvent.session_stopped(session_id="x"))
    assert a.received == []
```

- [ ] **Step 2: RED**

Run: `uv run pytest tests/unit/test_in_memory_broadcaster.py -v`

- [ ] **Step 3: Implementação broadcaster**

```python
# orchestrator/events/broadcaster.py
import asyncio
from typing import Protocol

from orchestrator.events.envelope import WsEvent


class WsClient(Protocol):
    async def send_json(self, data: dict[str, object]) -> None: ...


class WsBroadcaster(Protocol):
    async def publish(self, event: WsEvent) -> None: ...


class InMemoryWsBroadcaster:
    def __init__(self) -> None:
        self._subs: set[WsClient] = set()

    @property
    def subscribers(self) -> frozenset[WsClient]:
        return frozenset(self._subs)

    def subscribe(self, client: WsClient) -> None:
        self._subs.add(client)

    def unsubscribe(self, client: WsClient) -> None:
        self._subs.discard(client)

    async def publish(self, event: WsEvent) -> None:
        if not self._subs:
            return
        payload = event.to_dict()
        clients = list(self._subs)
        results = await asyncio.gather(
            *(client.send_json(payload) for client in clients),
            return_exceptions=True,
        )
        for client, result in zip(clients, results, strict=False):
            if isinstance(result, Exception):
                self._subs.discard(client)
```

- [ ] **Step 4: GREEN broadcaster**

Run: `uv run pytest tests/unit/test_in_memory_broadcaster.py -v`
Expected: 4 passed.

- [ ] **Step 5: Teste do `notify-send`**

```python
# tests/unit/test_notify_send_notifier.py
import pytest

from orchestrator.notifications.notify_send import NoopNotifier, NotifySendNotifier


class FakeRunner:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[list[str]] = []
        self._fail = fail

    async def run(self, argv: list[str]) -> None:
        self.calls.append(argv)
        if self._fail:
            raise FileNotFoundError("notify-send")


@pytest.mark.asyncio
async def test_notify_send_invokes_command() -> None:
    runner = FakeRunner()
    notifier = NotifySendNotifier(runner=runner)
    await notifier.notify(summary="J-arvis · main", body="Aguarda você", icon="dialog-information")
    assert runner.calls == [
        ["notify-send", "--icon=dialog-information", "J-arvis · main", "Aguarda você"]
    ]


@pytest.mark.asyncio
async def test_notify_send_swallows_filenotfound() -> None:
    runner = FakeRunner(fail=True)
    notifier = NotifySendNotifier(runner=runner)
    await notifier.notify(summary="x", body="y", icon="i")
    await notifier.notify(summary="x", body="y", icon="i")
    assert len(runner.calls) == 2  # both attempts ran; failures didn't crash


@pytest.mark.asyncio
async def test_noop_notifier_does_nothing() -> None:
    await NoopNotifier().notify(summary="x", body="y", icon="i")
```

- [ ] **Step 6: RED**

Run: `uv run pytest tests/unit/test_notify_send_notifier.py -v`

- [ ] **Step 7: Implementação `notify_send.py`**

```python
# orchestrator/notifications/notify_send.py
import asyncio
import logging
from typing import Protocol


_log = logging.getLogger(__name__)


class CommandRunner(Protocol):
    async def run(self, argv: list[str]) -> None: ...


class SubprocessRunner:  # pragma: no cover
    """Production runner. Excluded from coverage: needs notify-send + libnotify
    on the host. Behaviour is exercised manually."""
    async def run(self, argv: list[str]) -> None:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()


class NotifySendNotifier:
    def __init__(self, *, runner: CommandRunner | None = None) -> None:
        self._runner = runner or SubprocessRunner()
        self._warned = False

    async def notify(self, *, summary: str, body: str, icon: str) -> None:
        argv = ["notify-send", f"--icon={icon}", summary, body]
        try:
            await self._runner.run(argv)
        except FileNotFoundError:
            if not self._warned:
                _log.warning("notify-send unavailable; further notifications silenced")
                self._warned = True


class NoopNotifier:
    async def notify(self, *, summary: str, body: str, icon: str) -> None:
        return None
```

- [ ] **Step 8: GREEN**

Run: `uv run pytest tests/unit/test_notify_send_notifier.py -v`

- [ ] **Step 9: Coverage**

Run: `uv run pytest tests/unit/test_in_memory_broadcaster.py tests/unit/test_notify_send_notifier.py --cov=orchestrator.events/broadcaster --cov=orchestrator.notifications/notify_send --cov-report=term-missing`
Expected: 100% (com `SubprocessRunner` em pragma: no cover, justificado).

- [ ] **Step 10: Code review** subagent.

- [ ] **Step 11: Commit**

```bash
git add orchestrator/events/broadcaster.py orchestrator/notifications/notify_send.py tests/unit/test_in_memory_broadcaster.py tests/unit/test_notify_send_notifier.py
git commit -m "$(cat <<'EOF'
feat(F2.f): InMemoryWsBroadcaster + NotifySendNotifier (production impls)

- Broadcaster: gather paralelo, drop de subscribers que falham send_json
- Notifier: warning único quando notify-send ausente; SubprocessRunner em pragma
EOF
)"
```

---

## Task 7 — F2.g: Hooks router (3 endpoints)

**Files:**
- Create: `orchestrator/hooks/router.py`
- Modify: `orchestrator/api/_deps.py`
- Modify: `orchestrator/main.py` (registra router; defaults None pros novos states)
- Create: `tests/integration/test_hooks_routes.py`
- Create: `tests/integration/test_hooks_concurrency.py`

- [ ] **Step 1: Teste integration das 3 rotas**

```python
# tests/integration/test_hooks_routes.py
from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.events.broadcaster import InMemoryWsBroadcaster
from orchestrator.hooks.tokens import TokenRegistry, generate_token
from orchestrator.main import create_app
from orchestrator.notifications.notify_send import NoopNotifier
from orchestrator.store.database import Database
from orchestrator.store.models import ClaudeSession, Project, Worktree
from tests.integration.conftest import FakeSessionRuntime


async def _seed(db: Database, status: str = "executing") -> tuple[str, str]:
    token = generate_token()
    async with db.session() as s:
        proj = Project(name="p", path="/tmp/p")
        s.add(proj)
        await s.commit()
        await s.refresh(proj)
        wt = Worktree(project_id=proj.id, path="/tmp/p/wt", branch="main")
        s.add(wt)
        await s.commit()
        await s.refresh(wt)
        sess = ClaudeSession(
            worktree_id=wt.id,
            status=status,
            pid=1,
            jail_id="j",
            started_at=datetime.now(UTC),
            hook_token=token,
        )
        s.add(sess)
        await s.commit()
        await s.refresh(sess)
        return sess.id, token


def _build_app(db: Database, registry, broadcaster, notifier):
    app = create_app(database=db, runtime=FakeSessionRuntime(), ui_dist=None)
    app.state.token_registry = registry
    app.state.ws_broadcaster = broadcaster
    app.state.notifier = notifier
    return app


@pytest.mark.integration
async def test_notification_unknown_token_returns_404(db: Database) -> None:
    app = _build_app(db, TokenRegistry(), InMemoryWsBroadcaster(), NoopNotifier())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post("/api/hooks/Notification/nope", json={"message": "x"})
    assert r.status_code == 404


@pytest.mark.integration
async def test_notification_mutates_status(db: Database) -> None:
    sid, token = await _seed(db)
    registry = TokenRegistry(); registry.register(token, sid)
    app = _build_app(db, registry, InMemoryWsBroadcaster(), NoopNotifier())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(f"/api/hooks/Notification/{token}", json={"message": "x"})
    assert r.status_code == 204
    async with db.session() as s:
        row = await s.get(ClaudeSession, sid)
        assert row.status == "awaiting_response"


@pytest.mark.integration
async def test_pretooluse_returns_continue_true(db: Database) -> None:
    sid, token = await _seed(db)
    registry = TokenRegistry(); registry.register(token, sid)
    app = _build_app(db, registry, InMemoryWsBroadcaster(), NoopNotifier())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            f"/api/hooks/PreToolUse/{token}",
            json={"tool_name": "Bash", "tool_input": {"command": "ls"}},
        )
    assert r.status_code == 200
    assert r.json() == {"continue": True}


@pytest.mark.integration
async def test_stop_hook_sets_idle(db: Database) -> None:
    sid, token = await _seed(db)
    registry = TokenRegistry(); registry.register(token, sid)
    app = _build_app(db, registry, InMemoryWsBroadcaster(), NoopNotifier())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(f"/api/hooks/Stop/{token}", json={"reason": "end"})
    assert r.status_code == 204
    async with db.session() as s:
        row = await s.get(ClaudeSession, sid)
        assert row.status == "idle"


@pytest.mark.integration
async def test_notification_malformed_payload_returns_422(db: Database) -> None:
    sid, token = await _seed(db)
    registry = TokenRegistry(); registry.register(token, sid)
    app = _build_app(db, registry, InMemoryWsBroadcaster(), NoopNotifier())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(f"/api/hooks/Notification/{token}", json={})
    assert r.status_code == 422


@pytest.mark.integration
async def test_status_change_publishes_ws_event(db: Database) -> None:
    sid, token = await _seed(db)
    registry = TokenRegistry(); registry.register(token, sid)
    bc = InMemoryWsBroadcaster()
    received: list[dict] = []
    class Cap:
        async def send_json(self, data: dict) -> None: received.append(data)
    bc.subscribe(Cap())

    app = _build_app(db, registry, bc, NoopNotifier())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        await client.post(f"/api/hooks/Notification/{token}", json={"message": "x"})

    assert len(received) == 1
    assert received[0]["type"] == "session.status"
    assert received[0]["payload"]["status"] == "awaiting_response"
```

- [ ] **Step 2: RED**

Run: `uv run pytest tests/integration/test_hooks_routes.py -v`

- [ ] **Step 3: Resolvers em `_deps.py`**

Append a `orchestrator/api/_deps.py`:

```python
from orchestrator.events.broadcaster import WsBroadcaster
from orchestrator.hooks.tokens import TokenRegistry
from orchestrator.notifications.sink import NotifierSink


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
```

- [ ] **Step 4: Implementação router**

```python
# orchestrator/hooks/router.py
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.api._deps import (
    get_db_session,
    resolve_broadcaster,
    resolve_notifier,
    resolve_token_registry,
)
from orchestrator.core.sessions import SessionStatus, bump_last_hook_at, update_status
from orchestrator.events.broadcaster import WsBroadcaster
from orchestrator.events.envelope import WsEvent
from orchestrator.hooks.parser import (
    InvalidHookPayloadError,
    parse_notification,
    parse_pretooluse,
    parse_stop,
)
from orchestrator.hooks.tokens import TokenRegistry
from orchestrator.notifications.sink import NotifierSink, should_notify
from orchestrator.store.models import ClaudeSession, Project, Worktree

_log = logging.getLogger(__name__)
router = APIRouter()


def _notify_text(s: SessionStatus) -> tuple[str, str]:
    if s == SessionStatus.AWAITING_RESPONSE:
        return "Aguarda você", "dialog-information"
    return "Concluído", "emblem-default"


async def _summary(session: AsyncSession, session_id: str) -> str:
    row = await session.get(ClaudeSession, session_id)
    if row is None:  # pragma: no cover
        return "?"
    wt = await session.get(Worktree, row.worktree_id)
    if wt is None:  # pragma: no cover
        return "?"
    proj = await session.get(Project, wt.project_id)
    name = proj.name if proj else "?"
    branch = wt.branch or "(detached)"
    return f"J-arvis · {name} · {branch}"


async def _resolve_or_404(token: str, registry: TokenRegistry) -> str:
    sid = registry.resolve(token)
    if sid is None:
        raise HTTPException(status_code=404)
    return sid


@router.post("/hooks/Notification/{token}", status_code=204)
async def hook_notification(
    token: str,
    payload: dict[str, Any],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    registry: Annotated[TokenRegistry, Depends(resolve_token_registry)],
    broadcaster: Annotated[WsBroadcaster, Depends(resolve_broadcaster)],
    notifier: Annotated[NotifierSink, Depends(resolve_notifier)],
) -> None:
    sid = await _resolve_or_404(token, registry)
    try:
        new_status = parse_notification(payload)
    except InvalidHookPayloadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    prev, new = await update_status(db, sid, new_status)
    if prev != new:
        await broadcaster.publish(
            WsEvent.session_status(session_id=sid, new_status=new, previous_status=prev)
        )
    if should_notify(prev, new):
        body, icon = _notify_text(new)
        await notifier.notify(summary=await _summary(db, sid), body=body, icon=icon)


@router.post("/hooks/PreToolUse/{token}")
async def hook_pretooluse(
    token: str,
    payload: dict[str, Any],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    registry: Annotated[TokenRegistry, Depends(resolve_token_registry)],
    broadcaster: Annotated[WsBroadcaster, Depends(resolve_broadcaster)],
) -> dict[str, bool]:
    sid = await _resolve_or_404(token, registry)
    try:
        tool = parse_pretooluse(payload)
    except InvalidHookPayloadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await bump_last_hook_at(db, sid)
    await broadcaster.publish(WsEvent.session_tool_use(session_id=sid, tool=tool))
    return {"continue": True}


@router.post("/hooks/Stop/{token}", status_code=204)
async def hook_stop(
    token: str,
    payload: dict[str, Any],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    registry: Annotated[TokenRegistry, Depends(resolve_token_registry)],
    broadcaster: Annotated[WsBroadcaster, Depends(resolve_broadcaster)],
    notifier: Annotated[NotifierSink, Depends(resolve_notifier)],
) -> None:
    sid = await _resolve_or_404(token, registry)
    new_status = parse_stop(payload)
    prev, new = await update_status(db, sid, new_status)
    if prev != new:
        await broadcaster.publish(
            WsEvent.session_status(session_id=sid, new_status=new, previous_status=prev)
        )
        await broadcaster.publish(WsEvent.session_stopped(session_id=sid))
    if should_notify(prev, new):
        await notifier.notify(summary=await _summary(db, sid), body="Concluído", icon="emblem-default")
```

- [ ] **Step 5: Registrar router em `main.py`**

Edit `create_app` em `orchestrator/main.py`, dentro do `if database is not None:`:

```python
        from orchestrator.hooks.router import router as hooks_router
        app.include_router(hooks_router, prefix="/api")
```

E inicializar defaults pros novos `app.state` (em `create_app`, antes do `if database`):

```python
    app.state.database = database
    app.state.runtime = runtime
    app.state.token_registry = getattr(app.state, "token_registry", None)
    app.state.ws_broadcaster = getattr(app.state, "ws_broadcaster", None)
    app.state.notifier = getattr(app.state, "notifier", None)
    app.state.hook_base_url = getattr(app.state, "hook_base_url", None)
```

- [ ] **Step 6: GREEN**

Run: `uv run pytest tests/integration/test_hooks_routes.py -v`
Expected: 6 passed.

- [ ] **Step 7: Teste concorrência**

```python
# tests/integration/test_hooks_concurrency.py
import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.events.broadcaster import InMemoryWsBroadcaster
from orchestrator.hooks.tokens import TokenRegistry
from orchestrator.main import create_app
from orchestrator.notifications.notify_send import NoopNotifier
from orchestrator.store.database import Database
from orchestrator.store.models import ClaudeSession
from tests.integration.conftest import FakeSessionRuntime
from tests.integration.test_hooks_routes import _seed


@pytest.mark.integration
async def test_concurrent_hooks_do_not_corrupt_state(db: Database) -> None:
    sid, token = await _seed(db)
    registry = TokenRegistry(); registry.register(token, sid)
    app = create_app(database=db, runtime=FakeSessionRuntime(), ui_dist=None)
    app.state.token_registry = registry
    app.state.ws_broadcaster = InMemoryWsBroadcaster()
    app.state.notifier = NoopNotifier()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        await asyncio.gather(*[
            client.post(f"/api/hooks/Notification/{token}", json={"message": "x"})
            for _ in range(10)
        ])

    async with db.session() as s:
        row = await s.get(ClaudeSession, sid)
        assert row.status == "awaiting_response"
        assert row.last_hook_at is not None
```

- [ ] **Step 8: GREEN concorrência**

Run: `uv run pytest tests/integration/test_hooks_concurrency.py -v`

- [ ] **Step 9: Coverage**

Run: `uv run pytest tests/unit tests/integration -m 'not e2e' --cov=orchestrator --cov-report=term-missing`
Expected: 100% global.

- [ ] **Step 10: Code review** subagent.

- [ ] **Step 11: Commit**

```bash
git add orchestrator/hooks/router.py orchestrator/api/_deps.py orchestrator/main.py tests/integration/test_hooks_routes.py tests/integration/test_hooks_concurrency.py
git commit -m "$(cat <<'EOF'
feat(F2.g): hook router com 3 endpoints (Notification, PreToolUse, Stop)

- 404 token desconhecido; 422 payload malformado
- update_status idempotente; WS event só quando prev != new
- Notify só em transições * → AWAITING_RESPONSE/IDLE
- PreToolUse audit-only (F3 traz fila e bloqueio)
EOF
)"
```

---

## Task 8 — F2.h: WebSocket endpoint

**Files:**
- Create: `orchestrator/api/ws.py`
- Modify: `orchestrator/main.py`
- Create: `tests/integration/test_ws_endpoint.py`

- [ ] **Step 1: Teste WS**

> **Nota de design do teste:** mistura de `TestClient` sync com `asyncio.run_until_complete` em outra thread quebra (loop diferente). A estratégia robusta: usar o mesmo `TestClient` pra **conectar o WS e disparar uma rota HTTP** que internamente chama `broadcaster.publish`. Tanto o WS quanto a rota rodam no event loop do `TestClient`, então a entrega é determinística. Aproveitamos o hook router já existente — POST `/api/hooks/Notification/<token>` faz o publish do `session.status`.

```python
# tests/integration/test_ws_endpoint.py
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from orchestrator.events.broadcaster import InMemoryWsBroadcaster
from orchestrator.hooks.tokens import TokenRegistry, generate_token
from orchestrator.main import create_app
from orchestrator.notifications.notify_send import NoopNotifier
from orchestrator.store.database import Database
from orchestrator.store.models import ClaudeSession, Project, Worktree
from tests.integration.conftest import FakeSessionRuntime


async def _seed_session_with_token(db: Database) -> tuple[str, str]:
    token = generate_token()
    async with db.session() as s:
        proj = Project(name="p", path="/tmp/p"); s.add(proj); await s.commit(); await s.refresh(proj)
        wt = Worktree(project_id=proj.id, path="/tmp/p/wt", branch="main")
        s.add(wt); await s.commit(); await s.refresh(wt)
        sess = ClaudeSession(
            worktree_id=wt.id, status="executing", pid=1, jail_id="j",
            started_at=datetime.now(UTC), hook_token=token,
        )
        s.add(sess); await s.commit(); await s.refresh(sess)
        return sess.id, token


@pytest.mark.integration
async def test_ws_receives_status_event_when_hook_fires(db: Database) -> None:
    sid, token = await _seed_session_with_token(db)
    bc = InMemoryWsBroadcaster()
    registry = TokenRegistry(); registry.register(token, sid)
    app = create_app(database=db, runtime=FakeSessionRuntime(), ui_dist=None)
    app.state.token_registry = registry
    app.state.ws_broadcaster = bc
    app.state.notifier = NoopNotifier()

    # TestClient é sync mas roda app em loop dedicado; ws + POST compartilham loop.
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            r = client.post(f"/api/hooks/Notification/{token}", json={"message": "x"})
            assert r.status_code == 204
            data = ws.receive_json()
    assert data["type"] == "session.status"
    assert data["session_id"] == sid
    assert data["payload"]["status"] == "awaiting_response"


@pytest.mark.integration
async def test_ws_unsubscribes_on_disconnect(db: Database) -> None:
    sid, token = await _seed_session_with_token(db)
    bc = InMemoryWsBroadcaster()
    registry = TokenRegistry(); registry.register(token, sid)
    app = create_app(database=db, runtime=FakeSessionRuntime(), ui_dist=None)
    app.state.token_registry = registry
    app.state.ws_broadcaster = bc
    app.state.notifier = NoopNotifier()

    with TestClient(app) as client:
        with client.websocket_connect("/ws"):
            pass  # immediate disconnect
    # subscribers list should be empty after the WS context exits
    assert len(bc.subscribers) == 0
```

> O 1º teste exige que F2.g (hooks router) já esteja mergeado — Task 8 corre depois de Task 7, então isso está garantido.

- [ ] **Step 2: RED**

Run: `uv run pytest tests/integration/test_ws_endpoint.py -v`

- [ ] **Step 3: Implementação `api/ws.py`**

```python
# orchestrator/api/ws.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    broadcaster = websocket.app.state.ws_broadcaster
    if broadcaster is None:  # pragma: no cover
        await websocket.close(code=1011)
        return
    await websocket.accept()
    broadcaster.subscribe(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        return
    finally:
        broadcaster.unsubscribe(websocket)
```

- [ ] **Step 4: Registrar em `main.py`**

```python
        from orchestrator.api.ws import router as ws_router
        app.include_router(ws_router)  # /ws no root, sem prefix /api
```

- [ ] **Step 5: GREEN**

Run: `uv run pytest tests/integration/test_ws_endpoint.py -v`

- [ ] **Step 6: Coverage**

Run: `uv run pytest tests/integration/test_ws_endpoint.py --cov=orchestrator.api.ws --cov-report=term-missing`
Expected: 100% (com pragma se inalcançável).

- [ ] **Step 7: Code review** subagent.

- [ ] **Step 8: Commit**

```bash
git add orchestrator/api/ws.py orchestrator/main.py tests/integration/test_ws_endpoint.py
git commit -m "$(cat <<'EOF'
feat(F2.h): WebSocket endpoint /ws com subscribe → broadcaster

Cliente conectado recebe envelope JSON em todo broadcaster.publish.
Sem auth (local-only single-user, ADR-0001).
EOF
)"
```

---

## Task 9 — F2.i: Production wiring (config + main + sessions route)

**Files:**
- Modify: `orchestrator/config.py`
- Modify: `orchestrator/main.py`
- Modify: `orchestrator/api/sessions.py`
- Create: `tests/integration/test_session_lifecycle_with_hooks.py`

- [ ] **Step 1: Atualizar `config.py`**

```python
# orchestrator/config.py
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

RuntimeMode = Literal["aijail", "null"]
NotifyMode = Literal["on", "off"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JARVIS_", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./jarvis.db"
    runtime: RuntimeMode = "aijail"
    ui_dist: Path = Path("/app/ui-dist")
    port: int = 8765
    notify: NotifyMode = "on"
    hook_base_url: str | None = None

    @property
    def effective_hook_base_url(self) -> str:
        return self.hook_base_url or f"http://localhost:{self.port}"
```

> **Nota:** `BaseSettings` com `env_prefix="JARVIS_"` mapeia automaticamente cada campo: `port` → `JARVIS_PORT`, `notify` → `JARVIS_NOTIFY`, `hook_base_url` → `JARVIS_HOOK_BASE_URL`. Sem necessidade de declarar env vars manualmente.

- [ ] **Step 2: Wire production em `_build_production_app`**

```python
# orchestrator/main.py
def _build_production_app() -> FastAPI:
    settings = Settings()
    database = Database(settings.database_url)
    runtime = build_runtime(settings.runtime)
    ui_dist = settings.ui_dist if settings.ui_dist.is_dir() else None

    from orchestrator.events.broadcaster import InMemoryWsBroadcaster
    from orchestrator.hooks.tokens import TokenRegistry
    from orchestrator.notifications.notify_send import NoopNotifier, NotifySendNotifier

    broadcaster = InMemoryWsBroadcaster()
    registry = TokenRegistry()
    notifier = NotifySendNotifier() if settings.notify == "on" else NoopNotifier()

    app = create_app(database=database, runtime=runtime, ui_dist=ui_dist)
    app.state.token_registry = registry
    app.state.ws_broadcaster = broadcaster
    app.state.notifier = notifier
    app.state.hook_base_url = settings.effective_hook_base_url
    return app
```

- [ ] **Step 3: Atualizar `api/sessions.py`**

> Adicionar `Request` ao import: `from fastapi import APIRouter, Depends, HTTPException, Request, Response`.

Em `POST /sessions`:

```python
async def create_session(
    body: StartSessionBody,
    runtime: Annotated[SessionRuntime, Depends(resolve_runtime)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    request: Request,
) -> SessionResponse:
    registry = request.app.state.token_registry
    base_url = request.app.state.hook_base_url
    try:
        row = await sessions.start_session(
            db, runtime, body.worktree_id,
            token_registry=registry, base_url=base_url,
        )
    except sessions.WorktreeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SessionResponse.from_row(row)
```

E em `POST /sessions/{id}/stop`:

```python
async def stop_session_route(
    session_id: str,
    runtime: Annotated[SessionRuntime, Depends(resolve_runtime)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    request: Request,
) -> Response:
    registry = request.app.state.token_registry
    try:
        await sessions.stop_session(db, runtime, session_id, token_registry=registry)
    except sessions.SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)
```

- [ ] **Step 4: Teste lifecycle**

```python
# tests/integration/test_session_lifecycle_with_hooks.py
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.events.broadcaster import InMemoryWsBroadcaster
from orchestrator.hooks.tokens import TokenRegistry
from orchestrator.main import create_app
from orchestrator.notifications.notify_send import NoopNotifier
from orchestrator.store.database import Database
from tests.integration.conftest import FakeSessionRuntime
from tests.integration.test_sessions_api import _make_repo, _create_project_and_worktree


@pytest.mark.integration
async def test_lifecycle_with_hooks(db: Database, tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    runtime = FakeSessionRuntime()
    bc = InMemoryWsBroadcaster()
    registry = TokenRegistry()
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    app.state.token_registry = registry
    app.state.ws_broadcaster = bc
    app.state.notifier = NoopNotifier()
    app.state.hook_base_url = "http://localhost:8765"

    received: list[dict] = []
    class Cap:
        async def send_json(self, data: dict) -> None: received.append(data)
    bc.subscribe(Cap())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        _, wt_id = await _create_project_and_worktree(client, repo)
        sess = (await client.post("/api/sessions", json={"worktree_id": wt_id})).json()
        sid = sess["id"]
        token = next(t for t, s in registry._map.items() if s == sid)

        await client.post(f"/api/hooks/Notification/{token}", json={"message": "?"})
        await client.post(f"/api/hooks/Stop/{token}", json={"reason": "end"})
        await client.post(f"/api/sessions/{sid}/stop")

    types = [e["type"] for e in received]
    assert types == ["session.status", "session.status", "session.stopped"]
    assert registry.resolve(token) is None
```

- [ ] **Step 5: GREEN suite completa**

Run: `uv run pytest tests/unit tests/integration -m 'not e2e' -v`
Expected: tudo verde, coverage 100%.

- [ ] **Step 6: Code review** subagent.

- [ ] **Step 7: Commit**

```bash
git add orchestrator/config.py orchestrator/main.py orchestrator/api/sessions.py tests/integration/test_session_lifecycle_with_hooks.py
git commit -m "$(cat <<'EOF'
feat(F2.i): production wiring (config + main + sessions route)

- Settings ganha port (8765), notify (on/off), hook_base_url derivado
- _build_production_app injeta InMemoryWsBroadcaster + TokenRegistry + Notifier
- /api/sessions passa registry+base_url; stop revoga token
- Lifecycle test: start → Notification → Stop → stop_session = 3 eventos WS
EOF
)"
```

---

## Task 10 — F2.j: UI — WS connection + dispatch

**Files:**
- Create: `ui/src/lib/ws.ts`
- Create: `ui/src/lib/events.ts`
- Create: `ui/src/hooks/useSessionEvents.ts`
- Create: `ui/src/lib/ws.test.ts`
- Create: `ui/src/lib/events.test.ts`
- Create: `ui/src/hooks/useSessionEvents.test.ts`
- Modify: `ui/src/App.tsx`

- [ ] **Step 1: Teste `ws.ts`**

```ts
// ui/src/lib/ws.test.ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { connectWs } from './ws';

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  onopen: ((this: WebSocket, ev: Event) => unknown) | null = null;
  onmessage: ((this: WebSocket, ev: MessageEvent) => unknown) | null = null;
  onclose: ((this: WebSocket, ev: CloseEvent) => unknown) | null = null;
  onerror: ((this: WebSocket, ev: Event) => unknown) | null = null;
  readyState = 0;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }
  close = vi.fn(() => { this.readyState = 3; this.onclose?.(new CloseEvent('close')); });
  send = vi.fn();
}

beforeEach(() => {
  MockWebSocket.instances = [];
  vi.stubGlobal('WebSocket', MockWebSocket as unknown as typeof WebSocket);
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('connectWs', () => {
  it('opens to /ws relative to current host', () => {
    connectWs(() => {});
    expect(MockWebSocket.instances[0].url).toMatch(/\/ws$/);
  });

  it('forwards parsed JSON messages to onEvent', () => {
    const onEvent = vi.fn();
    connectWs(onEvent);
    const ws = MockWebSocket.instances[0];
    ws.onmessage?.(new MessageEvent('message', {
      data: '{"type":"session.status","session_id":"x","payload":{},"at":"2026-05-09T00:00:00Z"}',
    }));
    expect(onEvent).toHaveBeenCalledOnce();
    expect(onEvent.mock.calls[0][0].type).toBe('session.status');
  });

  it('ignores non-JSON messages', () => {
    const onEvent = vi.fn();
    connectWs(onEvent);
    const ws = MockWebSocket.instances[0];
    ws.onmessage?.(new MessageEvent('message', { data: 'not-json' }));
    expect(onEvent).not.toHaveBeenCalled();
  });

  it('reconnects with backoff after close', () => {
    connectWs(() => {});
    const first = MockWebSocket.instances[0];
    first.onclose?.(new CloseEvent('close'));
    vi.advanceTimersByTime(1000);
    expect(MockWebSocket.instances).toHaveLength(2);
  });

  it('disconnect() stops reconnect loop', () => {
    const conn = connectWs(() => {});
    conn.disconnect();
    const first = MockWebSocket.instances[0];
    first.onclose?.(new CloseEvent('close'));
    vi.advanceTimersByTime(5000);
    expect(MockWebSocket.instances).toHaveLength(1);
  });
});
```

- [ ] **Step 2: RED**

Run: `pnpm --dir ui test --run src/lib/ws.test.ts`

- [ ] **Step 3: Implementação `ws.ts`**

```ts
// ui/src/lib/ws.ts
import type { WsEvent } from './events';

export type WsConnection = { disconnect: () => void };

const BASE_DELAY_MS = 1000;
const MAX_DELAY_MS = 30000;

export function connectWs(onEvent: (event: WsEvent) => void): WsConnection {
  let stopped = false;
  let socket: WebSocket | null = null;
  let attempts = 0;

  function open(): void {
    if (stopped) return;
    const url = `${location.protocol.replace('http', 'ws')}//${location.host}/ws`;
    socket = new WebSocket(url);
    socket.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data) as WsEvent;
        onEvent(data);
      } catch {
        // non-JSON or malformed; drop silently
      }
    };
    socket.onclose = () => {
      if (stopped) return;
      attempts += 1;
      const delay = Math.min(BASE_DELAY_MS * 2 ** (attempts - 1), MAX_DELAY_MS);
      setTimeout(open, delay);
    };
    socket.onopen = () => { attempts = 0; };
  }

  open();

  return {
    disconnect: () => {
      stopped = true;
      socket?.close();
    },
  };
}
```

- [ ] **Step 4: Teste `events.ts`**

```ts
// ui/src/lib/events.test.ts
import { describe, expect, it, vi } from 'vitest';
import { dispatch, type WsEvent } from './events';

describe('dispatch', () => {
  it('calls handler matching type', () => {
    const onStatus = vi.fn();
    const event: WsEvent = {
      type: 'session.status', session_id: 'x',
      payload: { status: 'idle', previous: 'executing' }, at: '...',
    };
    dispatch(event, { 'session.status': onStatus });
    expect(onStatus).toHaveBeenCalledWith(event);
  });

  it('does nothing for unknown type', () => {
    const handler = vi.fn();
    // @ts-expect-error testing unknown type at runtime
    dispatch({ type: 'session.unknown', session_id: 'x', payload: {}, at: '' },
             { 'session.status': handler });
    expect(handler).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 5: Implementação `events.ts`**

```ts
// ui/src/lib/events.ts
export type WsEvent =
  | { type: 'session.status';   session_id: string; payload: { status: string; previous: string }; at: string }
  | { type: 'session.tool_use'; session_id: string; payload: { tool: string };                     at: string }
  | { type: 'session.stopped';  session_id: string; payload: Record<string, never>;               at: string };

export type WsHandlers = {
  [K in WsEvent['type']]?: (event: Extract<WsEvent, { type: K }>) => void;
};

export function dispatch(event: WsEvent, handlers: WsHandlers): void {
  const handler = handlers[event.type];
  if (handler) {
    (handler as (e: WsEvent) => void)(event);
  }
}
```

- [ ] **Step 6: GREEN ws + events**

Run: `pnpm --dir ui test --run src/lib/ws.test.ts src/lib/events.test.ts`

- [ ] **Step 7: Teste `useSessionEvents.ts`**

```ts
// ui/src/hooks/useSessionEvents.test.ts
import { QueryClient } from '@tanstack/react-query';
import { renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { queryKeys } from '../lib/query-keys';
import { useSessionEvents } from './useSessionEvents';

const connectMock = vi.fn();
vi.mock('../lib/ws', () => ({
  connectWs: (onEvent: (e: unknown) => void) => {
    connectMock(onEvent);
    return { disconnect: vi.fn() };
  },
}));

beforeEach(() => connectMock.mockReset());

describe('useSessionEvents', () => {
  it('invalidates sessions queries on session.status', () => {
    const qc = new QueryClient();
    const invalidate = vi.spyOn(qc, 'invalidateQueries');
    renderHook(() => useSessionEvents(qc));
    const onEvent = connectMock.mock.calls[0][0] as (e: unknown) => void;
    onEvent({ type: 'session.status', session_id: 'x', payload: { status: 'idle', previous: 'executing' }, at: '' });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.sessions });
  });

  it('invalidates on session.stopped too', () => {
    const qc = new QueryClient();
    const invalidate = vi.spyOn(qc, 'invalidateQueries');
    renderHook(() => useSessionEvents(qc));
    const onEvent = connectMock.mock.calls[0][0] as (e: unknown) => void;
    onEvent({ type: 'session.stopped', session_id: 'x', payload: {}, at: '' });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.sessions });
  });
});
```

- [ ] **Step 8: Implementação hook**

```ts
// ui/src/hooks/useSessionEvents.ts
import type { QueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';

import { dispatch } from '../lib/events';
import { queryKeys } from '../lib/query-keys';
import { connectWs } from '../lib/ws';

export function useSessionEvents(queryClient: QueryClient): void {
  useEffect(() => {
    const conn = connectWs((event) => {
      dispatch(event, {
        'session.status': () => {
          queryClient.invalidateQueries({ queryKey: queryKeys.sessions });
        },
        'session.stopped': () => {
          queryClient.invalidateQueries({ queryKey: queryKeys.sessions });
        },
      });
    });
    return () => conn.disconnect();
  }, [queryClient]);
}
```

- [ ] **Step 9: GREEN hook**

Run: `pnpm --dir ui test --run src/hooks/useSessionEvents.test.ts`

- [ ] **Step 10: Integrar em `App.tsx`**

> **Cuidado:** `App.tsx` tem ~200 linhas (existing components abaixo do `App` shell). **NÃO** sobrescrever o arquivo inteiro — fazer 3 edits cirúrgicos:

**Edit 1** — adicionar 2 imports no topo do `App.tsx` (junto com os outros imports React/TanStack):

```tsx
import { useQueryClient } from '@tanstack/react-query';
import { useSessionEvents } from './hooks/useSessionEvents';
```

**Edit 2** — dentro da função `App()` existente (atualmente entre linhas ~13-20), adicionar 2 linhas no topo do corpo, antes do `return`:

```tsx
  const queryClient = useQueryClient();
  useSessionEvents(queryClient);
```

**Edit 3** — não há outras mudanças. Todos os componentes abaixo (`ProjectsSection`, `AddProjectForm`, `ProjectItem`, `WorktreeItem`, `SessionsSection`, `SessionItem`) ficam intactos.

Verificar com `git diff ui/src/App.tsx` que apenas 4 linhas foram adicionadas.

- [ ] **Step 11: Suite Vitest completa**

Run: `pnpm --dir ui test --run`
Expected: tudo verde, 18+ tests anteriores + 8+ novos.

Run: `pnpm --dir ui test --run --coverage`
Expected: 100% sobre `lib/ws.ts`, `lib/events.ts`, `hooks/useSessionEvents.ts`.

- [ ] **Step 12: Code review** subagent.

- [ ] **Step 13: Commit**

```bash
git add ui/src/lib/ws.ts ui/src/lib/events.ts ui/src/hooks/ ui/src/App.tsx ui/src/lib/ws.test.ts ui/src/lib/events.test.ts
git commit -m "$(cat <<'EOF'
feat(F2.j): UI conecta ao /ws e invalida sessions queries em status events

- connectWs com reconnect+backoff exponencial; ignora payloads não-JSON
- events.dispatch tipado por discriminated union
- useSessionEvents: TanStack Query invalida ['sessions'] em session.status / session.stopped
EOF
)"
```

---

## Task 11 — F2.k: E2E flow

**Files:**
- Create: `tests/e2e/test_hooks_e2e_flow.py`
- Modify: `tests/e2e/conftest.py` (set `JARVIS_DEBUG=1` no container)
- Modify: `orchestrator/main.py` (debug endpoint condicional, em pragma: no cover)

> O E2E **não** roda Claude real nem ai-jail dentro do container CI. Estratégia: o teste obtém o `hook_token` da sessão via um endpoint de debug montado só quando `JARVIS_DEBUG=1`, e simula a chamada do hook fazendo `fetch()` no próprio browser do Playwright (que está conectado ao mesmo daemon). Tudo bate no loopback dentro do container — o pattern de "rodar comando dentro do container do daemon" já existe em `tests/e2e/conftest.py` (fixture `orchestrator_with_repo` cria repo via shell dentro do container) — seguir o mesmo padrão se preferir o curl ao invés do `fetch`.

- [ ] **Step 1: Adicionar debug endpoint condicional em `main.py`**

> Adicionar `Request` e `HTTPException` ao import do FastAPI: `from fastapi import FastAPI, HTTPException, Request`.

```python
# orchestrator/main.py — em create_app, dentro do if database is not None:
import os
if os.environ.get("JARVIS_DEBUG") == "1":  # pragma: no cover
    @app.get("/api/_debug/token/{session_id}")
    async def _debug_token(session_id: str, request: Request) -> dict:
        registry = request.app.state.token_registry
        for token, sid in registry._map.items():
            if sid == session_id:
                return {"token": token}
        raise HTTPException(status_code=404)
```

> Pragma: no cover é justificado — é caminho de teste E2E, não cobrado pelo gate de unit/integration.

- [ ] **Step 2: Atualizar `tests/e2e/conftest.py`**

Em ambos os fixtures (`orchestrator_url` e `orchestrator_with_repo`), adicionar `.with_env("JARVIS_DEBUG", "1")` na construção do `DockerContainer`. Exemplo (ajustar ao código atual):

```python
container = (
    DockerContainer(str(orchestrator_image))
    .with_exposed_ports(8000)
    .with_env("JARVIS_RUNTIME", "null")
    .with_env("JARVIS_DEBUG", "1")
    .waiting_for(wait)
)
```

- [ ] **Step 3: Teste E2E**

```python
# tests/e2e/test_hooks_e2e_flow.py
import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
def test_hooks_e2e_status_changes_via_simulated_hook(
    page: Page, orchestrator_with_repo: tuple[str, str]
) -> None:
    url, repo_path = orchestrator_with_repo

    page.goto(url)
    expect(page).to_have_title("J-arvis")

    page.get_by_label("project-name").fill("demo")
    page.get_by_label("project-path").fill(repo_path)
    page.get_by_role("button", name="Adicionar projeto").click()
    expect(page.get_by_role("heading", name="demo")).to_be_visible()

    page.get_by_label("start-main").click()
    expect(page.get_by_text("Em execução")).to_be_visible()

    sessions_resp = page.evaluate("async () => (await fetch('/api/sessions')).json()")
    sid = sessions_resp[0]["id"]
    debug_resp = page.evaluate(
        f"async () => (await fetch('/api/_debug/token/{sid}')).json()"
    )
    token = debug_resp["token"]

    page.evaluate(
        "async (t) => fetch(`/api/hooks/Notification/${t}`,"
        " { method: 'POST', headers: { 'Content-Type': 'application/json' },"
        "   body: JSON.stringify({ message: 'need input' }) })",
        token,
    )
    expect(page.get_by_text("Aguardando resposta")).to_be_visible()

    page.evaluate(
        "async (t) => fetch(`/api/hooks/Stop/${t}`,"
        " { method: 'POST', headers: { 'Content-Type': 'application/json' },"
        "   body: JSON.stringify({ reason: 'end' }) })",
        token,
    )
    expect(page.get_by_text("Ocioso")).to_be_visible()
```

- [ ] **Step 4: Build da imagem + rodar E2E**

Run: `uv run pytest tests/e2e/test_hooks_e2e_flow.py -v`
Expected: passed (1ª build do container leva 2-5min; reusos do cache são rápidos).

- [ ] **Step 5: Suite full final**

Run: `uv run pytest -v`
Expected: tudo verde (unit + integration + e2e).

Run: `pnpm --dir ui test --run`
Expected: tudo verde.

- [ ] **Step 6: Code review** subagent.

- [ ] **Step 7: Commit**

```bash
git add tests/e2e/test_hooks_e2e_flow.py tests/e2e/conftest.py orchestrator/main.py
git commit -m "$(cat <<'EOF'
feat(F2.k): E2E flow — UI muda status via fetch simulando hook

- Debug endpoint /api/_debug/token/<id> habilitado por JARVIS_DEBUG=1 (pragma)
- Fixture E2E seta JARVIS_DEBUG no container
- Playwright: add project → start → simulate Notification → "Aguardando resposta" → Stop → "Ocioso"
EOF
)"
```

---

## Task 12 — F2.l: ADRs + ARCHITECTURE.md updates

**Files:**
- Create: `docs/adr/0009-hooks-via-settings-no-jail.md`
- Create: `docs/adr/0010-websocket-canal-unico-envelope-tipado.md`
- Modify: `docs/adr/README.md`
- Modify: `ARCHITECTURE.md` (§4 + §13)

- [ ] **Step 1: Criar ADR-0009**

Conteúdo (Status: Accepted, Data: 2026-05-09, Decisores: Marcos):

- **Contexto:** Claude Code precisa ser instruído a chamar nossos endpoints quando dispara hooks. Quatro alternativas foram consideradas (settings global do user, settings por worktree, wrapper shim do binário `claude`, settings dentro do `.ai-jail`).
- **Decisão:** daemon escreve `<worktree>/.claude/settings.json` antes do `ai-jail run`. ai-jail bind-monta o path no mesmo path absoluto dentro da jaula, então Claude Code lê o arquivo a partir do `cwd`. Daemon remove o settings.json em `stop_session` ou em `Process.poll()` morto. Adiciona `.claude/settings.json` ao `.gitignore` da worktree (idempotente) pra evitar commit acidental do token.
- **Alternativas rejeitadas:**
  - Settings global em `~/.claude/`: vaza pra Claude Code rodando fora do J-arvis.
  - Wrapper shim `j-arvis-claude`: binário extra; depende de checagem de versão do Claude.
  - `CLAUDE_CONFIG_DIR` env var: precisa de mais glue e suporte do Claude Code.
- **Consequências:** zero pegada em `~/.claude`; ai-jail precisa permitir egress pra `localhost:<port>` (validado na fase de impl); sessões fora do J-arvis não são afetadas; cleanup robusto em crash usa idempotência.
- **Referências:** spec `docs/superpowers/specs/2026-05-09-f2-hooks-status-semantico-design.md` §4.3, ARCHITECTURE.md §4, ADR-0001.

- [ ] **Step 2: Criar ADR-0010**

Conteúdo:

- **Contexto:** F2 publica eventos de status pra UI; F3/F4/F6 vão adicionar mais tipos (approvals, tasks, run-from-panel logs).
- **Decisão:** WebSocket único em `/ws` (sem auth, local-only) com envelope tipado `{type, session_id, payload, at}`. UI filtra por `type` no cliente (TanStack Query invalida queries específicas).
- **Alternativas rejeitadas:**
  - Canais por recurso (`/ws/sessions`, `/ws/approvals`): gasta connection slots em browsers; código duplicado de keepalive.
  - Canal por sessão + global: over-engineering pro estágio atual; payoff só em F8 (transcript stream).
  - SSE em vez de WS: contradiz §4 da arquitetura; sem ganho significativo.
- **Consequências:** UI revalida queries seletivamente; reconnect simples no cliente (`connectWs` com backoff); sem replay no servidor (clientes revalidam após reconnect); F3/F4/F6 adicionam novos `type`s sem multiplicar canais.
- **Referências:** spec §4.2, ARCHITECTURE.md §4.

- [ ] **Step 3: Atualizar `docs/adr/README.md`**

Adicionar 2 linhas no índice (após ADR-0008):

```markdown
| 0009 | Hooks via settings.json injetado no jail | Accepted |
| 0010 | WebSocket canal único com envelope tipado | Accepted |
```

- [ ] **Step 4: Atualizar `ARCHITECTURE.md` §4**

Substituir o bloco atual de §4 por:

```markdown
## 4. Comunicação Claude Code ↔ daemon

Hooks do Claude Code apontam para `http://localhost:<port>/api/hooks/<event>/<token>`:

- `Notification` em F2 sempre vira `awaiting_response` (refinado em F3 quando
  a fila de aprovações distinguir tipos).
- `PreToolUse` em F2 é audit-only: registra evento, mantém status. F3
  introduz `ApprovalRequest` e bloqueio real.
- `Stop` → marca `idle`.
- Leitura periódica do transcript para auto-resumo de 1 linha (v1.5).

Daemon → UI: WebSocket único em `/ws`, broadcast com envelope tipado
`{type, session_id, payload, at}`. Tipos atuais: `session.status`,
`session.tool_use`, `session.stopped`. Ver ADR-0009 (registro) e ADR-0010
(envelope).
```

- [ ] **Step 5: Atualizar `ARCHITECTURE.md` §13**

Adicionar ao final da tabela:

```markdown
| Hooks via settings.json no jail | [0009](docs/adr/0009-hooks-via-settings-no-jail.md) | Daemon escreve `<worktree>/.claude/settings.json` antes de `ai-jail run` | Sandbox-clean, zero pegada em `~/.claude` |
| WebSocket canal único | [0010](docs/adr/0010-websocket-canal-unico-envelope-tipado.md) | `/ws` + envelope tipado | Escala pra F3/F4/F6 sem multiplicar canais |
```

- [ ] **Step 6: Code review** subagent (revisa coerência entre ADRs, README, ARCHITECTURE).

- [ ] **Step 7: Commit final**

```bash
git add docs/adr/0009-hooks-via-settings-no-jail.md docs/adr/0010-websocket-canal-unico-envelope-tipado.md docs/adr/README.md ARCHITECTURE.md
git commit -m "$(cat <<'EOF'
docs(F2.l): ADR-0009 + ADR-0010; ARCHITECTURE.md §4 + §13 atualizados

- ADR-0009 documenta a injeção de settings.json dentro do jail
- ADR-0010 documenta o canal WS único com envelope tipado
- §4 nuance F2 vs F3 (Notification → AWAITING_RESPONSE em F2; PreToolUse audit-only)
- §13 indexa as 2 ADRs novas
EOF
)"
```

---

## Validação final (depois das 12 tasks)

- [ ] **Suite completa**: `uv run pytest -v` + `pnpm --dir ui test --run`; tudo verde.
- [ ] **Coverage 100%**: `uv run pytest --cov=orchestrator --cov-report=term-missing` + `pnpm --dir ui test --run --coverage`.
- [ ] **Demo A** (NullSessionRuntime, automatizada): garantida pelo Task 11.
- [ ] **Demo B** (AiJailRuntime, manual): rodar daemon localmente com `JARVIS_RUNTIME=aijail`; abrir UI; criar projeto+sessão; verificar:
  - `<worktree>/.claude/settings.json` existe com URLs corretas e token válido.
  - `<worktree>/.gitignore` tem a linha `.claude/settings.json`.
  - Disparar uma `Notification` real do Claude (digite algo e veja o card mudar).
  - Balão `notify-send` aparece no desktop.
  - Em `stop_session` (botão Stop) o `.claude/settings.json` some.
- [ ] **Branch ready pra PR**: `git log --oneline | head -15` mostra ~12 commits novos com prefixos `feat(F2.x)`/`docs(F2.x)`.

---

## Execution Handoff

Plan complete and saved. Two execution options:

1. **Subagent-Driven** — Eu dispatch um subagent fresco por task; review entre tasks; iteração rápida com contexto isolado por task.
2. **Inline Execution** — Executo tasks nesta sessão usando `superpowers:executing-plans`, em batches com checkpoints pra você revisar.

Qual?
