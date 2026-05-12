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
| 8 | **`cwd` do master session é XDG user data dir** (`~/.local/share/j-arvis/master/` em Linux). Daemon cria o dir se não existir. | Master é app-global, não project-specific. Não suja repos. Persiste `.ai-jail` config + settings.json entre restarts (necessários pro `--resume` funcionar). |
| 9 | **Hook system (F2) NÃO participa no master**. `settings.json` do master tem `mcpServers` + token; NÃO tem `hooks` (URLs de status). | Hooks de F2 são per-task lifecycle. Master é global e não tem ciclo de "session started/stopped" no sentido do F4. Status (idle/active) também não faz sentido pra uma sessão sempre rodando. |
| 10 | **PtyMultiplexer overflow policy**: queue full → unsubscribe o consumer lento. | Single tab travada não pode matar o `_read_loop` (que serve todas as tabs). Sacrificar o lento mantém o sistema vivo. Tab desconectada vê erro no console + reconecta. |
| 11 | **WS protocol message types**: `input`/`output`/`resize`/`system`. Sistema messages carregam `{type:"system", level:"warn"\|"error", message:"..."}` pra notificações (ex: `--resume` falhou). | Sem isso, a UI não tem como surfaceá erros não-fatais. Manter o protocolo curto: 4 tipos, sem expansão prematura. |

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

**Produção:** `SubprocessPtyOps` usa `os.openpty()` + `subprocess.Popen` com stdin/stdout/stderr=slave_fd. Async I/O via `loop.add_reader` no master_fd. **Linux/macOS only** (Windows out of scope; `loop.add_reader` não funciona no ProactorEventLoop).

**Spawn error policy:** se `MasterSessionRuntime.spawn` falha (ai-jail não no PATH, openpty falha, etc.), `lifespan` loga erro mas **NÃO aborta o daemon** — o J-arvis sobe sem master session, UI mostra estado degradado (`<MasterSidebar />` recebe `{type:"system", level:"error", message:"master indisponível: ..."}` ao conectar WS). Usuário pode usar o Kanban normalmente. Restart manual via endpoint `POST /api/master/restart` em F8+1 (out of scope inicial; pra agora restart do daemon é o único caminho).

**Settings.json escrito por `write_master_settings`:**

```json
{
  "mcpServers": {
    "j-arvis-master": {
      "type": "http",
      "url": "http://localhost:8765/api/mcp",
      "headers": {
        "Authorization": "Bearer <token-gerado-por-boot>"
      }
    }
  }
}
```

Local: `<cwd>/.claude/settings.json` (Claude Code lê settings.json relativos ao cwd). `<cwd>` é o XDG user data dir (decisão 8: `~/.local/share/j-arvis/master/`).

**`.ai-jail` config escrito por `write_master_aijail_config`:**

```toml
command = ["claude", "--dangerously-skip-permissions", "--resume", "<claude_session_id>"]
rw_maps = []
ro_maps = []
hide_dotdirs = []
mask = []
allow_tcp_ports = [8765]
```

`allow_tcp_ports = [8765]` é necessário pra Claude (dentro do jail) acessar o MCP server na porta do daemon. Difere da F1+ config que tem `allow_tcp_ports = []`.

**Comparação `AiJailRuntime` (F1+) vs `MasterSessionRuntime` (F8):**

| Aspecto | F1+ | F8 |
|---|---|---|
| Saída terminal | gnome-terminal/konsole nativo | PTY pair (master_fd → WebSocket → xterm.js) |
| Claude flags | catalog perfil (yolo/default/read-only) | sempre `--dangerously-skip-permissions --resume <id>` |
| Settings.json | hooks (F2) + tokens | **NÃO tem hooks** — só `mcpServers` config + MCP bearer token (decisão 9) |
| Lifecycle | 1 por task, ephemeral | 1 global, restartável via `--resume` |
| Catalog (F7) | usa | bypass (master é privilegiado) |

## 6. MCP server (Streamable HTTP transport)

