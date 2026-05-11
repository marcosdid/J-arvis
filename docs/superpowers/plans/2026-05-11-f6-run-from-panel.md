# F6 — Run from Panel (implementation plan)

- **Spec:** `docs/superpowers/specs/2026-05-11-f6-run-from-panel-design.md`
- **Decisões fechadas:** §3 do spec (11 + 6 derivadas)
- **Branch:** continuar em `claude/fresh-start-cleanup-XDaHV` (F5 fechada)
- **Métodologia:** subagent-driven (igual F5) — implementer + 2 reviewers por sub-task
- **Disciplina:** TDD iron law (ADR-0004); 100% coverage gate em cada commit

## File Structure

**Backend (Python):**

```
orchestrator/
├── core/
│   ├── manifest.py            NOVO — parse + validar `.orchestrator/run.yml`
│   ├── port_allocator.py      NOVO — alocação 31000-31999 c/ socket test
│   ├── runs.py                NOVO — start_run, stop_run, state machine
│   └── bootstrap.py           NOVO — spawn sessão efêmera + file watcher
├── sandbox/
│   ├── aijail.py              MOD — write_aijail_config aceita extra_tcp_ports
│   └── docker_ops.py          NOVO — Protocol DockerOps + SubprocessDockerOps
├── store/
│   └── models.py              MOD — adicionar RunInstance
├── api/
│   ├── runs.py                NOVO — POST /tasks/{id}/runs, /runs/{id}/stop, /logs (SSE)
│   ├── bootstrap.py           NOVO — POST /tasks/{id}/bootstrap-manifest
│   └── tasks.py               MOD — hook cleanup pra stop_run em terminal states
├── events/
│   └── envelope.py            MOD — factories run.status/log/failed/stopped/bootstrap.proposed
├── ws/
│   └── broadcaster.py         MOD (se necessário) — batching pra run.log
└── main.py                    MOD — wire DockerOps + PortAllocator no app.state

alembic/versions/
└── 0005_run_instances.py      NOVO — create table run_instances
```

**Tests (Python):**

```
tests/
├── unit/
│   ├── test_manifest.py
│   ├── test_port_allocator.py
│   ├── test_docker_ops.py        (com FakeDockerOps)
│   ├── test_runs_core.py
│   └── test_bootstrap.py
├── integration/
│   ├── test_api_runs.py
│   ├── test_run_failure.py
│   ├── test_run_cleanup_on_task_terminal.py
│   ├── test_bootstrap_session.py
│   └── test_aijail_config_with_run_ports.py
└── e2e/
    ├── test_f6_simple_run_flow.py
    └── test_f6_bootstrap_missing_manifest.py
```

**Frontend (TypeScript):**

```
ui/src/
├── lib/
│   ├── api.ts                 MOD — types Run/Service/Bootstrap + endpoints
│   ├── events.ts              MOD — adicionar run.* + bootstrap.proposed
│   └── runSseClient.ts        NOVO — EventSource wrapper pra /logs
├── hooks/
│   ├── useSessionEvents.ts    MOD — handlers run.*, bootstrap.proposed
│   ├── useRun.ts              NOVO — query + mutations (start/stop)
│   └── useRunLogs.ts          NOVO — SSE consumer com buffer ring
└── components/
    ├── RunStatus.tsx          NOVO — rodapé do TaskCard
    ├── RunTab.tsx             NOVO — aba do TaskDetailModal
    ├── RunLogsPanel.tsx       NOVO — stream + filtro por serviço
    ├── BootstrapModal.tsx     NOVO — modal "Manifesto faltando"
    ├── ServiceStatusBadge.tsx NOVO — badge per-service
    ├── TaskCard.tsx           MOD — embed <RunStatus />
    └── TaskDetailModal.tsx    MOD — embed <RunTab />
```

## Pre-flight corrections (READ BEFORE EXECUTING)

### PFC-1 — ~~`extra_tcp_ports` no `.ai-jail`~~ NÃO É NECESSÁRIO (F6.0 descoberta)

Hipótese original: `start_run` precisava re-escrever o `.ai-jail` com
`allow_tcp_ports = [31xxx]` pra Claude na jaula acessar
`localhost:31xxx` do host. F6.0 spike provou que **isso é falso** em
ai-jail v0.10: `allow_tcp_ports = []` não bloqueia loopback do host.
Ver gotcha #17.

