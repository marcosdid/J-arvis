# Orquestrador Claude Code — arquitetura técnica

Documento ativo de arquitetura. Atualizar conforme decisões mudam. Para
contexto histórico do brainstorm, ver `CONTEXT.md`.

## 1. Princípios

1. **Sandbox-first** — orquestrador roda no host; toda sessão Claude Code
   roda dentro de jaula. Orquestrador supervisiona, não é o ambiente.
2. **Task-first** — `Task` é o objeto primário. `Session` é uma execução
   de uma task. UI gira em torno de tasks; sessões são detalhe.
3. **Local-only / single-user** — zero auth, zero rede externa por
   padrão, tudo via `localhost`.
4. **On-demand** — daemon sobe quando o usuário inicia, derruba quando
   fecha. Sem systemd, sem auto-start.
5. **TDD como regra de ferro** — ver §8.

## 2. Componentes

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (UI: React + Vite)                                 │
│   ↕ HTTP + WebSocket                                        │
├─────────────────────────────────────────────────────────────┤
│  Orchestrator daemon (Python + FastAPI) — fora da jaula     │
│  ├── api/        REST + WS                                  │
│  ├── core/       domínio: tasks, sessions                   │
│  ├── runtime/    Run from Panel (manifesto + Docker)        │
│  ├── sandbox/    SessionRuntime (backend ai-jail)           │
│  ├── hooks/      endpoints + parser de eventos              │
│  ├── store/      SQLite local                               │
│  └── planner/    meta-agente (v1.5)                         │
├─────────────────────────────────────────────────────────────┤
│  ai-jail (binário externo, Akita) — dependência do host     │
│   └── claude-code (1 processo por sessão)                   │
└─────────────────────────────────────────────────────────────┘
```

## 3. Modelo de dados (SQLite)

- `Project(id, name, path, created_at)`
- `Repository(id, project_id, name, sub_path, created_at)` *(F5)*
  - `UNIQUE(project_id, sub_path)`. Auto-detectado no `POST /api/projects` —
    monorepo gera 1 row com `sub_path="."`; multi-repo gera N rows (1 por
    sub-dir com `.git`). Ver [ADR-0015](docs/adr/0015-project-multi-repo-com-auto-detect.md).
- `Worktree(id, repository_id, task_id?, path, branch)` *(F5)*
  - `task_id NULL` = órfã (criada externamente via terminal). UI mostra
    sob sub-tree "órfãs" com botão `✕`. Ver [ADR-0017](docs/adr/0017-worktree-detalhe-da-task-sem-create-ui.md).
- `Task(id, project_id, title, description, state, branch?, template?, permission_profile?, created_at, updated_at)`
  - `state ∈ {idea, ready, in_progress, review, done, discarded}`
  - `branch` (F5): opcional. Vazio → daemon usa `slugify_for_branch(title)`.
    Imutável após 1ª sessão (422).
  - `template`/`permission_profile` populados em F7 quando user escolhe template no form de criar task. Tasks F4-F6 ficam NULL e usam fallback (`yolo`) do catálogo no spawn.
- `ClaudeSession(id, task_id, cwd, jail_id, status, pid, started_at, ended_at?, transcript_path)`
  - Classe nomeada `ClaudeSession` para não colidir com `sqlalchemy.orm.Session`/`AsyncSession`. Tabela `sessions`.
  - `cwd` (F5) substitui `worktree_id` da F1/F4: pra multi-repo `cwd` é o
    diretório-pai que contém N worktrees. Ver [ADR-0016](docs/adr/0016-multi-repo-1-sessao-cwd-shared.md).
  - `status ∈ {executing, awaiting_response, idle, error, done}`
- `RunInstance(id, task_id, cwd, manifest_path, status, ports_json, containers_json, network_name, started_at, ended_at?, error_message?)` *(F6)*
  - `status ∈ {pending, building, seeding, ready, failed, stopping, stopped}`
  - Partial unique `(task_id) WHERE ended_at IS NULL` → 1 run ativa por
    task. Ver [ADR-0018](docs/adr/0018-run-instance-detalhe-da-task.md).
  - `ports_json` mapa `{<service>: <host_port>}`; `containers_json` mapa
    `{<service>: <container_id>}` pra cleanup.

`claude-mem` cuida de memória entre sessões — não duplicar.

## 4. Comunicação Claude Code ↔ daemon

Hooks do Claude Code apontam para `http://localhost:<port>/api/hooks/<event>/<token>`
(token UUID por sessão, gerado em `start_session`, registrado em memória
e revogado em `stop_session`):