**Protocolo correto.** MCP usa JSON-RPC 2.0 sobre Streamable HTTP — não REST per-tool. Spec oficial: `POST /api/mcp` é o ÚNICO endpoint; todas as operações são JSON-RPC messages diferenciadas por `method` (`tools/list`, `tools/call`, etc.). Headers obrigatórios: `MCP-Protocol-Version: 2025-11-25` (versão atual) e `MCP-Session-Id` (após handshake `initialize`). Response: `Content-Type: application/json` (single) ou `text/event-stream` (streaming).

**Novo módulo** `orchestrator/mcp/server.py`. Usa o SDK oficial Python (`mcp>=1.0` — nova dep) que cuida do transport e roteamento JSON-RPC:

```python
import json
from mcp.server import Server
from mcp.types import Tool, TextContent

# Server é construído uma vez no module level; tools registrados via decorators
mcp_server = Server("j-arvis-master")


@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(name="list_projects", description="List all projects.",
             inputSchema={"type": "object", "properties": {}}),
        Tool(name="get_project", description="Get a project by id.",
             inputSchema={"type": "object", "required": ["project_id"],
                          "properties": {"project_id": {"type": "string"}}}),
        Tool(name="list_tasks", description="List tasks, optionally filtered.",
             inputSchema={
                 "type": "object",
                 "properties": {
                     "project_id": {"type": "string"},
                     "state": {"type": "string",
                               "enum": ["idea", "ready", "in_progress", "review", "done", "discarded"]},
                 },
             }),
        Tool(name="get_task", description="Get a task by id.",
             inputSchema={"type": "object", "required": ["task_id"],
                          "properties": {"task_id": {"type": "string"}}}),
        Tool(name="create_task", description="Create a new task.",
             inputSchema={
                 "type": "object",
                 "required": ["project_id", "title"],
                 "properties": {
                     "project_id": {"type": "string"},
                     "title": {"type": "string"},
                     "description": {"type": "string"},
                     "template": {"type": "string",
                                  "enum": ["frontend", "backend", "refactor", "bugfix"]},
                     "branch": {"type": "string"},
                 },
             }),
        Tool(name="update_task", description="Update fields on a task (state machine respected).",
             inputSchema={
                 "type": "object",
                 "required": ["task_id"],
                 "properties": {
                     "task_id": {"type": "string"},
                     "title": {"type": "string"},
                     "description": {"type": "string"},
                     "template": {"type": "string"},
                     "state": {"type": "string"},
                     "branch": {"type": "string"},
                 },
             }),
        Tool(name="discard_task", description="Move task to discarded state.",
             inputSchema={"type": "object", "required": ["task_id"],
                          "properties": {"task_id": {"type": "string"}}}),
    ]


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Dispatch JSON-RPC tool calls. Dependencies vêm do request context."""
    ctx = mcp_server.request_context
    db: AsyncSession = ctx.state["db"]
    catalog: Catalog = ctx.state["catalog"]
    broadcaster: WsBroadcaster = ctx.state["broadcaster"]

    if name == "list_projects":
        rows = await list_projects(db)
        return [TextContent(type="text", text=json.dumps([_serialize(r) for r in rows]))]
    if name == "create_task":
        task = await create_task(db, catalog=catalog, **arguments)
        await broadcaster.publish(WsEvent.task_created(
            task_id=task.id, project_id=task.project_id, title=task.title, state=task.state,
        ))
        return [TextContent(type="text", text=_serialize_task(task))]
    if name == "update_task":
        task_id = arguments.pop("task_id")
        task = await update_task(db, task_id, catalog=catalog, **arguments)
        await broadcaster.publish(WsEvent.task_updated(...))
        return [TextContent(type="text", text=_serialize_task(task))]
    if name == "discard_task":
        task = await update_task(db, arguments["task_id"], state="discarded", catalog=catalog)
        await broadcaster.publish(WsEvent.task_updated(...))
        return [TextContent(type="text", text=_serialize_task(task))]
    # ... resto dos tools (get_*, list_*) seguem o mesmo padrão (read-only, sem broadcast)
    raise ValueError(f"unknown tool {name!r}")
```

**Auth via Streamable HTTP**: usa `Authorization: Bearer <token>` (padrão HTTP, não custom header). Token único por boot do daemon:

```python
# Em create_app lifespan:
app.state.master_mcp_token = secrets.token_urlsafe(32)


async def _verify_mcp_auth(request: Request) -> None:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    if auth[7:] != request.app.state.master_mcp_token:
        raise HTTPException(401, "invalid MCP token")
```

**Mount em FastAPI**: o SDK MCP fornece `StreamableHttpServerTransport` que é um ASGI app montável. Em `main.py:create_app`:

```python
from mcp.server.streamable_http import StreamableHttpServerTransport
from orchestrator.mcp.server import mcp_server, build_mcp_app

mcp_asgi = build_mcp_app(
    server=mcp_server,
    state_provider=lambda req: {
        # Cada request recebe estes recursos via ctx.state no call_tool
        "db": req.app.state.database,
        "catalog": req.app.state.catalog,
        "broadcaster": req.app.state.ws_broadcaster,
        "git_ops": req.app.state.git_ops,
    },
    auth=_verify_mcp_auth,
)
app.mount("/api/mcp", mcp_asgi)
```

`build_mcp_app` é nosso wrapper (a definir em F8.c) que: cria o `StreamableHttpServerTransport`, embrulha em middleware ASGI que valida auth e injeta deps no `mcp_server.request_context.state` antes do handler rodar.

**Catalog injection (explícito):** o SDK MCP **não** suporta `Depends()` no `call_tool`. A injeção do `Catalog` é feita via `request_context.state` (set via middleware no mount). O handler de cada tool lê `ctx.state["catalog"]` e passa pro `core.tasks.create_task(..., catalog=catalog)` — mesma assinatura F7.

**Tool inventory:**

| Tool | Input (JSON Schema simplificado) | Output | Side effect |
|---|---|---|---|
| `list_projects` | `{}` | `[Project]` JSON | none |
| `get_project` | `{project_id}` | `Project` JSON | none |
| `list_tasks` | `{project_id?, state?}` | `[Task]` JSON | none |
| `get_task` | `{task_id}` | `Task` JSON | none |
| `create_task` | `{project_id, title, description?, template?, branch?}` | `Task` JSON | INSERT + WS `task_created` broadcast pra Kanban subscribers |
| `update_task` | `{task_id, fields...}` | `Task` JSON | UPDATE + WS `task_updated` |
| `discard_task` | `{task_id}` | `Task` JSON | state→discarded + WS `task_updated` |

**Reuso F7:** `create_task` MCP recebe `template` opcional e passa pelo mesmo `core.tasks.create_task` — resolve perfil, gera branch via prefix, raise `InvalidTemplateError` se template não existe. O erro vira JSON-RPC error response `{code: -32602, message: "Invalid params: template_not_in_catalog: valid=['frontend',...]"}` que Claude vê e pode reagir (corrigir + reenviar).

**MCP write echo policy** (decisão explícita):
- Tool response é a **fonte de verdade pra Claude** (ele recebe o `Task` row criado/editado direto na response do `tools/call`)
- WS broadcasts (`task_created`, `task_updated`) vão pra **subscribers do Kanban via WS existente** (F2 `/ws/sessions`), NÃO ecoam de volta pra master PTY
- Master não recebe events de "task changed by someone else" — sem loop reativo possível. Fora de scope F8 ter Claude reagir a mudanças externas.

## 7. WebSocket bridge

**Novo módulo** `orchestrator/api/master_ws.py`:

```python
@router.websocket("/ws/master")
async def master_ws(websocket: WebSocket, request: Request) -> None:
    """Bridge bidirectional entre browser e PTY do master session.

    Múltiplas tabs do browser conectam simultaneamente. Fazem multiplex
    no MESMO PTY (single global). Output broadcast pra todas as tabs.
    """
    # Race protection: PTY pode ainda não estar pronto (lifespan slow) ou
    # ter falhado o spawn. Fechar com close code 1011 (server error) + razão.
    handle = getattr(request.app.state, "master_handle", None)
    multiplexer = getattr(request.app.state, "master_multiplexer", None)
    if handle is None or multiplexer is None:
        await websocket.accept()
        await websocket.send_json({
            "type": "system", "level": "error",
            "message": "master session not available",
        })
        await websocket.close(code=1011, reason="master_not_ready")
        return

    await websocket.accept()

    # Writes ao PTY são serializados via lock — escrita concorrente de 2 tabs
    # podem interlevar bytes mid-keystroke. Lock garante atomicidade por write().
    write_lock = request.app.state.master_write_lock  # asyncio.Lock global

    async def browser_to_pty() -> None:
        async for msg in websocket.iter_json():
            if msg["type"] == "input":
                async with write_lock:
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
                break  # EOF (PTY morreu)
            # Decisão 10: subscriber lento que enche queue é desconectado;
            # nunca bloqueia o reader (que serve todas as tabs).
            for q in list(self._subscribers):
                try:
                    q.put_nowait(chunk)
                except asyncio.QueueFull:
                    self._subscribers.discard(q)
                    # Subscriber dropped — sua WS handler vai detectar (queue.get hangs)
                    # ou recebe um {type:"system",level:"error","message":"dropped (slow)"} próximo

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
        async with database.session() as s:
            await cleanup_orphan_master_at_startup(s)  # mata PID de boot anterior

        # F8: spawn / resume master session
        async with database.session() as s:
            master = await s.get(MasterSession, "singleton")
            session_id = master.claude_session_id if master else None

        app.state.master_mcp_token = secrets.token_urlsafe(32)
        app.state.master_write_lock = asyncio.Lock()

        # XDG user data dir (decisão 8)
        master_cwd = Path.home() / ".local" / "share" / "j-arvis" / "master"
        master_cwd.mkdir(parents=True, exist_ok=True)

        # Runtime instance (SubprocessPtyOps em prod; FakePtyOps em tests via param)
        pty_ops = SubprocessPtyOps()
        master_runtime = MasterSessionRuntime(pty_ops)

        try:
            handle = await master_runtime.spawn(
                cwd=master_cwd,
                claude_session_id=session_id,
                mcp_url=f"http://localhost:{port}/api/mcp",
                token=app.state.master_mcp_token,
            )
        except (FileNotFoundError, OSError) as exc:
            # Spawn falhou (ex: ai-jail não no PATH, openpty failed).
            # Daemon SOBE sem master session; UI mostra estado degradado.
            logger.error("master session spawn failed: %s", exc)
            app.state.master_handle = None
            app.state.master_multiplexer = None
        else:
            app.state.master_handle = handle
            app.state.master_multiplexer = PtyMultiplexer(pty_ops, handle.master_fd)
            # Persistir state atualizado
            async with database.session() as s:
                await s.merge(MasterSession(
                    id="singleton",
                    claude_session_id=handle.claude_session_id,
                    pid=handle.pid,
                    started_at=handle.started_at,
                    last_active=datetime.now(UTC),
                ))
                await s.commit()

            # Detecta se `claude --resume` falhou (jsonl corrompido):
            # PTY morre rápido (<1s) com exit code != 0. Se acontecer, spawn
            # de novo com session_id=None (perde história mas sobrevive).
            # Detalhe: implementado em F8.e via watchdog que monitora EOF
            # do multiplexer; se EOF em <1s, broadcast system message +
            # spawn fallback.

    yield

    # Shutdown
    if getattr(app.state, "master_multiplexer", None):
        await app.state.master_multiplexer.shutdown()
    if getattr(app.state, "master_handle", None):
        try:
            pty_ops.kill(app.state.master_handle.pid)
        except ProcessLookupError:
            pass
        # Atualiza pid=None no banco pro próximo boot
        async with database.session() as s:
            master = await s.get(MasterSession, "singleton")
            if master:
                master.pid = None
                await s.commit()
```

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
- `test_master_runtime.py` — spawn escreve `.ai-jail` + `settings.json` corretos; novo `session_id` se None; reusa se passado; spawn falha (FileNotFoundError) é capturada
- `test_master_settings_writer.py` — `write_master_settings` produz `mcpServers` JSON válido com bearer token; `write_master_aijail_config` produz TOML com `--resume` flag e `allow_tcp_ports = [<port>]`
- `test_pty_multiplexer.py` — fan-out funciona; subscribe/unsubscribe limpa; subscriber lento (queue full) é descartado sem matar reader; shutdown cancela reader task