**Consequência:** `sandbox/aijail.py::write_aijail_config(cwd)` fica
intacto (assinatura igual pós-F5). `core/runs.py::start_run` NÃO toca
no `.ai-jail`. Simplifica F6.e (1 step a menos no rollback).

### PFC-2 — Port allocator é estado in-memory + reservas DB-backed

Range 31000-31999 = 1000 portas. Allocator vive em `app.state.port_allocator`.
Pra robustez contra restart do daemon:
- No startup, daemon carrega `ports_json` de todas as `run_instances` com
  `status` em `(pending, building, seeding, ready, stopping)` e marca as
  portas como reservadas.
- Allocator usa `socket.SOCK_STREAM.bind(('127.0.0.1', port))` pra detectar
  conflito com processos não-J-arvis. Se bind falha, pula porta.

### PFC-3 — `RunInstance.containers_json` é necessário pra cleanup confiável

Quando daemon crasha mid-run, containers podem ficar orfãos. Persistir
`{service_name: container_id}` permite cleanup honesto no startup:

```python
async def cleanup_orphan_containers_at_startup(db, docker):
    rows = await db.execute(select(RunInstance).where(
        RunInstance.ended_at.is_(None)
    ))
    for run in rows.scalars():
        containers = json.loads(run.containers_json)
        for name, cid in containers.items():
            try:
                await docker.stop(cid, force=True)
                await docker.rm(cid)
            except DockerError:
                pass  # já morto
        try:
            await docker.network_rm(run.network_name)
        except DockerError:
            pass
        run.status = "stopped"
        run.ended_at = _now()
    await db.commit()
```

### PFC-4 — SSE endpoint não é WS

Logs streaming usa **Server-Sent Events** (HTTP unidirecional do server pro
client), não WS. Razão: simpler client (EventSource builtin), backpressure
natural, fácil de cancelar (close connection). FastAPI suporta via
`StreamingResponse` com `media_type="text/event-stream"`. Cada linha de log
vai como `data: {service}\t{stream}\t{text}\n\n`.

### PFC-5 — Bootstrap session é separada de ClaudeSession

A "sessão Claude efêmera" pra propor manifesto **não** é uma `ClaudeSession`
(sem `task_id`, sem lifecycle compartilhado). É spawn direto via
`AiJailRuntime.spawn(project.path)` (cwd = project root, não worktree).
Daemon não rastreia o PID dela depois do spawn — file watcher é o sinal.

`api/bootstrap.py::POST /tasks/{id}/bootstrap-manifest`:
1. Verifica task válida (existe).
2. Inicia watch em `<project.path>/.orchestrator/` (cria dir se falta).
3. Spawn `runtime.spawn(project_path)` com prompt customizado.
4. Retorna 202 `BootstrapSessionRead{session_id, cwd}`.

### PFC-6 — File watcher pra `.orchestrator/run.yml`

Pra detectar quando Claude salvar o manifesto, daemon usa polling
(`asyncio.sleep(2)` em loop). Polling é mais simples e suficiente:
per-project watcher só ativa enquanto bootstrap pending.

```python
# Em api/bootstrap.py após spawn
async def watch_for_manifest(project_path: Path, db, broadcaster):
    target = project_path / ".orchestrator" / "run.yml"
    for _ in range(900):  # 30min total (900 * 2s)
        await asyncio.sleep(2)
        if target.exists():
            await broadcaster.publish(WsEvent.bootstrap_proposed(
                manifest_text=target.read_text()
            ))
            return
    # timeout: silently stop watching
```

Spawn este watcher como `asyncio.create_task(...)`. Cancel se nova
bootstrap_session for criada pro mesmo project.

### PFC-7 — Centralizar substituição de variáveis

`$PORT_<svc>`, `$URL_<svc>`, `$RUN_ID`, `$CWD` substituídos em `env` values
do manifest. Pure function em `core/manifest.py::resolve_substitutions()`.
Não substituir em `command`, `image`, `build` — só em `env` (escopo
controlado, evita injection acidentais).

### PFC-8 — `mount_source` default = True só pra serviços com `build:`

Se o serviço usa `image:` (pré-built, como `postgres:16`), `mount_source`
default = False (mountar source num postgres causa caos). Se usa `build:`
(custom Dockerfile), default = True.

Lógica em `manifest.py::ServiceSpec.effective_mount_source()`:
```python
def effective_mount_source(self) -> bool:
    if self.mount_source is not None:
        return self.mount_source
    return self.build is not None  # default
```

### PFC-9 — Concurrency: 1 run ativa por task (lock per-task)

