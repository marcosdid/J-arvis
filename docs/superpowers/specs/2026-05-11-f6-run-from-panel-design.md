# F6 — Run from Panel (design spec)

- **Data:** 2026-05-11
- **Autor:** Marcos
- **Status:** Proposed

## 1. Objetivo

Adicionar botão `▶ Run` no `TaskCard` (e no `TaskDetailModal`) que:

1. Lê `<project.path>/.orchestrator/run.yml` (manifesto commitado).
2. Sobe a stack inteira (DB + serviços) dentro do `cwd` da task — 1 sessão
   Docker-network compartilhada entre os containers.
3. Mostra URLs `🌐 :PORT` clicáveis no card quando os serviços ficam `ready`.
4. Para a stack automaticamente quando:
   - usuário clica `⏹ Stop Run` (manual),
   - sessão Claude da mesma task termina (auto), ou
   - task transita pra `done`/`discarded` (auto, junto com cleanup F5).

Quando o manifesto não existe, daemon abre uma sessão Claude **efêmera**
(não vinculada à task) com prompt *"leia o repo e proponha
`.orchestrator/run.yml`"*; usuário revisa, salva e commita.

## 2. Não-objetivos

- Cluster / orquestração distribuída.
- Uso em produção. F6 é dev-only: stack descartável, sem TLS/auth/etc.
- Hot reload custom (depende do app interno: `uvicorn --reload`,
  `nodemon`, `vite`). Daemon só monta o volume.
- Suporte a Podman, containerd, Kubernetes, etc. ADR-0006 fixou Docker.
- Substituto de `docker-compose` em produção — é abstração leve focada
  no fluxo "1 task = 1 stack efêmera".

## 3. Decisões fechadas

| # | Decisão | Escolha | Por quê |
|---|---|---|---|
| 1 | Entry point UI | Botão `▶ Run` no `TaskCard` + no `TaskDetailModal` | 1 run por task; modelo task-first preservado |
| 2 | Localização do manifesto | 1 arquivo em `<project.path>/.orchestrator/run.yml` (commitado) | ADR-0005; manifesto faz parte do projeto |
| 3 | Lifecycle | 3 camadas: manual `▶/⏹` + auto-stop ao parar sessão + auto-stop em `done`/`discarded` | Controle explícito + safety nets evitam container fantasma |
| 4 | Bootstrap (manifesto faltando) | Daemon spawna sessão Claude efêmera *"propor manifesto"*; usuário revisa+commita | Coerente com ADR-0005; não-acoplado a task atual |
| 5 | Schema do manifesto | `services:` dict + `depends_on` entre serviços (estilo docker-compose) | Cobre N serviços (db, cache, backend, frontend, workers) |
| 6 | Container engine | Docker direto (sem Protocol/abstração de runtime) | YAGNI; ADR-0006 |
| 7 | DB schema | `RunInstance(id, task_id, cwd, manifest_path, status, ports_json, started_at, ended_at)` | Paralelo a `ClaudeSession` pós-F5 |
| 8 | Run ↔ Session | Run **independente** de Session — só exige task em `in_progress`/`review` | Permite "olhar a UI" sem abrir Claude |
| 9 | Logs | Streamados via WS pra aba "Run" no `TaskDetailModal` | Diagnóstico rápido de build fail |
| 10 | Como URLs aparecem | Chips clicáveis (`🌐 backend :31101`) no `TaskCard` + modal | Visual, 1 click pra abrir |
| 11 | Hot reload | Default ON: daemon faz `-v <cwd>/<svc>:/app`; opt-out via `mount_source: false` | 80% dos casos têm reload via tooling do app |

**Derivadas (não-perguntáveis):**

| 12 | Port range | 31000-31999 (ADR-0005/ARCHITECTURE §6) | já fixado |
| 13 | Network | 1 Docker bridge por Run: `jarvis-run-<run_id>`; serviços se acham por `<service_name>` interno | isolamento por run |
| 14 | Acesso da sessão Claude | `.ai-jail` ganha `allow_tcp_ports = [31xxx]` dinâmico no spawn (reuso do F5.0 fix) | jail vê só as portas necessárias |
| 15 | Image tagging | `jarvis-run-<project_id>-<service>` (cache entre tasks do mesmo projeto) | rebuild rápido |
| 16 | Build context | Paths no manifesto são relativos ao `cwd` da task (não a `project.path`) | hot reload + build veem o estado da worktree |
| 17 | Manifesto resolution | Daemon copia `<project.path>/.orchestrator/run.yml` → `<cwd>/.orchestrator/run.yml` antes do build | builds rodam contra o snapshot da task |

