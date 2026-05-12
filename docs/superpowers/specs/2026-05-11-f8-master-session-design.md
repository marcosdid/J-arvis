# F8 — Sessão master Claude no sidebar web (design)

**Status:** spec aprovada, plan pending
**Data:** 2026-05-11
**Phase:** F8 (primeira fase pós-MVP)

## 1. Contexto

ARCHITECTURE.md §11 originalmente definia F8 como "Planner meta-agente — usuário cola épico → preview de subtasks → backlog. Sessão efêmera, tela de preview, bulk insert."

Durante brainstorm, a feature foi **reformulada** pra uma ambição maior: uma **sessão master Claude global, persistente, renderizada num sidebar web** que gerencia o app inteiro via tools que mexem no banco do J-arvis. O caso de uso "decompor épico em subtasks" continua coberto — mas agora como **uma das interações possíveis** com o master (você pede via chat, Claude usa o tool `create_task` N vezes), não como uma UI dedicada.

**ARCHITECTURE.md §11 será atualizado em F8.g** pra refletir o novo escopo.

## 2. Decisões architecturais

| # | Decisão | Motivação |
|---|---|---|
| 1 | **F8 substitui o F8 original** (épico ephemeral). Mestre genérico absorve o caso de uso "decomponha esse épico em 8 tasks" como uma das suas habilidades via tools. | Master cobre estritamente mais que o F8 original. Manter ambos seria redundante. |
| 2 | **Master é uma sessão Claude Code (CLI) como qualquer outra de F1+**, com ai-jail + `--dangerously-skip-permissions`, **com tools adicionais via MCP server**. | Reusa toda a infra de F1+ (ai-jail, hooks, status semantics). Diferença: privilégios elevados, não tecnologia diferente. |
| 3 | **UI = sidebar web com xterm.js + PTY backend** (não terminal nativo). | Usuário pediu literalmente "lateral do painel". Tech de "VSCode terminal" (xterm.js + PTY) é o padrão. |
| 4 | **Tool surface ampla**: read (list/get projects/tasks), write (create/update/discard task). Cobre 90% dos use cases via chat. | Match com "criando tarefas, refinando tarefas e qualquer outra coisa do tipo" do usuário. |
| 5 | **Fora de F8 inicial**: start_session, start_run, manage worktrees, edit projects. Master planeja, usuário executa. | YAGNI + safety. Pode ser ampliado em F8+1 se houver demanda. |
| 6 | **Persistência via Claude CLI `--resume <session-id>`**. Daemon grava `claude_session_id` no banco; no restart spawna `claude --resume <id>` → Claude lembra naturalmente do jsonl que ele mesmo persiste em `~/.claude/projects/.../`. | Sem trabalho de persistência custom. Claude já tem a primitiva certa. |
| 7 | **Uma única sessão global** (não per-project, não múltiplas conversas paralelas). | YAGNI. Master vê todos projetos via tools; contexto implícito do projeto ativo pode vir em F8+1. |

## 3. Modelo de dados

**Migração 0006** (`alembic/versions/0006_master_session.py`):

```python
class MasterSession(Base):
    __tablename__ = "master_session"
    # Singleton design — só pode existir 1 row
    id: Mapped[str] = mapped_column(String, primary_key=True, default="singleton")
    claude_session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_active: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (
        CheckConstraint("id = 'singleton'", name="ck_master_singleton"),
    )
```

`claude_session_id` é o UUID hex que Claude CLI gera (vive em `~/.claude/projects/<repo>/<uuid>.jsonl`). Daemon guarda esse ID e usa `claude --resume <id>` em todo restart pra continuar a conversa.

`pid` é o PID do `ai-jail` rodando — `NULL` quando daemon não está com PTY ativa. Usado pra cleanup de PIDs órfãos no startup.

## 4. Arquitetura