- `Notification` vira `awaiting_response` (final; ADR-0011 cancelou o
  refinamento via F3).
- `PreToolUse` é audit-only **definitivamente**: registra evento,
  broadcasta `session.tool_use`, retorna `{"continue": true}`. Decisão
  de permissão fica no terminal nativo do Claude (prompt `[y/n/always]`)
  + `permissions.allow`/`deny` no `settings.json` por projeto. Ver
  ADR-0011.
- `Stop` → marca `idle`.
- Leitura periódica do transcript para auto-resumo de 1 linha (v1.5).

Daemon → UI: WebSocket único em `/ws`, broadcast com envelope tipado
`{type, session_id, payload, at}`. Tipos atuais: `session.status`,
`session.tool_use`, `session.stopped`. Ver ADR-0009 (registro via
settings.json no jail) e ADR-0010 (envelope WS).

## 5. Sandbox

- Sessão = `ai-jail run -- claude-code <args>`
- Cada sessão recebe: 1 worktree montada + rede isolada + perfil de
  permissão da task + blocklist de comandos perigosos.
- `ai-jail` (Fabio Akita) é dependência **externa** do host. Linux only.
- Se `ai-jail` não der conta no futuro, trocamos por wrapper próprio
  (bwrap + Landlock + seccomp) **na mesma interface** `SessionRuntime` —
  zero ripple no resto do código.

## 6. Run from Panel

- Manifesto `.orchestrator/run.yml` no repo (commitado, parte do projeto).
- Bootstrap: se ausente, daemon abre sessão Claude efêmera com prompt
  "leia o repo, proponha manifesto" → usuário revisa → salva.
- Portas dinâmicas em `31000-31999`, exportadas como `PORT_*` para o
  manifesto.
- DB: `docker run --rm` por execução, com cache de imagem; seed roda
  após health check.
- Ambiente roda dentro da mesma jaula da worktree (rede só localhost
  da jaula; porta exposta ao host só pra UI).

## 7. Estrutura do repo

```
J-arvis/
├── pyproject.toml
├── Makefile
├── Dockerfile.orchestrator
├── orchestrator/
│   ├── __init__.py
│   ├── main.py
│   ├── api/
│   ├── core/
│   ├── runtime/
│   ├── sandbox/
│   ├── hooks/
│   ├── store/
│   └── planner/
├── ui/
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
├── tests/
│   ├── unit/                 # pytest, sem I/O
│   ├── integration/          # pytest + testcontainers
│   │   ├── conftest.py
│   │   └── routes/
│   └── e2e/                  # Playwright + testcontainers
│       ├── conftest.py
│       └── flows/
└── .orchestrator/
    └── run.yml               # dogfood do próprio orquestrador
```

## 8. Disciplina de desenvolvimento — TDD

Sem exceção:

1. **RED** — escrevo o teste, rodo, vejo falhar pelo motivo certo.
2. **GREEN** — código mínimo pra passar.
3. **REFACTOR** — limpo mantendo verde.

Não escrevo código de produção sem teste falhando antes. Não testo
"depois". Se quebrar a ordem, deleto e refaço.

## 9. Camadas de cobertura