## 4. Modelo de dados — migration 0005

### 4.1 Schema novo / modificado

**Nova tabela `run_instances`:**

```python
class RunInstance(Base):
    __tablename__ = "run_instances"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    cwd: Mapped[str] = mapped_column(String(1024), nullable=False)
    manifest_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    # state ∈ {pending, building, seeding, ready, failed, stopping, stopped}
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    # JSON object: {"backend": 31101, "frontend": 31102, ...}
    ports_json: Mapped[str] = mapped_column(Text(), nullable=False, default="{}")
    # JSON object: {"backend": "<container_id>", ...} pra cleanup
    containers_json: Mapped[str] = mapped_column(Text(), nullable=False, default="{}")
    network_name: Mapped[str] = mapped_column(String(255), nullable=False)
    started_at: Mapped[datetime] = mapped_column(default=_now, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
```

**Invariants:**
- `UniqueConstraint(task_id)` parcial onde `ended_at IS NULL`
  (1 run ativa por task; runs finalizadas acumulam histórico).
- `cwd` é o mesmo da `ClaudeSession.cwd` se a task tem session ativa.
  Daemon valida: se task tem session, usa o cwd da session; senão deriva
  do mesmo jeito (`<dirname(project.path)>/<basename(project.path)>--<branch>`).
- Status terminal: `failed`, `stopped`. Status ativos: `pending`, `building`,
  `seeding`, `ready`, `stopping`.

### 4.2 Migration 0005 — upgrade

```python
def upgrade() -> None:
    op.create_table("run_instances", ...)
    # Sem backfill: RunInstance é entidade nova, não há F1-F5 com runs ativos.
```

### 4.3 Migration downgrade

```python
def downgrade() -> None:
    op.drop_table("run_instances")
```

## 5. API surface

### 5.1 Endpoints novos

| Método | Path | Comportamento |
|---|---|---|
| `POST` | `/api/tasks/{task_id}/runs` | Inicia stack. 201 com `RunRead`. 409 se já tem run ativa; 422 se manifesto inválido/faltando (com hint pra bootstrap); 422 se task não está em `in_progress`/`review` |
| `POST` | `/api/runs/{run_id}/stop` | Para a stack. 204 idempotente. Cleanup containers + network + DB row marca `stopped` |
| `GET`  | `/api/tasks/{task_id}/run` | Retorna `RunRead` da run ativa da task; 404 se não tem |
| `GET`  | `/api/runs/{run_id}/logs?service=<name>` | Stream Server-Sent-Events com stdout+stderr do container do serviço |
| `POST` | `/api/tasks/{task_id}/bootstrap-manifest` | Spawn sessão Claude efêmera "propor manifesto". Retorna `BootstrapSessionRead` (separada de ClaudeSession comum) |

### 5.2 Schemas Pydantic

```python
class ServiceStatus(BaseModel):
    model_config = {"extra": "forbid"}
    name: str
    state: Literal["building", "seeding", "ready", "failed", "stopped"]
    port_host: int | None = None      # porta exposta no host, se aplicável
    port_container: int | None = None # porta interna do container
    container_id: str | None = None
    error: str | None = None

class RunRead(BaseModel):
    model_config = {"extra": "forbid"}
    id: str
    task_id: str
    cwd: str
    manifest_path: str
    status: Literal["pending", "building", "seeding", "ready", "failed", "stopping", "stopped"]
    services: list[ServiceStatus]
    network_name: str
    started_at: datetime
    ended_at: datetime | None
    error_message: str | None

class BootstrapSessionRead(BaseModel):
    model_config = {"extra": "forbid"}
    session_id: str  # ID da sessão Claude efêmera (sem task_id)
    cwd: str
```

### 5.3 WS events novos (envelope do ADR-0010 + 0014)