`core/runs.py::start_run` usa `_per_task_lock` igual `start_session` de F5
(em `core/sessions.py`). Antes de criar `RunInstance`, checa via SELECT
existing com `ended_at IS NULL` AND `task_id=X`. Se encontra, 409.

### PFC-10 — Atomic 3-layer rollback (FS + DB + Docker)

Reuse padrão F5.d. `start_run` cria DB row em `pending`, então:
1. Build images (se falha → status=failed, broadcast, return)
2. Create network (se falha → cleanup imagens? só status=failed; imagens
   ficam pra cache)
3. Spawn containers (se algum falha mid-spawn → rollback: stop+rm os já
   criados, network_rm, status=failed)
4. Healthcheck loop (se timeout → cleanup todos, network_rm, status=failed)
5. Seed phase (similar)
6. status=ready

Cada falha emite WS `run.failed` com `service?` apontando o culpado.

### PFC-11 — Reusar gotchas #15/#16

- gotcha #15 (ai-jail aninhado): demo manual + E2E só rodam do host.
- gotcha #16 (`ai-jail` CLI v0.10): F6.0 reusa o `write_aijail_config`
  patched em F5.0.

### PFC-12 — Naming: evitar shadow do builtin `exec`

DockerOps Protocol expõe `container_exec`, **não** `exec` (que shadow do
builtin). Mesma razão pra `run` (shadow do builtin) — usar `container_run`.

## Disciplina

- TDD em cada sub-task: red → green → refactor.
- Coverage gate 100% em cada commit.
- Pre-commit code-reviewer subagent obrigatório.
- 1 commit por sub-task com padrão `feat(F6.X): ...` ou `fix(F6.X): ...`.
- Atualizar `gotchas.md` quando aprender algo novo.

---

## Task 0 — F6.0: Spike Docker network + ai-jail allow_tcp_ports