```
┌─ Browser (React) ──────────────────────────┐
│  ┌──────────────────┐                      │
│  │ <MasterSidebar/> │                      │
│  │  xterm.js panel  │ ←── WebSocket ──┐    │
│  │  + input         │                 │    │
│  └──────────────────┘                 │    │
└───────────────────────────────────────│────┘
                                        │
┌───────────────────────────────────────│────┐
│ Daemon (FastAPI)                      │    │
│                                       ▼    │
│  /ws/master ←→ PtyMultiplexer              │
│                  │                         │
│                  ▼                         │
│           PTY pair (single global)         │
│                  │                         │
│           ai-jail + claude --resume <id>   │
│                          --dangerously-... │
│                  │                         │
│                  ▼ MCP tools (via settings)│
│           /api/mcp sub-app                 │
│           Tools: list/create/update/...    │
└────────────────────────────────────────────┘
```

## 5. PTY runtime

**Novo módulo** `orchestrator/sandbox/pty_runtime.py`:

```python
class PtyProcessOps(Protocol):
    """Abstração de PTY pair (fakeable em tests)."""
    def spawn(self, cmd: list[str], cwd: str) -> tuple[int, int]:
        """Retorna (pid, master_fd)."""
    async def read(self, master_fd: int, n: int = 4096) -> bytes: ...
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


class MasterSessionRuntime:
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
        write_master_aijail_config(cwd, claude_session_id=session_id)
        pid, fd = self._pty.spawn(["ai-jail"], str(cwd))
        return MasterPtyHandle(pid, fd, session_id, datetime.now(UTC))
```

**Produção:** `SubprocessPtyOps` usa `os.openpty()` + `subprocess.Popen` com stdin/stdout/stderr=slave_fd. Async I/O via `loop.add_reader` no master_fd.

**Comparação `AiJailRuntime` (F1+) vs `MasterSessionRuntime` (F8):**

| Aspecto | F1+ | F8 |
|---|---|---|
| Saída terminal | gnome-terminal/konsole nativo | PTY pair (master_fd → WebSocket → xterm.js) |
| Claude flags | catalog perfil (yolo/default/read-only) | sempre `--dangerously-skip-permissions --resume <id>` |
| Settings.json | hooks (F2) + tokens | hooks + tokens + **MCP server config** (novo) |
| Lifecycle | 1 por task, ephemeral | 1 global, restartável via `--resume` |
| Catalog (F7) | usa | bypass (master é privilegiado) |

## 6. MCP server

**Novo módulo** `orchestrator/mcp/server.py` — FastAPI sub-app montada em `/api/mcp`:

```python
mcp_app = FastAPI(title="J-arvis Master MCP")

def _auth(token: str = Header(..., alias="X-MCP-Token")) -> None:
    if token != app.state.master_mcp_token:
        raise HTTPException(401, "invalid MCP token")


@mcp_app.post("/tools/list_projects", dependencies=[Depends(_auth)])
async def tool_list_projects(...) -> list[ProjectRead]: ...

@mcp_app.post("/tools/list_tasks", dependencies=[Depends(_auth)])
async def tool_list_tasks(
    project_id: str | None = None,
    state: str | None = None,
    ...
) -> list[TaskRead]: ...

@mcp_app.post("/tools/get_task", dependencies=[Depends(_auth)])
async def tool_get_task(task_id: str, ...) -> TaskRead: ...

@mcp_app.post("/tools/create_task", dependencies=[Depends(_auth)])
async def tool_create_task(...) -> TaskRead:
    # Reusa core.tasks.create_task (catalog, slugify, etc.)
    ...

@mcp_app.post("/tools/update_task", dependencies=[Depends(_auth)])
async def tool_update_task(...) -> TaskRead: ...

@mcp_app.post("/tools/discard_task", dependencies=[Depends(_auth)])
async def tool_discard_task(task_id: str, ...) -> TaskRead:
    # Equivalente a PATCH state=discarded (reusa state machine F4)
    ...
```

**Tool inventory:**