| Event type | task_id presente | payload |
|---|---|---|
| `run.status` | sim | `{run_id, status, services?: [...]}` — fired em cada transição |
| `run.log` | sim | `{run_id, service, stream: "stdout"\|"stderr", text}` — high-frequency, batched no client |
| `run.failed` | sim | `{run_id, service?, error}` — terminal; UI mostra toast |
| `run.stopped` | sim | `{run_id, reason: "manual"\|"session_stopped"\|"task_terminal"}` |
| `bootstrap.proposed` | não (efêmera) | `{session_id, manifest_text}` — Claude propôs; UI mostra diff |

## 6. Manifest schema — `.orchestrator/run.yml`

### 6.1 Estrutura formal

```yaml
# Top-level
version: "1"                          # required, gates futura compat
services:                             # required, dict não-vazio
  <service_name>:                     # alfanumérico + hífens
    image: <docker-image>             # OR build: <path>; um dos dois é required
    build: <relative-path>            # context do docker build (relativo ao cwd da task)
    dockerfile: <path>                # opcional, default "Dockerfile" dentro do build context
    command: [<argv>...]              # opcional, override do CMD
    env:                              # opcional, dict env vars
      KEY: VALUE                      # daemon substitui $PORT_<service>, $URL_<service>, $RUN_ID
    port: <int>                       # opcional; se presente, daemon expõe host:host_port → container:port
    depends_on: [<service_name>, ...] # opcional; daemon garante ordem + healthcheck
    healthcheck:                      # opcional
      command: [<argv>...]
      interval: <seconds, default 2>
      retries: <int, default 30>
    seed:                             # opcional, roda 1x após healthcheck OK, antes de marcar ready
      command: [<argv>...]
    mount_source: <bool>              # default true (hot reload); false pra db/cache/etc
```

### 6.2 Exemplo (gcb-hub multi-repo)

```yaml
version: "1"
services:
  db:
    image: postgres:16
    port: 5432
    env:
      POSTGRES_USER: dev
      POSTGRES_PASSWORD: dev
      POSTGRES_DB: gcbhub
    healthcheck:
      command: ["pg_isready", "-U", "dev"]
    seed:
      command: ["psql", "-U", "dev", "-d", "gcbhub", "-f", "/seed.sql"]
    mount_source: false

  backend:
    build: ./backend
    port: 8000
    env:
      DATABASE_URL: "postgresql://dev:dev@db:5432/gcbhub"
    depends_on: [db]
    healthcheck:
      command: ["curl", "-f", "http://localhost:8000/health"]

  frontend:
    build: ./frontend
    port: 5173
    command: ["pnpm", "dev", "--host", "0.0.0.0", "--port", "5173"]
    env:
      VITE_API_URL: "$URL_backend"   # substituído pelo daemon: http://localhost:31101
    depends_on: [backend]
```

### 6.3 Substituições suportadas (daemon-side)

| Variável | Resolve pra |
|---|---|
| `$PORT_<service>` | porta **host** alocada pro serviço (31xxx) |
| `$URL_<service>` | `http://localhost:$PORT_<service>` (acessível do host e da jail) |
| `$RUN_ID` | ID da run (primeiros 8 chars do uuid hex, convenção Docker short SHA) |
| `$CWD` | path absoluto do cwd da task |

Variáveis `$KEY` que **não** começam com `$PORT_/$URL_/$RUN_ID/$CWD` ficam inalteradas (deixadas pro container resolver, e.g. `$HOME`).

### 6.4 Validação Pydantic

`core/manifest.py` parseia o yml com Pydantic v2 + `extra="forbid"`. Erros
viram 422 com path JSON do campo inválido (`services.backend.port: must be int`).

## 7. Network topology

```
host
├── 31100 ──┐
├── 31101 ──┤   docker network "jarvis-run-<short_id>"
├── 31102 ──┤   ├── db (postgres:16, internal :5432)
│           │   ├── backend (jarvis-run-<proj>-backend, internal :8000)
│           │   └── frontend (jarvis-run-<proj>-frontend, internal :5173)
└── ai-jail (cwd da task, allow_tcp_ports = [31100, 31101, 31102])
    └── claude
```