### Backend integration (`tests/integration/`)

- `test_pty_real_subprocess.py` — **PTY integration smoke**: spawna `/bin/echo "hello"` via `SubprocessPtyOps` real, verifica round-trip de bytes via `read()`. Garante que `os.openpty()` + subprocess wiring funciona. Pequeno (~50 lines), single test.
- `test_api_mcp_read_tools.py` — `tools/list` retorna 7 tools com schemas; `tools/call name=list_tasks` com token válido → 200 + JSON-RPC result; sem token → 401
- `test_api_mcp_create_task.py` — `tools/call name=create_task` com template → reusa F7 path; sem template → NULL/NULL; template inválido → JSON-RPC error `-32602`
- `test_api_mcp_update_task.py` — update_task respeita state machine (F4); discard_task vira `state=discarded`
- `test_api_master_ws.py` — connect → mocked PTY echoes input; multiple connections compartilham PTY; race protection: WS antes do PTY pronto → close 1011 + system message
- `test_master_session_persists.py` — restart simulado: daemon reusa `claude_session_id` do banco
- `test_master_cleanup_orphan.py` — PID órfão é morto no startup
- `test_master_spawn_failure_degraded.py` — `ai-jail` ausente → daemon sobe sem master; WS connect retorna system error; resto da API funciona

### UI (`ui/src/`)

- `MasterSidebar.test.tsx` — renderiza xterm.js (mock do construtor); conecta WS (mock); envia input ao escrever; renderiza output recebido; resize handler; exibe system messages como banner
- xterm.js internals (canvas rendering, buffer manipulation) ficam em `vitest.config.coverage.exclude` — lib externa não conta pro gate

### E2E (host-only, `tests/e2e/`)

- `test_f8_master_creates_task.py` — abrir UI, digitar "cria task X no projeto Y" no sidebar via xterm, esperar Claude responder via MCP, verificar task aparece no Kanban
- **Como Playwright lê do xterm.js**: `MasterSidebar.tsx` expõe `window.__masterTerm = term` (apenas em modo dev/test, condicional a `import.meta.env.MODE !== 'production'`). E2E usa `page.evaluate(() => window.__masterTerm.buffer.active.getLine(N).translateToString())` pra inspecionar conteúdo da scrollback. Sem essa exposição explícita, xterm.js renderiza pra canvas e Playwright não consegue assert de texto.

## 11. Sub-tasks breakdown (preview)

| ID | Entrega | Tests | Depende de |
|---|---|---|---|
| **F8.a** | `MasterSession` model + migration 0006 + `PtyProcessOps` Protocol stub | unit (model) | — |
| **F8.b** | `MasterSessionRuntime` + `write_master_aijail_config` + `write_master_settings` + `SubprocessPtyOps` impl + `test_pty_real_subprocess` smoke | unit + integration (runtime) | F8.a |
| **F8.c** | MCP server: módulo + tools read-only (list/get) + auth bearer + ASGI mount em `/api/mcp` | integration (mcp read) | F8.a |
| **F8.d** | MCP tools write: create/update/discard_task (reusa core/tasks); WS broadcast pra Kanban | integration (mcp write) | F8.c |
| **F8.e** | WebSocket `/ws/master` + `PtyMultiplexer` + lifespan integration + race protection + cleanup_orphan | integration (ws + lifecycle) | F8.b, F8.d |
| **F8.f** | UI `<MasterSidebar />` + xterm.js (gate: smoke render React 19 compat antes de prosseguir) + WebSocket client + integração no App.tsx + `window.__masterTerm` expose | UI (sidebar) | F8.e |
| **F8.g** | ADR-0022 + ARCHITECTURE F8 ✅ + E2E skeleton + closure | docs + e2e | F8.f |

**Paralelização**: F8.b ∥ F8.c (independentes após F8.a). F8.f tem gate de compat na primeira sub-step: instala xterm 5.5 + faz render smoke; se falhar com React 19, abre blocker (fallback: downgrade React em escopo isolado, ou pin xterm versão anterior).

7 sub-tasks. Tamanho similar a F7. F8.b/F8.e são os maiores (PTY infra + WS bridge + race + cleanup).

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