| Camada | Stack | Alvo | Escopo |
|---|---|---|---|
| **Unit (Python)** | `pytest` + `pytest-asyncio` + `coverage.py` | **100%** | Lógica de domínio sem I/O. Usa fakes nas costuras. |
| **Integration (rotas)** | `pytest` + `httpx.AsyncClient` + `testcontainers-python` | **100% das rotas** | FastAPI real, SQLite real (arquivo temp), testcontainers do Docker para paths que tocam `RunInstance`. |
| **E2E (fluxos UI)** | `Playwright` + `testcontainers-python` | **100% dos fluxos** | Container do daemon + build estático da UI + ai-jail real (já instalado no host de dev). |
| **Frontend unit** | `Vitest` + RTL | **100% em hooks e lógica**; componentes de apresentação puros dispensados. | Lógica frontend, formatadores, stores. |

`# pragma: no cover` é **admitido** para:
- Linhas defensivas inalcançáveis (`raise NotImplementedError` em
  Protocol, branches `match` exaustivos com `case _:`).
- Blocos guard que dependem de plataforma e o ambiente de teste não
  consegue exercitar.

Cobertura computada **após** exclusões justificadas — o alvo de 100% é
literal sobre o conjunto não excluído.

## 10. Costuras de teste

Sem essas, viramos refém de mocks frágeis. Toda dependência de I/O,
processo ou tempo é injetada via Protocol:

```python
class SessionRuntime(Protocol):
    async def spawn(self, worktree: Path, profile: PermissionProfile) -> JailHandle: ...
    async def kill(self, handle: JailHandle) -> None: ...

class ProcessSpawner(Protocol):
    async def run(self, cmd: list[str], env: dict) -> ProcessHandle: ...

class DockerRuntime(Protocol):
    async def run_ephemeral(self, image: str, env: dict, ports: dict) -> ContainerHandle: ...

class Clock(Protocol):
    def now(self) -> datetime: ...

class HookSink(Protocol):
    async def emit(self, event: HookEvent) -> None: ...
```

- **Unit** usa `Fake*` deterministas em memória.
- **Integration** usa implementações reais (`AiJailRuntime`,
  `SubprocessSpawner`, `DockerSdkRuntime`) com testcontainers.
- **E2E** usa tudo real, dentro de containers.

## 11. Roadmap em fases

Cada fase termina demonstrável + verde nas três camadas.