- Cada container expõe `port_container` na network bridge.
- Daemon mapeia `port_host (31xxx) → port_container` no `docker run`.
- Serviços se acham por DNS Docker: `backend` → IP do container backend
  na network bridge (sem porta host envolvida).
- Sessão Claude na ai-jail acessa via `localhost:31xxx` (não o IP da network).
- F5.0 `write_aijail_config` é estendido pra adicionar `allow_tcp_ports`
  quando a task tem run ativo.

## 8. State machine

```
        ┌──────────┐
        │ pending  │  (POST /runs criou row; nada rodando ainda)
        └────┬─────┘
             ▼
        ┌──────────┐
        │ building │  (docker build em cada serviço com build:)
        └────┬─────┘
             ▼
        ┌──────────┐
        │ seeding  │  (containers up + healthchecks + seed commands)
        └────┬─────┘
             ▼
        ┌──────────┐                         ┌──────────┐
        │  ready   │ ─── ⏹ Stop / session ──▶│ stopping │
        └──────────┘     stop / task term.   └────┬─────┘
                                                  ▼
                                            ┌──────────┐
                                            │ stopped  │ (terminal)
                                            └──────────┘

       any → ┌─────────┐
             │ failed  │ (build err, healthcheck timeout, seed crash)
             └─────────┘  terminal; error_message populado
```

Transições inválidas retornam 422.

## 9. Bootstrap UX — manifesto faltando

1. User clica `▶ Run` no `TaskCard` de uma task em `in_progress`.
2. Daemon: `POST /tasks/{id}/runs` → checa `<project.path>/.orchestrator/run.yml`.
3. Não existe → 422 `ManifestMissingError` com payload:
   `{error: "manifest_missing", bootstrap_url: "/api/tasks/{id}/bootstrap-manifest"}`.
4. UI mostra modal: *"Manifesto faltando. Iniciar bootstrap?"* → botão
   "Iniciar bootstrap" → POST pra `bootstrap_url`.
5. Daemon spawn sessão Claude **efêmera** (não-vinculada a task) com:
   - cwd = `project.path`
   - prompt inicial: *"leia este repo e proponha
     `.orchestrator/run.yml` seguindo o schema F6.
     Identifique serviços (DB, backend, frontend, etc), portas, comandos
     de build/start, healthchecks. Salve o arquivo no caminho indicado."*
   - sem token de hook (sessão efêmera; UI não rastreia status como task).
6. Usuário interage com Claude no terminal nativo. Quando satisfeito,
   Claude salva `.orchestrator/run.yml` e commita.
7. Daemon emite `bootstrap.proposed` quando detecta o arquivo (file watch
   em `project.path/.orchestrator/`).
8. UI recebe WS, mostra toast: *"Manifesto pronto. Tente `▶ Run` de novo."*

**Edge cases:**
- Claude pode abandonar sem salvar — daemon não força nada. Próximo `▶ Run`
  refaz o flow.
- Manifesto inválido (Pydantic erro) — bootstrap não detecta; o próximo
  `▶ Run` retorna 422 com path do erro. Usuário re-edita.

## 10. Frontend

### 10.1 Mudanças em componentes existentes

| Arquivo | Mudança |
|---|---|
| `TaskCard.tsx` | + bloco `<RunStatus task={task} />` no rodapé do card |
| `TaskDetailModal.tsx` | + tab "Run" (lazy-load), exibe URLs + logs streaming + start/stop |
| `useSessionEvents.ts` | + handlers `run.status`, `run.log` (batched), `run.failed`, `run.stopped`, `bootstrap.proposed` |

### 10.2 Componentes novos

```
ui/src/components/
├── RunStatus.tsx           — chips de URL no TaskCard
├── RunTab.tsx              — tab "Run" do TaskDetailModal
├── RunLogsPanel.tsx        — streaming de logs por serviço (com filtro)
├── BootstrapModal.tsx      — modal "Manifesto faltando" + botão iniciar
└── ServiceStatusBadge.tsx  — badge per-service no RunTab
```

### 10.3 RunStatus (TaskCard footer)

