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
│  ├── core/       domínio: tasks, sessions, approvals        │
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
- `Worktree(id, project_id, path, branch, current_task_id?)`
- `Task(id, project_id, title, description, state, template, permission_profile, created_at)`
  - `state ∈ {idea, ready, in_progress, review, done, discarded}`
- `Session(id, task_id, worktree_id, jail_id, status, started_at, ended_at?, transcript_path)`
  - `status ∈ {executing, awaiting_approval, awaiting_response, idle, error, done}`
- `ApprovalRequest(id, session_id, tool, args_json, state, created_at, decided_at?)`
  - `state ∈ {pending, approved, denied, expired}`
- `RunInstance(id, worktree_id, manifest_path, status, ports_json, started_at)`
  - `status ∈ {building, seeding, ready, failed, stopped}`

`claude-mem` cuida de memória entre sessões — não duplicar.

## 4. Comunicação Claude Code ↔ daemon

Hooks do Claude Code apontam para `http://localhost:<port>/hooks/<event>`:

- `Notification` → muda `Session.status` para `awaiting_approval` ou
  `awaiting_response` conforme parser do payload.
- `PreToolUse` → cria `ApprovalRequest`, devolve decisão sync ao Claude Code.
- `Stop` → marca `idle` ou `done` conforme contexto.
- Leitura periódica do transcript para auto-resumo de 1 linha (v1.5).

Daemon → UI: WebSocket único, broadcast de eventos.

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
| **F2 — Status semântico via hooks** | Cards mostram `awaiting_approval` / `awaiting_response` / `idle` em tempo real | `/hooks/*`, parser de eventos, broadcast WS, `notify-send` |
| **F3 — Fila central de aprovações** | Painel único agrega todos os `PreToolUse`; aprovar/negar resolve sync | `ApprovalRequest`, UI da fila, blocklist, perfis |
| **F4 — Backlog kanban** | Drag-and-drop entre estados; iniciar sessão a partir de uma task | `Task`, kanban UI, vínculo Task↔Session, templates iniciais |
| **F5 — Mapa de worktrees** | Árvore visual por projeto; criar/destruir worktree pela UI | git ops, vinculação a tasks |
| **F6 — Run from Panel** | Botão ▶ Run sobe DB+back+front e abre URL | manifesto, bootstrap por Claude, alocação de portas, Docker descartável, lifecycle |
| **F7 — Templates + perfis** | Templates frontend/backend/refactor/bugfix com perfil pré-aprovado | catálogo, perfil aplicado no spawn |
| **F8 (v1.5)** — Planner meta-agente | Usuário cola épico → preview de subtasks → backlog | sessão efêmera, tela de preview, bulk insert |

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