| Tool | Input | Output | Side effect |
|---|---|---|---|
| `list_projects` | (none) | `[Project]` | none |
| `get_project` | `project_id: str` | `Project` | none |
| `list_tasks` | `project_id?: str`, `state?: str` | `[Task]` | none |
| `get_task` | `task_id: str` | `Task` | none |
| `create_task` | `project_id, title, description?, template?, branch?` | `Task` | INSERT + WS broadcast |
| `update_task` | `task_id, {title?, description?, template?, state?, branch?}` | `Task` | UPDATE + WS broadcast |
| `discard_task` | `task_id` | `Task` | state machine transition + WS broadcast |

**Auth:** token único gerado por boot do daemon (`secrets.token_urlsafe(32)`), armazenado em `app.state.master_mcp_token`. Token é injetado no `settings.json` que vive dentro do `.ai-jail` jail do master — não acessível pelo usuário. Rotaciona a cada restart.

**Reuso F7:** `create_task` MCP recebe `template` opcional e segue o mesmo path do `core.tasks.create_task` — resolve perfil, gera branch via prefix, raise `InvalidTemplateError` se template não existe no catálogo.

## 7. WebSocket bridge

**Novo módulo** `orchestrator/api/master_ws.py`:

```python
@router.websocket("/ws/master")
async def master_ws(websocket: WebSocket, request: Request) -> None:
    """Bridge bidirectional entre browser e PTY do master session.

    Múltiplas tabs do browser conectam simultaneamente. Fazem multiplex
    no MESMO PTY (single global). Output broadcast pra todas as tabs.
    """
    await websocket.accept()
    handle: MasterPtyHandle = request.app.state.master_handle
    multiplexer: PtyMultiplexer = request.app.state.master_multiplexer

    async def browser_to_pty() -> None:
        async for msg in websocket.iter_json():
            if msg["type"] == "input":
                await pty_ops.write(handle.master_fd, msg["data"].encode())
            elif msg["type"] == "resize":
                pty_ops.resize(handle.master_fd, msg["rows"], msg["cols"])

    queue: asyncio.Queue[bytes] = await multiplexer.subscribe()
    async def pty_to_browser() -> None:
        while True:
            chunk = await queue.get()
            await websocket.send_json({"type": "output", "data": chunk.decode("utf-8", errors="replace")})

    try:
        await asyncio.gather(browser_to_pty(), pty_to_browser())
    except WebSocketDisconnect:
        multiplexer.unsubscribe(queue)
```

**`PtyMultiplexer`** (novo): single reader on PTY master_fd, fan-out to N subscriber queues. Permite N WebSocket connections (N browser tabs) compartilharem o mesmo PTY.

```python
class PtyMultiplexer:
    def __init__(self, pty_ops: PtyProcessOps, master_fd: int) -> None:
        self._pty = pty_ops
        self._master_fd = master_fd
        self._subscribers: set[asyncio.Queue[bytes]] = set()
        self._reader_task = asyncio.create_task(self._read_loop())

    async def _read_loop(self) -> None:
        while True:
            chunk = await self._pty.read(self._master_fd, 4096)
            if not chunk:
                break  # EOF
            for q in self._subscribers:
                q.put_nowait(chunk)

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
```

## 8. UI sidebar

### Dependências novas (UI)

```json
"@xterm/xterm": "^5.5.0",
"@xterm/addon-fit": "^0.10.0"
```

Verificar compat com React 19 antes de F8.f começar (último checkpoint conhecido: xterm 5.x stable Q4 2025).

### Componente

`ui/src/components/MasterSidebar.tsx`:

```tsx
export function MasterSidebar() {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const term = new Terminal({
      fontSize: 13,
      fontFamily: 'monospace',
      theme: { background: '#1e293b', foreground: '#e2e8f0' },
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(containerRef.current!);
    fit.fit();

    const ws = new WebSocket(`ws://${window.location.host}/ws/master`);
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === 'output') term.write(msg.data);
    };
    term.onData((data) => ws.send(JSON.stringify({ type: 'input', data })));
    term.onResize(({ rows, cols }) =>
      ws.send(JSON.stringify({ type: 'resize', rows, cols })),
    );

    return () => { ws.close(); term.dispose(); };
  }, []);

  return (
    <aside className="master-sidebar" aria-label="master-session">
      <header>
        <h3>Claude master</h3>
        <span className="hint">compartilhado entre abas</span>
      </header>
      <div ref={containerRef} className="master-term" />
    </aside>
  );
}
```

### Layout

```
┌─ App ──────────────────────────────────────────────────┐
│ ┌─ Kanban (existente) ───────────┐ ┌─ MasterSidebar ─┐ │
│ │                                │ │  Claude master  │ │
│ │  [idea] [ready] [in_progress]  │ │  ┌──────────┐   │ │
│ │  [...] [...]   [...]           │ │  │ xterm.js │   │ │
│ │                                │ │  │          │   │ │
│ │                                │ │  └──────────┘   │ │
│ └────────────────────────────────┘ └─────────────────┘ │
└────────────────────────────────────────────────────────┘
```

CSS grid no `App.tsx`: Kanban `1fr`, sidebar `400px` (resizable opcional). Sidebar full-height, fixed à direita.

## 9. Lifecycle

### Daemon startup

```python
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if database is not None:
        await database.bootstrap()
        # F8: spawn / resume master session
        async with database.session() as s:
            master = await s.get(MasterSession, "singleton")
            session_id = master.claude_session_id if master else None
        app.state.master_mcp_token = secrets.token_urlsafe(32)
        handle = await master_runtime.spawn(
            cwd=Path("/some/master-cwd"),  # decisão pendente: onde mora o master cwd?
            claude_session_id=session_id,
            mcp_url=f"http://localhost:{port}/api/mcp",
            token=app.state.master_mcp_token,
        )
        app.state.master_handle = handle
        app.state.master_multiplexer = PtyMultiplexer(pty_ops, handle.master_fd)
        # Persistir/atualizar
        async with database.session() as s:
            await s.merge(MasterSession(
                id="singleton",
                claude_session_id=handle.claude_session_id,
                pid=handle.pid,
                started_at=handle.started_at,
                last_active=datetime.now(UTC),
            ))
            await s.commit()
    yield
    # Shutdown: kill PTY, atualizar pid=None
    if hasattr(app.state, "master_handle"):
        await app.state.master_multiplexer.shutdown()
        pty_ops.kill(app.state.master_handle.pid)