```
┌─ TaskCard ────────────────────┐
│ ● projA                       │
│ Add OAuth                     │
│ [in-progress]                 │
│ ┌─ Run ─────────────────────┐ │
│ │ ● ready  [⏹ Stop]         │ │
│ │ 🌐 backend  :31101        │ │
│ │ 🌐 frontend :31102        │ │
│ └───────────────────────────┘ │
└───────────────────────────────┘
```

Quando não há run ativa: footer mostra `[▶ Run]` simples. Em building/seeding:
spinner + `Building backend...`. Em failed: `✗ Failed: <error>` clicável
abre modal logs.

### 10.4 RunLogsPanel

- Stream via SSE de `/api/runs/{id}/logs?service=<name>`.
- Buffer client-side: últimas 500 linhas por serviço.
- Filtro por serviço (dropdown).
- Auto-scroll bottom; "pause" ao scrollar pra cima.

## 11. Edge cases & error handling

| Cenário | Comportamento |
|---|---|
| Port range exausto (31000-31999 todos ocupados) | 422 "no free port"; raro |
| `port:` duplicado entre serviços do mesmo manifesto | 422 validação na Pydantic |
| Dependência cíclica em `depends_on` | 422 validação |
| Build fail | run.status = `failed`, error_message com tail do stderr; toast UI |
| Healthcheck timeout (default 30 tentativas × 2s = 60s) | run.status = `failed` com nome do serviço |
| Container crash mid-ready | run.status volta pra `failed`; logs preservados; sem auto-restart |
| `docker` binary não disponível | 500 "docker not installed"; check at startup |
| User clica Stop durante building | aborta build, status → `stopped`, cleanup parcial |
| Manifesto editado durante run | mudanças só efetivas no próximo run; cópia em `<cwd>/.orchestrator/run.yml` é snapshot |
| Network bridge orfão (daemon crashou) | startup do daemon limpa `jarvis-run-*` networks sem RunInstance ativa |
| Task vira `done`/`discarded` com run ativa | cleanup do F5 chama stop_run antes de remover worktrees |

## 12. Testes

### 12.1 Unit

```
tests/unit/
├── test_manifest.py          — Pydantic schema, $PORT_/$URL_/$RUN_ID/$CWD substitution
├── test_run_lifecycle.py     — state transitions, terminal states
├── test_port_allocator.py    — range 31000-31999, exhaustion, release
└── test_docker_ops.py        — ContainerOps Protocol fake (build/run/stop/network)
```

### 12.2 Integration

```
tests/integration/
├── test_api_runs.py          — POST/DELETE/GET /api/tasks/{id}/runs com DB real
├── test_run_failure.py       — build fail, healthcheck timeout, crash mid-ready
└── test_run_cleanup_on_task_terminal.py  — task done → run stopped + worktrees gone
```

### 12.3 E2E (do host, fora da jaula — gotcha #9)

```
tests/e2e/
├── test_f6_simple_run_flow.py       — add proj com manifesto → criar task → ▶ Run → ready → ⏹ Stop
└── test_f6_bootstrap_missing_manifest.py — proj sem manifesto → ▶ Run → bootstrap toast
```

### 12.4 UI tests (vitest)

```
ui/src/components/
├── RunStatus.test.tsx
├── RunTab.test.tsx
├── RunLogsPanel.test.tsx
└── BootstrapModal.test.tsx
```

## 13. Rollout — sub-tasks F6.0 → F6.k