| Fase | Entrega demonstrável | Inclui |
|---|---|---|
| **F0 — Esqueleto + harness** | `make up` sobe daemon + UI vazia; `make test-all` verde com sentinelas em unit/int/e2e | pyproject, FastAPI scaffold, Vite + Vitest + Playwright, Dockerfile.orchestrator, testcontainers, gates de cobertura |
| **F1 — Spawn isolado** | UI lista projetos/worktrees, botão "Nova sessão" abre Claude Code dentro de ai-jail | `Project`, `Worktree`, `Session`, `SessionRuntime` real, status básico |
| **F2 — Status semântico via hooks** | Cards mostram `awaiting_response` / `idle` em tempo real | `/hooks/*`, parser de eventos, broadcast WS, `notify-send` |
| ~~F3~~ | **Cancelada** — fundida em F2; ver [ADR-0011](docs/adr/0011-f3-cancelada-merged-into-f2.md) | — |
| **F4 — Backlog kanban** ✅ | Kanban unificado cross-project; criar/mover/discardar tasks; iniciar sessão de uma task; quick session cria task implícita | `Task`, kanban UI 5 colunas com `@dnd-kit`, `Session.task_id` NOT NULL, drawer lateral pra projects/worktrees. F4.m fechou gate de cobertura (auto-marker em `tests/conftest.py`) |
| **F5 — Mapa de worktrees + multi-repo** ✅ | Drawer "Projetos & Worktrees": árvore task-grouped por projeto; multi-repo (1 task → N worktrees compartilham 1 sessão); worktrees auto-criadas ao iniciar sessão, auto-removidas em `done`/`discarded`; órfãs detectadas e removíveis | `Repository` model + auto-detect, `GitWorktreeOps`, `start_session` atomic 3-layer (FS+DB+WS), `task.branch` opcional, hard-break `POST /api/sessions {worktree_id}` |
| **F6 — Run from Panel** ✅ | `▶ Run` no TaskCard sobe stack via `.orchestrator/run.yml` (services dict docker-compose-like); chips de URL clicáveis quando ready; SSE stream de logs por serviço; bootstrap de manifesto por sessão Claude efêmera quando falta | `RunInstance` task-scoped (1 ativa por task), Pydantic manifest parser, PortAllocator 31000-31999, `DockerOps` Protocol + Subprocess impl, atomic 3-layer rollback, file watcher pra bootstrap |
| **F7 — Templates + perfis** ✅ | Templates frontend/backend/refactor/bugfix com perfil pré-aprovado aplicado no spawn; catálogo curado em `orchestrator/config/catalog.yml`; dropdown único no form de criar task | `Catalog` Pydantic + `load_catalog`, `GET /api/catalog`, `Task.template`/`permission_profile` populados; `AiJailRuntime.spawn` consome `claude_args` do catálogo; fallback yolo p/ tasks F4-F6 com NULL |
| **F8 — Sessão master no sidebar** ✅ | Sessão Claude persistente global no sidebar web do J-arvis (xterm.js + PTY); manipula tasks via MCP tools (list/create/update/discard); persiste via `claude --resume` | `MasterSession` singleton + migration 0006; `MasterSessionRuntime` em PTY; MCP server JSON-RPC 2.0 via SDK `mcp`; WebSocket bridge com PtyMultiplexer fan-out; xterm.js + `@xterm/addon-fit` no UI |

**MVP = F0 → F7.**

## 12. Definition of Done por fase

- [ ] Red→green→refactor em cada feature
- [ ] Unit coverage 100% (pós-exclusões justificadas) no código novo
- [ ] Toda rota nova com integration test usando testcontainer
- [ ] Todo fluxo novo da UI com E2E
- [ ] `make test-all` verde
- [ ] Sem warnings no output de teste
- [ ] Demo manual executada no browser

## 13. Decisões registradas

Resumo. Cada decisão tem ADR em [`docs/adr/`](docs/adr/) com contexto,
alternativas e consequências. **Ao tomar nova decisão arquitetural,
criar novo ADR e atualizar `docs/adr/README.md`.**