**Objetivo:** validar que (a) Docker bridge funciona pra inter-container,
(b) ai-jail com `allow_tcp_ports=[31xxx]` permite a sessão Claude bater
em `localhost:31xxx` do host onde Docker exposes. **Host-only (gotcha #15).**

**Files:** spike script `/tmp/f6-spike/` (não commitado).

- [ ] **Step 1: Setup synthetic — db postgres + app simples**

Subir 1 postgres + 1 nginx em network bridge nomeada. Verificar
inter-container DNS (postgres acessível por hostname `spike-db`).

- [ ] **Step 2: ai-jail com allow_tcp_ports acessando localhost:31100**

`.ai-jail` com `allow_tcp_ports = [31100]`, command que faz `curl
http://localhost:31100`. Expected: nginx HTML printado.

- [ ] **Step 3: Sem allow_tcp_ports (controle negativo)**

Mesma cwd, sem `allow_tcp_ports`. Expected: curl falha — confirma que a
config é necessária.

- [ ] **Step 4: Cleanup + Decisão**

Se Step 2 OK e Step 3 falha → proceed F6.a (rede + sandbox compatíveis).

---

## Task 1 — F6.a: Migration 0005 + `RunInstance` model + roundtrip

**Objetivo:** schema verde, model SQLAlchemy mapeado, integration test que cria/lê.

**Files:**
- `alembic/versions/0005_run_instances.py`
- `orchestrator/store/models.py`
- `tests/integration/test_models_run_instance.py`

- [ ] **Step 1: Migration 0005**

```python
"""run_instances table for F6"""
revision = "0005"
down_revision = "0004"

def upgrade() -> None:
    op.create_table(
        "run_instances",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("task_id", sa.String(32),
                  sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cwd", sa.String(1024), nullable=False),
        sa.Column("manifest_path", sa.String(1024), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("ports_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("containers_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("network_name", sa.String(255), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True),
                  server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_run_active", "run_instances", ["task_id"],
                    unique=True, sqlite_where=sa.text("ended_at IS NULL"))
```

- [ ] **Step 2: SQLAlchemy model** mirror da migration.
- [ ] **Step 3: Roundtrip integration test** — create + query active.
- [ ] **Step 4: Test parcial unique constraint** — 2 rows com mesmo task_id ambos `ended_at=None` → IntegrityError.
- [ ] **Step 5: Commit** `feat(F6.a): migration 0005 + RunInstance model`

---

## Task 2 — F6.b: `core/manifest.py` — Pydantic schema + substituição

**Objetivo:** parse + validate `.orchestrator/run.yml`; substitute
`$PORT_<svc>`, `$URL_<svc>`, `$RUN_ID`, `$CWD` em `env`.

**Files:**
- `orchestrator/core/manifest.py`
- `tests/unit/test_manifest.py`

- [ ] **Step 1: Schema Pydantic com `extra="forbid"`**

```python
class ServiceSpec(BaseModel):
    model_config = {"extra": "forbid"}
    image: str | None = None
    build: str | None = None
    dockerfile: str = "Dockerfile"
    command: list[str] | None = None
    env: dict[str, str] = Field(default_factory=dict)
    port: int | None = None
    depends_on: list[str] = Field(default_factory=list)
    healthcheck: HealthcheckSpec | None = None
    seed: SeedSpec | None = None
    mount_source: bool | None = None  # tri-state: None = auto

    @model_validator(mode="after")
    def _image_or_build(self):
        if not self.image and not self.build:
            raise ValueError("must specify either image or build")
        if self.image and self.build:
            raise ValueError("cannot specify both image and build")
        return self

    def effective_mount_source(self) -> bool:
        if self.mount_source is not None:
            return self.mount_source
        return self.build is not None
```

- [ ] **Step 2: Parser + erros tipados**

`ManifestError`, `ManifestMissingError`, `ManifestInvalidError(path, msg)`.
`load_manifest(project_path) -> ManifestSpec`.

- [ ] **Step 3: Substituição pure function**

```python
def resolve_substitutions(
    env: dict[str, str], *,
    ports_host: dict[str, int],
    run_id: str,
    cwd: str,
) -> dict[str, str]:
    """Substitui $PORT_<svc>, $URL_<svc>, $RUN_ID, $CWD em env values.
    Variáveis $KEY com prefixo desconhecido ficam intactas."""
```

- [ ] **Step 4: Tests cobrindo todos os ramos**

- válido mínimo (1 service `image:` only)
- válido com `build:`
- ambos image e build → erro
- nem image nem build → erro
- depends_on cíclico → erro
- depends_on referencia service inexistente → erro
- port duplicado entre services → erro
- substituição `$URL_backend` quando `backend` tem `port: 8000`
- substituição preserva `$HOME` (prefixo desconhecido)
- env vazio → dict vazio

- [ ] **Step 5: Commit** `feat(F6.b): manifest schema + load + substitutions`

---

## Task 3 — F6.c: `core/port_allocator.py`

**Objetivo:** alocar portas únicas em 31000-31999, validar via socket bind,
liberar no stop.

**Files:**
- `orchestrator/core/port_allocator.py`
- `tests/unit/test_port_allocator.py`

- [ ] **Step 1: API**

```python
class PortAllocator:
    """Range 31000-31999. Thread-safe via asyncio.Lock."""

    RANGE_START = 31000
    RANGE_END = 31999

    def __init__(self, socket_factory=None):
        self._reserved: set[int] = set()
        self._lock = asyncio.Lock()
        self._socket_factory = socket_factory or _default_socket_factory

    async def allocate(self) -> int: ...
    async def release(self, port: int) -> None: ...
    async def reserve(self, port: int) -> None: ...  # restore-from-DB
    def _is_free(self, port: int) -> bool: ...      # socket.bind probe
```

- [ ] **Step 2: Tests com FakeSocket**

- allocate retorna porta no range
- allocate skipa portas ocupadas (FakeSocket falha bind em N)
- exhaustion → NoFreePortError
- release devolve a porta pro pool
- reserve aceita porta sem bind
- concurrent allocate via 2 tasks asyncio retornam portas diferentes

- [ ] **Step 3: Commit** `feat(F6.c): port allocator com socket probe`

---

## Task 4 — F6.d: `sandbox/docker_ops.py` — Protocol + Subprocess

**Objetivo:** seam de teste pro Docker CLI; thin wrapper.

**Files:**
- `orchestrator/sandbox/docker_ops.py`
- `tests/unit/test_docker_ops.py`

- [ ] **Step 1: Protocol + tipos**

```python
@dataclass(frozen=True)
class ContainerSpec:
    name: str
    image: str
    network: str
    env: dict[str, str]
    port_map: dict[int, int] | None      # {host: container}
    volumes: list[tuple[str, str]] = ()
    command: list[str] | None = None

class DockerError(Exception):
    def __init__(self, msg: str, stderr: str = ""):
        super().__init__(msg)
        self.stderr = stderr

class DockerOps(Protocol):
    async def build(self, *, context: Path, dockerfile: str, tag: str) -> None: ...
    async def network_create(self, name: str) -> None: ...
    async def network_rm(self, name: str) -> None: ...
    async def container_run(self, spec: ContainerSpec) -> str: ...  # container_id
    async def container_exec(self, cid: str, cmd: list[str]) -> tuple[int, str, str]: ...
    async def stream_logs(self, cid: str) -> AsyncIterator[tuple[str, str]]: ...
    async def stop(self, cid: str, *, force: bool = False) -> None: ...
    async def rm(self, cid: str) -> None: ...
```

(Nomes `container_run`/`container_exec` evitam shadow dos builtins —
PFC-12.)

- [ ] **Step 2: SubprocessDockerOps**

Cada método usa `asyncio.create_subprocess_exec("docker", ...)` e parseia
output. Erros não-zero exit levantam `DockerError`. `stream_logs`
retorna async generator que stream linha a linha enquanto subprocess vivo.

- [ ] **Step 3: FakeDockerOps pra unit tests de outros módulos**

```python
class FakeDockerOps:
    def __init__(self):
        self.build_calls: list[tuple[Path, str, str]] = []
        self.run_calls: list[ContainerSpec] = []
        # ... pra cada método
        self.next_container_id = "abc123"
        self.build_raises: type[BaseException] | None = None
```

- [ ] **Step 4: Unit tests do SubprocessDockerOps**

Monkeypatch `asyncio.create_subprocess_exec` pra evitar docker real:
- build success → None
- build failure (exit≠0) → DockerError com stderr
- container_run com port_map → argv tem `-p host:container`
- container_run com volumes → argv tem `-v host:container`
- container_run com env → argv tem `-e KEY=VAL`
- stream_logs yields linhas até subprocess terminar

- [ ] **Step 5: Commit** `feat(F6.d): docker_ops protocol + subprocess impl`

---

## Task 5 — F6.e: `core/runs.py` — `start_run`, `stop_run`, state machine

**Objetivo:** core do feature. Orquestra docker_ops + port_allocator +
manifest + DB. State machine completa.

**Files:**
- `orchestrator/core/runs.py`
- `tests/unit/test_runs_core.py`
- `tests/integration/test_run_lifecycle.py`

- [ ] **Step 1: API**

```python
class RunStartError(Exception): pass
class RunAlreadyActiveError(RunStartError): pass
class TaskNotEligibleForRunError(RunStartError): pass

async def start_run(
    db, docker, port_allocator, broadcaster,
    *, task_id: str, cwd: Path, manifest: ManifestSpec,
) -> RunInstance:
    # 1. Lock por task; checa state in_progress/review
    # 2. INSERT RunInstance(status=pending)
    # 3. Topological sort dos serviços
    # 4. Alocar portas host pros services com port:
    # 5. Build images (broadcast run.status building)
    # 6. Create network
    # 7. Spawn containers em topological order
    # 8. Wait healthchecks
    # 9. Run seeds
    # 10. status=ready; broadcast run.status ready
    # Rollback em qualquer falha (atomic 3-layer)

async def stop_run(
    db, docker, port_allocator, broadcaster,
    *, run_id: str,
    reason: Literal["manual","session_stopped","task_terminal"],
) -> None: ...

async def get_active_run(db, task_id: str) -> RunInstance | None: ...
```

- [ ] **Step 2: Helpers internos**

- `_topo_sort(manifest)` — Kahn's algo, raises se cycle
- `_allocate_ports(services, allocator)` — chama `allocator.allocate()` por svc com `port:`
- `_build_image(docker, service, cwd)` — `docker.build` com tag
- `_run_container(docker, service_name, service_spec, host_ports, run_id, cwd)` — `docker.container_run`
- `_wait_healthy(docker, cid, healthcheck)` — loop com retries
- `_run_seed(docker, cid, seed)` — `docker.container_exec`
- `_rollback(docker, port_allocator, run, partial_state)` — limpa o criado

- [ ] **Step 3: Tests unit com FakeDockerOps**

- happy path 2 services com depends_on
- build fail no service 2 → service 1 fica limpo
- healthcheck timeout → status=failed
- seed crash → status=failed
- topological order: services com `depends_on: [db]` rodam depois de db
- ports alocados em ordem do manifest
- env vars com `$URL_*` substituídos
- stop_run idempotente (chamar 2x sem erro)

- [ ] **Step 4: Tests integration com CollectingBroadcaster**

- start_run cria DB row, broadcasta WS events em sequência
- stop_run zera ports e marca ended_at

- [ ] **Step 5: Commit** `feat(F6.e): start_run + stop_run + state machine`

---

## Task 6 — F6.f: API routes

**Objetivo:** wiring HTTP.

**Files:**
- `orchestrator/api/runs.py`
- `tests/integration/test_api_runs.py`

- [ ] **Step 1: Routers**

```python
router = APIRouter(prefix="/tasks/{task_id}/runs", tags=["runs"])

@router.post("", response_model=RunRead, status_code=201)
async def create_run(task_id: str, request: Request, db: ...):
    task = await get_task(db, task_id)
    if task.state not in ("in_progress", "review"):
        raise HTTPException(422, "task not eligible")
    project = await get_project(db, task.project_id)
    try:
        manifest = load_manifest(Path(project.path))
    except ManifestMissingError:
        raise HTTPException(422, detail={
            "error": "manifest_missing",
            "bootstrap_url": f"/api/tasks/{task_id}/bootstrap-manifest",
        })
    except ManifestInvalidError as e:
        raise HTTPException(422, detail={"error": "manifest_invalid", "path": e.path})

    cwd = await _derive_cwd_for_task(db, task)
    run = await start_run(db, request.app.state.docker_ops,
                          request.app.state.port_allocator,
                          request.app.state.ws_broadcaster,
                          task_id=task_id, cwd=cwd, manifest=manifest)
    return _to_run_read(run)

router_runs = APIRouter(prefix="/runs", tags=["runs"])

@router_runs.post("/{run_id}/stop", status_code=204)
async def stop(run_id: str, request: Request, db: ...): ...

@router_runs.get("/{run_id}/logs")
async def logs(run_id: str, service: str, request: Request, db: ...):
    # StreamingResponse com text/event-stream usando docker.stream_logs
    ...
```

- [ ] **Step 2: Wire em main.py**

```python
app.state.port_allocator = PortAllocator()
app.state.docker_ops = SubprocessDockerOps()
@app.on_event("startup")
async def _cleanup_orphan_runs():
    async with session_factory() as db:
        await cleanup_orphan_containers_at_startup(db, app.state.docker_ops)
```

- [ ] **Step 3: Tests integration**

- POST /tasks/{id}/runs com task in_progress + manifest válido → 201
- POST com task em backlog → 422
- POST com manifest faltando → 422 com bootstrap_url
- POST com manifest inválido → 422 com path
- POST 2x mesma task → 1ª 201, 2ª 409
- POST /runs/{id}/stop → 204
- POST /runs/{id}/stop em run já stopped → 204 (idempotent)
- GET /tasks/{id}/run com run ativa → 200 RunRead
- GET /tasks/{id}/run sem run → 404
- GET /runs/{id}/logs streaming (FakeDockerOps emite N linhas)

- [ ] **Step 4: Commit** `feat(F6.f): API routes /api/tasks/{id}/runs + /api/runs/{id}`

---

## Task 7 — F6.g: WS envelope events + broadcasts

**Objetivo:** factories pros 5 eventos novos; instrumentar pontos de transição.

**Files:**
- `orchestrator/events/envelope.py`
- `tests/unit/test_envelope_run_events.py`

- [ ] **Step 1: Factories**

```python
@classmethod
def run_status(cls, *, task_id, run_id, status, services=()) -> "WsEvent": ...

@classmethod
def run_log(cls, *, task_id, run_id, service, stream, text) -> "WsEvent": ...

@classmethod
def run_failed(cls, *, task_id, run_id, service, error) -> "WsEvent": ...

@classmethod
def run_stopped(cls, *, task_id, run_id, reason) -> "WsEvent": ...

@classmethod
def bootstrap_proposed(cls, *, manifest_text) -> "WsEvent":
    return cls(type="bootstrap.proposed", session_id="", task_id=None, ...)
```

- [ ] **Step 2: Instrumentar `core/runs.py`**

Cada transição emite `run.status`. Logs durante build emitem `run.log`
batched. **Não** broadcast logs durante runtime — usar SSE endpoint
exclusivo (PFC-4).

- [ ] **Step 3: Tests unit**

Cada factory: shape correto, task_id no envelope (exceto bootstrap onde
é None), at parseável.

- [ ] **Step 4: Commit** `feat(F6.g): WS factories run.* + bootstrap.proposed`

---

## Task 8 — F6.h: Bootstrap session + file watcher

**Objetivo:** spawn sessão Claude efêmera + detectar manifesto salvado.

**Files:**
- `orchestrator/api/bootstrap.py`
- `orchestrator/core/bootstrap.py`
- `tests/integration/test_bootstrap_session.py`

- [ ] **Step 1: Endpoint**

```python
@router.post("/tasks/{task_id}/bootstrap-manifest",
             response_model=BootstrapSessionRead, status_code=202)
async def bootstrap_manifest(task_id, request, db):
    task = await get_task(db, task_id)
    project = await get_project(db, task.project_id)
    project_path = Path(project.path)
    (project_path / ".orchestrator").mkdir(exist_ok=True)

    runtime = request.app.state.session_runtime
    handle = await runtime.spawn(project_path)

    asyncio.create_task(watch_for_manifest(
        project_path, request.app.state.ws_broadcaster
    ))

    return BootstrapSessionRead(session_id=uuid4().hex, cwd=str(project_path))
```

- [ ] **Step 2: File watcher**

`core/bootstrap.py::watch_for_manifest(project_path, broadcaster)`:
polling 2s, timeout 30min. Quando detecta arquivo → broadcast event.

- [ ] **Step 3: Tests integration**

- POST /bootstrap-manifest com manifest inexistente → 202, .orchestrator/ criado
- Watcher detecta manifest novo → broadcasta event
- Idempotência: 2 bootstrap requests pro mesmo project não duplicam events

- [ ] **Step 4: Commit** `feat(F6.h): bootstrap session efêmera + file watcher`

---

## Task 9 — F6.i: UI lib

**Objetivo:** types TS + hooks + SSE client.

**Files:**
- `ui/src/lib/api.ts` (MOD)
- `ui/src/lib/events.ts` (MOD)
- `ui/src/lib/runSseClient.ts` (NOVO)
- `ui/src/hooks/useRun.ts` (NOVO)
- `ui/src/hooks/useRunLogs.ts` (NOVO)
- `ui/src/hooks/useSessionEvents.ts` (MOD)

- [ ] **Step 1: types Run/ServiceStatus**

```typescript
export interface ServiceStatus {
  name: string;
  state: 'building'|'seeding'|'ready'|'failed'|'stopped';
  port_host: number | null;
  port_container: number | null;
  container_id: string | null;
  error: string | null;
}
export interface Run {
  id: string;
  task_id: string;
  cwd: string;
  status: 'pending'|'building'|'seeding'|'ready'|'failed'|'stopping'|'stopped';
  services: ServiceStatus[];
  network_name: string;
  started_at: string;
  ended_at: string | null;
  error_message: string | null;
}
```

- [ ] **Step 2: api endpoints**

`api.startRun(taskId)`, `api.stopRun(runId)`, `api.getActiveRun(taskId)`,
`api.bootstrapManifest(taskId)`.

- [ ] **Step 3: SSE client**

```typescript
export function createLogsSse(runId: string, service: string, onLine: (l: LogLine) => void) {
  const es = new EventSource(`/api/runs/${runId}/logs?service=${service}`);
  es.onmessage = (ev) => onLine(JSON.parse(ev.data));
  return { close: () => es.close() };
}
```

- [ ] **Step 4: hooks**

`useRun(taskId)`: query (refetch on `run.status` WS).
`useStartRun(taskId)` / `useStopRun(runId)`: mutations.
`useRunLogs(runId, service)`: buffer ring (500 lines) + auto-attach SSE.

- [ ] **Step 5: useSessionEvents extension**

Handlers pra `run.status`, `run.failed`, `run.stopped` invalidam query
de runs. `bootstrap.proposed` dispatch toast.

- [ ] **Step 6: Tests**

Types compilam contra `exactOptionalPropertyTypes`. SSE client parse
correto. hooks: useRun retorna null quando 404. 100% coverage.

- [ ] **Step 7: Commit** `feat(F6.i): UI lib api.ts + hooks useRun/useRunLogs + SSE client`

---

## Task 10 — F6.j: UI components

**Objetivo:** RunStatus, RunTab, RunLogsPanel, BootstrapModal,
ServiceStatusBadge.

**Files:** `ui/src/components/Run*.tsx` + tests; MOD TaskCard, TaskDetailModal.

- [ ] **Step 1: ServiceStatusBadge**

Span com classe `badge-${state}`, icon + nome do serviço.

- [ ] **Step 2: RunStatus (TaskCard footer)**

Lê `useRun(taskId)`. Conditional render:
- null → botão `▶ Run`
- pending/building/seeding → spinner + label
- ready → chips clicáveis (`<a href="http://localhost:PORT">`) + Stop
- failed → ✗ + "Ver logs" abre modal
- stopped/no-active → botão Run de novo

- [ ] **Step 3: RunTab (TaskDetailModal)**

Tab que mostra: status grande + serviços badges + `<RunLogsPanel />`.

- [ ] **Step 4: RunLogsPanel**

- Dropdown filtro por serviço
- Buffer ring 500 linhas
- Auto-scroll bottom; "pause" ao scrollar pra cima

- [ ] **Step 5: BootstrapModal**

Disparado por 422 manifest_missing no startRun. Botão "Iniciar bootstrap"
→ `api.bootstrapManifest(taskId)`. Listen `bootstrap.proposed` → fecha
modal + toast.

- [ ] **Step 6: TaskCard + TaskDetailModal mod**

`<RunStatus task={task} />` no rodapé do card. `<RunTab />` no modal.

- [ ] **Step 7: Tests unit (vitest)**

Cada componente: render condicional, click handlers, mock api responses.
Coverage 100% nos arquivos novos.

- [ ] **Step 8: Commit** `feat(F6.j): UI components — RunStatus + RunTab + LogsPanel + BootstrapModal`

---

## Task 11 — F6.k: E2E + ARCHITECTURE + ADRs + demo

**Objetivo:** fechamento.

**Files:**
- `tests/e2e/test_f6_simple_run_flow.py`
- `tests/e2e/test_f6_bootstrap_missing_manifest.py`
- `ARCHITECTURE.md` (MOD §3, §11, §13)
- `docs/adr/0018-run-instance-detalhe-da-task.md`
- `docs/adr/0019-manifest-services-dict-com-depends-on.md`
- `docs/adr/0020-bootstrap-via-sessao-claude-efemera.md`
- `docs/adr/README.md` (MOD)

- [ ] **Step 1: E2E `test_f6_simple_run_flow.py`**

Conftest fixture: `orchestrator_with_run_ready_project` com manifesto
preset (nginx-only, ou mock que não exige rede externa).

Flow: cria projeto, criar task, iniciar sessão, ▶ Run, espera ready,
verifica chip aparece, ⏹ Stop, verifica container/network não existem.

- [ ] **Step 2: E2E `test_f6_bootstrap_missing_manifest.py`**

Projeto sem manifesto → ▶ Run → modal "Manifesto faltando" → click
Bootstrap → endpoint chamado.

- [ ] **Step 3: ADR-0018** — RunInstance é detalhe da Task.
- [ ] **Step 4: ADR-0019** — Manifest `services:` dict + depends_on.
- [ ] **Step 5: ADR-0020** — Bootstrap via sessão efêmera.

- [ ] **Step 6: ARCHITECTURE updates**

§3: adicionar `RunInstance`.
§11: marcar F6 ✅.
§13: 3 rows novas.

- [ ] **Step 7: docs/adr/README.md** — 3 entries.

- [ ] **Step 8: Coverage gate final**

```bash
unset VIRTUAL_ENV && uv run --group test-unit --group test-integration python -m pytest tests/unit tests/integration --cov=orchestrator --cov-fail-under=100
cd ui && CI=true pnpm coverage
```

- [ ] **Step 9: E2E run (do host)**

- [ ] **Step 10: Code review final** (subagent superpowers:code-reviewer)

"Review entire F6 branch from F5 end. Verify against spec decisions
#1-17; every test in §12 exists; ARCHITECTURE/ADRs reflect."

- [ ] **Step 11: Demo manual (host, §16 do spec)**

- [ ] **Step 12: Commit final** `test(F6.k): E2E + ARCHITECTURE + ADRs + demo`

---

## Encerramento — checklist final F6

- [ ] Todos os tests F1/F2/F4/F5 pré-existentes passam (regressão zero)
- [ ] `uv run pytest tests/unit -q`: 100% verde
- [ ] `uv run pytest tests/integration -q`: 100% verde
- [ ] `pnpm --dir ui exec vitest run`: 100% verde
- [ ] `uv run pytest tests/e2e -v`: passa (do host)
- [ ] `--cov=orchestrator --cov-fail-under=100`: 100%
- [ ] Demo manual (12 passos do spec §16) executada
- [ ] `git log --oneline | head -15` mostra commits F6.X consecutivos
- [ ] `gotchas.md` atualizada com aprendizados novos (se aplicável)
- [ ] Push da branch — fora da jaula
- [ ] Marcar F6 ✅ em ARCHITECTURE.md §11