```

**Decisão pendente menor:** `cwd` do master session. Opções:
- `~/.local/share/j-arvis/master/` (XDG user data dir) — isolado, não suja repos
- O cwd do projeto ativo no UI — contextual mas muda

Recomendação inicial: XDG user data dir. Master é app-global, não project-specific.

### Cleanup orphan master at startup

Igual ao `cleanup_orphan_runs_at_startup` do F6:

```python
async def cleanup_orphan_master_at_startup(s: AsyncSession) -> None:
    """Se daemon caiu sem matar PTY, tenta `kill -9` do PID antigo."""
    master = await s.get(MasterSession, "singleton")
    if master and master.pid is not None:
        try:
            os.kill(master.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass  # já morreu
        master.pid = None
        await s.commit()
```

## 10. Plano de testes

### Backend unit (`tests/unit/`)

- `test_pty_ops.py` — `FakePtyOps` com queues; spawn retorna pids; read/write/resize/kill chamáveis
- `test_master_runtime.py` — spawn escreve `.ai-jail` + `settings.json` corretos; novo `session_id` se None; reusa se passado
- `test_master_settings_writer.py` — `write_master_settings` produz JSON válido com MCP server + token
- `test_pty_multiplexer.py` — fan-out funciona; subscribe/unsubscribe limpa; shutdown cancela reader task

### Backend integration (`tests/integration/`)

- `test_api_mcp_read_tools.py` — list_projects, list_tasks, get_task com token válido → 200; sem token → 401
- `test_api_mcp_create_task.py` — POST create_task com template → reusa F7 path; sem template → NULL/NULL; invalid → 422
- `test_api_mcp_update_task.py` — update_task respeita state machine (F4); discard_task vira `state=discarded`
- `test_api_master_ws.py` — connect → mocked PTY echoes input; multiple connections compartilham PTY
- `test_master_session_persists.py` — restart simulado: daemon reusa `claude_session_id` do banco
- `test_master_cleanup_orphan.py` — PID órfão é morto no startup

### UI (`ui/src/`)

- `MasterSidebar.test.tsx` — renderiza xterm.js (mock); conecta WS (mock); envia input ao escrever; renderiza output recebido; resize handler
- Sem coverage gate em xterm.js internals (lib externa marca exclusion)

### E2E (host-only)

- `test_f8_master_creates_task.py` — abrir UI, digitar "cria task X no projeto Y" no sidebar via xterm, esperar Claude responder via MCP, verificar task aparece no Kanban

## 11. Sub-tasks breakdown (preview)

| ID | Entrega | Tests |
|---|---|---|
| **F8.a** | `MasterSession` model + migration 0006 + `PtyProcessOps` Protocol stub | unit (model) |
| **F8.b** | `MasterSessionRuntime` + `write_master_aijail_config` + `write_master_settings` | unit (runtime + writers) |
| **F8.c** | MCP server: módulo + tools read-only (list_*, get_*) + auth token | integration (mcp read) |
| **F8.d** | MCP tools write: create/update/discard_task (reusa core/tasks); WS broadcast | integration (mcp write) |
| **F8.e** | WebSocket `/ws/master` + `PtyMultiplexer` + lifespan integration | integration (ws + lifecycle) |
| **F8.f** | UI `<MasterSidebar />` + xterm.js + WebSocket client + integração no App.tsx | UI (sidebar) |
| **F8.g** | ADR-0022 + ARCHITECTURE F8 ✅ + E2E skeleton + closure | docs + e2e |

7 sub-tasks. Tamanho similar a F7. F8.b e F8.e são os maiores (PTY infrastructure + WS bridge).

## 12. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Múltiplas tabs do browser confundem usuário (typo numa tab = aparece em todas) | Decisão consciente — match com "1 master global". Hint visível no header: "compartilhado entre abas". |
| Claude CLI `--resume` falha (jsonl corrompido) | Detect falha de spawn → fallback pra novo session_id (perde história mas sobrevive) + log warning + notifica UI |
| PTY zombie após crash do daemon | `cleanup_orphan_master_at_startup` mata PID antigo no boot (mesmo padrão F6) |
| MCP server tem auth fraca | Token único por boot, em settings.json dentro do .ai-jail jail (não acessível user). Rotaciona a cada restart. |
| `xterm.js` + React 19 incompat | Verificar compat na primeira sub-task de UI (F8.f); fallback: usar Vite preact-like compat shim ou downgrade React em escopo isolado |
| Master pode criar tasks malformadas | MCP `create_task` reusa `core.tasks.create_task` → validação F4/F7 aplicada (title, branch, template); Claude vê 422 e pode corrigir |
| Master pode loopear chamando tools | Claude já tem rate-limit interno; daemon não precisa de circuit breaker no F8 inicial. Monitora em logs por enquanto. |

## 13. Não-objetivos

- Múltiplas conversas simultâneas estilo ChatGPT/Cursor (decisão 7 — uma global)
- Master gerencia worktrees/runs/sessions (decisão 5 — fora de scope F8 inicial)
- Per-project master sessions (decisão 7)
- Transcript em DB próprio (decisão 6 — Claude jsonl é a fonte)
- Anthropic API direta (decisão 2 — Claude CLI nativo)
- UI dedicada de "decompor épico" (decisão 1 — absorvido pelo chat genérico)
- Confirmação por ação destrutiva no UI (Claude tem `--dangerously-skip-permissions` ativo; usuário confia que ele não vai discardar tasks erradas; pode adicionar em F8+1 se necessário)