| # | Sub-task | Entregável | Dependências |
|---|---|---|---|
| F6.0 | Spike Docker network + ai-jail allow_tcp_ports | Validar do host: containers up, jail acessa via localhost:31xxx | gotcha #15 (host-only) |
| F6.a | Migration 0005 + `RunInstance` model + roundtrip | Schema verde | F6.0 |
| F6.b | `core/manifest.py` — Pydantic schema + substituição | Pure function + unit tests | — |
| F6.c | `core/port_allocator.py` — range 31000-31999 + reserve/release | Concurrency-safe (per-task lock) | — |
| F6.d | `core/docker_ops.py` — wrapper subprocess pro CLI docker + tests com FakeDockerOps | API ready | — |
| F6.e | `core/runs.py` — `start_run`, `stop_run`, state machine | Core layer ready | F6.a-d |
| F6.f | API routes `/api/tasks/{id}/runs`, `/api/runs/{id}/stop`, `/api/runs/{id}/logs` (SSE) | API surface ready | F6.e |
| F6.g | WS events `run.*`, `bootstrap.proposed` + broadcasts | UI escuta | F6.f |
| F6.h | Bootstrap session efêmera + file watcher pra `.orchestrator/run.yml` | Bootstrap UX | F6.f |
| F6.i | UI lib (api.ts types, hooks `useRun`, SSE consumer) | Frontend infra | F6.g |
| F6.j | UI components — `RunStatus`, `RunTab`, `RunLogsPanel`, `BootstrapModal`, `ServiceStatusBadge` | UI render | F6.h, F6.i |
| F6.k | E2E + ARCHITECTURE update + ADR-0018/0019/0020 + demo manual | Fechamento | F6.j |

## 14. Riscos

| Risco | Mitigação |
|---|---|
| Ports 31000-31999 colidem com outras coisas no host | Allocator faz `socket.bind` test antes de alocar; falha graceful → tenta próxima |
| Build do Docker é lento na 1ª vez | Cache de layers Docker default; image tag `jarvis-run-<proj>-<svc>` reusa |
| F5.0 + F6 = `.ai-jail` gerado por 2 fontes (worktree git_dirs + run ports) | Centralizar `write_aijail_config(cwd, *, git_dirs=..., extra_tcp_ports=...)` |
| User edita manifesto durante run ativa | Cópia em `<cwd>/.orchestrator/run.yml` é snapshot; daemon não relê durante run |
| Containers orfãos se daemon crashar | Cleanup no startup (`docker network ls | grep jarvis-run-`); RunInstance sem container_id válido vira `failed` |
| SSE pode lotar memória do client (logs infinitos) | Buffer client 500 linhas/serviço; servidor não armazena |
| Bootstrap session "infinita" — Claude não termina nem salva | UI mostra toast com link "Bootstrap aberto há Xmin"; user mata manualmente no terminal |
| `mount_source` exposed source code to container as `rw` — container pode corromper o disco | Docs: aceitar risco; usuário entendido das implicações |

## 15. ADRs novos

A escrever em F6.k:

- **ADR-0018** — RunInstance é detalhe da Task (paralelo a Worktree/Session pós-F5).
- **ADR-0019** — Manifesto formato `services:` + `depends_on` (rejeita roles fixas e full-stack-monolítico).
- **ADR-0020** — Bootstrap via sessão Claude efêmera (rejeita template inappar pré-preenchido).

## 16. Demo manual (F6.k, do host)

1. Subir daemon + UI.
2. Adicionar projeto `gcb-hub-fake` (`/tmp/demo-gcbhub/{backend,frontend}` cada um com `.git` + `Dockerfile` mock).
3. Criar task "Demo F6" → mover pra ready → iniciar sessão → in_progress.
4. Click `▶ Run` no card → modal "Manifesto faltando" → "Iniciar bootstrap".
5. Sessão Claude efêmera abre no terminal — type "salve um run.yml básico com db postgres e backend python".
6. Claude propõe `.orchestrator/run.yml` no `project.path` → WS toast.
7. Click `▶ Run` de novo → status muda building → seeding → ready.
8. URLs aparecem como chips no card → click `🌐 backend :31101` → browser abre.
9. Stop session no terminal Claude → run auto-stops (lifecycle 2).
10. Re-start session → `▶ Run` novamente → re-sobe stack (re-usa cwd + cache de layers).
11. Move task → review → ainda OK (run continua).
12. Move task → done via modal → run para automaticamente (lifecycle 3) + worktree cleanup (F5).

## 17. Referências

- `ARCHITECTURE.md` §3 (modelo de dados), §6 (Run from Panel), §11 (roadmap)
- ADR-0005 (manifesto explícito), ADR-0006 (DB descartável), ADR-0008 (terminal nativo)
- F5 spec (decisões #1/3/8 sobre 1 sessão por task; cleanup task-terminal)
- gotcha #9 (E2E fora da jaula), #15 (ai-jail não roda aninhado), #16 (`.ai-jail` config)