| Decisão | ADR | Escolha | Motivação |
|---|---|---|
| Plataforma | — | Linux only (MVP) | Alinhado com ai-jail e simplicidade |
| Python + daemon | [0002](docs/adr/0002-stack-do-daemon.md) | 3.13 + FastAPI + SQLAlchemy 2 async + Alembic | Stack ortodoxa, ecossistema maduro |
| UI | [0003](docs/adr/0003-stack-da-ui.md) | Vite 6 + React 19 + TanStack Query + Zustand | Cache fino + estado local sem provider hell |
| Sandbox | [0001](docs/adr/0001-sandbox-via-ai-jail-externo.md) | ai-jail externo (Akita) sob `SessionRuntime` | Não reinventar kernel-isolation; trocável |
| TDD + cobertura | [0004](docs/adr/0004-tdd-iron-law-100-cobertura.md) | Iron law, 3 camadas a 100% | Confiabilidade sem auditoria humana constante |
| Run from Panel manifesto | [0005](docs/adr/0005-run-from-panel-manifesto-explicito.md) | `.orchestrator/run.yml` + bootstrap por Claude | Explícito > heurística frágil |
| DB do Run from Panel | [0006](docs/adr/0006-db-descartavel-por-execucao.md) | `docker run --rm` por execução | Estado limpo, cache amortiza custo |
| Modelo de domínio | [0007](docs/adr/0007-task-first-em-vez-de-session-first.md) | Task-first, sessão é detalhe | Resolve a dor real de contexto perdido |
| Sessão em terminal nativo | [0008](docs/adr/0008-sessao-em-terminal-nativo-do-desktop.md) | Daemon spawna terminal do desktop com `ai-jail run -- claude` | UX "mágica no clique" sem PTY-em-browser |
| Hooks via settings.json no jail | [0009](docs/adr/0009-hooks-via-settings-no-jail.md) | Daemon escreve `<worktree>/.claude/settings.json` antes de `ai-jail run` | Sandbox-clean, zero pegada em `~/.claude` |
| WebSocket canal único | [0010](docs/adr/0010-websocket-canal-unico-envelope-tipado.md) | `/ws` + envelope tipado | Escala pra F4/F6 sem multiplicar canais |
| F3 cancelada / fundida em F2 | [0011](docs/adr/0011-f3-cancelada-merged-into-f2.md) | Sem fila ativa, sem `ApprovalRequest`; `AWAITING_APPROVAL` removido do enum | Decisão de permissão fica no Claude Code (terminal nativo + `settings.json`); evita caminho paralelo |
| Task como entidade primária | [0012](docs/adr/0012-task-como-entidade-primaria.md) | `Session.task_id` NOT NULL; quick session cria task implícita | Honra task-first do §1.2 |
| Kanban unificado cross-project | [0013](docs/adr/0013-kanban-unificado-cross-project.md) | Single board com chip de projeto + filtros multi-select | Trabalho cross-project é o caso real |
| Envelope WS com `task_id` opcional | [0014](docs/adr/0014-envelope-ws-task-id-opcional.md) | Campo opcional aditivo ao envelope F2 | UI invalida cache de tasks sem mapa próprio |
| Project multi-repo com auto-detect | [0015](docs/adr/0015-project-multi-repo-com-auto-detect.md) | `Repository` entre `Project` e `Worktree`; scan de `.git` em depth 0/1 | Modela mono e multi-repo (gcb-hub) sem friction |
| Multi-repo 1 sessão cwd shared | [0016](docs/adr/0016-multi-repo-1-sessao-cwd-shared.md) | `ClaudeSession.cwd` = dir-pai contendo N worktrees | Claude vê produto inteiro; preserva "1 session por task" |
| Worktree é detalhe da task | [0017](docs/adr/0017-worktree-detalhe-da-task-sem-create-ui.md) | Sem UI/API de create avulsa; worktrees auto-gerenciadas pelo ciclo da task | Modelo mental coeso; zero lixo no disco |
| RunInstance é detalhe da task | [0018](docs/adr/0018-run-instance-detalhe-da-task.md) | `task_id` FK + partial unique `WHERE ended_at IS NULL`; 1 run ativa por task | Paralelo a Worktree/Session pós-F5; cleanup automático em terminal state |
| Manifest F6 — services dict + depends_on | [0019](docs/adr/0019-manifest-services-dict-com-depends-on.md) | `services:` dict (docker-compose-like), Pydantic `extra="forbid"`, topo sort | Cobre N serviços; familiar pra dev backend |
| Bootstrap via Claude efêmero | [0020](docs/adr/0020-bootstrap-via-sessao-claude-efemera.md) | Sessão Claude sem task_id + file watcher polling `.orchestrator/run.yml` | Zero manutenção de templates; manifesto fica commitado |
| F7 catálogo | [0021](docs/adr/0021-catalog-yaml-curado-templates-perfis.md) | YAML curado + Pydantic + load 1x lifespan | Sem migração, auditável via git diff, editar = commit |
| F8 master session | [0022](docs/adr/0022-sessao-master-claude-no-sidebar-web.md) | xterm.js + PTY + MCP via Streamable HTTP | Reusa Claude CLI; tools no banco; persistência via `--resume` |
