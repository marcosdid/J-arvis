# Changelog

All notable changes to J-arvis follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [F9 — 2026-05-12] UI redesign (CIPHER)

UI vanilla substituída por Tailwind v4 + shadcn/ui com identidade "CIPHER v2" (operator cyberpunk dark-only). 419 testes verdes; 100% coverage mantido em `src/lib`, `src/hooks`, `src/stores` e backend.

### Adicionado

- **Design tokens** em `ui/src/lib/tokens.css` (CSS custom properties — bg/border/text scales, accents, semantic colors, fontes, --ring).
- **Tailwind v4** com `@tailwindcss/vite` + `@config` directive + `@import "tw-animate-css"`.
- **shadcn/ui** primitives (Button, Sheet, Dialog, Tabs, Tooltip, Badge, Input, Skeleton, Sonner, DropdownMenu).
- **HUD top bar** (`HudTopBar` + `HudMetric`) com métricas live (CPU/MEM/RTT/uptime/alerts); `tone='hot'` magenta quando `active_alerts_count > 0`.
- **AppHeader** com brand `j-arvis`, counts (proj·tsk·active) e shortcuts `/`/`P`/`R`/`N` via `useKeyboardShortcut`.
- **StatusBar** tmux-style com segmentos state/ws/mcp/alerts (esquerda) + mode/profile/git/v (direita); estado WS via `useWsConnectionStore`.
- **AppShell** grid `auto auto auto 1fr auto` montando HudTopBar → ErrorBanner → AppHeader → main → StatusBar.
- **TaskDetailSheet** substitui `TaskDetailModal` — shadcn Sheet right com 4 tabs (Overview/Sessions/Run/Logs).
- **MasterSidebar** refatorada com `MasterHeader` + `QuickCommands` (5 chips MCP) + `MasterFooter` (pty + pid + live + RTT).
- **NewTaskInline** quick-add no footer de cada KanbanColumn.
- **NewTaskSheet** (refatorado de `NewTaskForm`) aberto pelo `[N]` do AppHeader.
- **Empty/loading/error states**: kanban empty `[no tasks yet]`, `TaskCardSkeleton`, `ErrorBanner` quando WS offline/reconnecting.
- **8 card states** via pure helper `deriveCardState` + `data-card-state` no TaskCard.
- **Backend novo**: `GET /api/health` (psutil) + handler WS `{type:"ping"}` → `{type:"pong"}` pra RTT.
- **Hooks novos**: `useSystemHealth`, `useWebSocketRTT`, `useKeyboardShortcut`.
- **Store novo**: `useWsConnectionStore` (zustand) alimentado por `connectWs(onStateChange)`.

### Mudado

- `Kanban` + `KanbanColumn` + `TaskCard` movidos pra `ui/src/components/kanban/` com CIPHER Tailwind classes.
- `ProjectsDrawer` migrado pra shadcn `<Sheet side="left">` em `components/drawers/`.
- `BootstrapModal` migrado pra shadcn `<Dialog>` em `components/dialogs/`.
- `index.css` reescrito com scanlines overlay e `@keyframes cipher-blink/cipher-pulse`.

### Deferido

- **Palette refinement** (Phase 14): iteração visual com user no ambiente rodando — paleta atual é green-dominante.
- **`pid` no MasterFooter**: requer mensagem `type:"pid"` do backend.
- **RunPanel completo**, filter input logic (`/`), Cmd+K command palette: pós-F9.

### ADRs

- [0023](docs/adr/0023-tailwind-v4-shadcn-ui-stack.md) — Tailwind v4 + shadcn/ui (Radix)
- [0024](docs/adr/0024-cipher-design-system.md) — CIPHER v2 design identity
- [0025](docs/adr/0025-component-architecture-app-shell.md) — AppShell + folder-por-domínio

---

## [0.1.0-mvp] — 2026-05-11

**MVP completo** — F0 → F7 conforme ARCHITECTURE.md §11. 21 ADRs documentando todas as decisões arquiteturais.

### F7 — Templates + perfis de permissão

- Catálogo curado `orchestrator/config/catalog.yml` com 3 perfis (`yolo`, `default`, `read-only`) + 4 templates (`frontend`, `backend`, `refactor`, `bugfix`). Carregado 1x no lifespan via Pydantic v2; daemon recusa subir se inválido.
- `GET /api/catalog` — listing read-only com response model tipado.
- `POST /api/tasks` aceita `template` opcional; server resolve `permission_profile` + branch prefix via `slugify_for_branch`. `template_not_in_catalog → 422` com `valid_templates`.
- `AiJailRuntime.spawn` consome catálogo no spawn-time, resolve `claude_args`, escreve `.ai-jail`. `PermissionProfileNotInCatalogError → 422` se admin removeu o perfil.
- UI: `useCatalog` hook (`staleTime: Infinity`), dropdown de Template no `NewTaskForm` com hint dinâmico, badges color-coded em `TaskCard`, seção Configuração em `TaskDetailModal`, tooltips com descriptions do catálogo.
- Fallback `yolo` pra tasks F4-F6 com `NULL/NULL` — comportamento bit-identical ao hardcoded F1-F6.
- ADRs: [0021](docs/adr/0021-catalog-yaml-curado-templates-perfis.md).

### F6 — Run from Panel

- `▶ Run` no TaskCard sobe stack via `.orchestrator/run.yml` (services dict docker-compose-like). 1 `RunInstance` ativa por task (`partial unique index`).
- Pydantic manifest parser com substituições (`$PORT_<svc>`, `$NETWORK`, `$RUN_ID`); ordering sort-by-len-DESC pra evitar prefix collision.
- `PortAllocator` range 31000-31999 com socket-bind probe.
- `DockerOps` Protocol + `SubprocessDockerOps` impl; cleanup 3-layer (task-terminal, session-stopped, daemon-restart).
- SSE de logs por serviço; URL chips clicáveis quando ready; hot reload default ON.
- Bootstrap de manifesto: spawna sessão Claude efêmera + file watcher (polling 2s, timeout 30min) quando manifesto faltando.
- ADRs: [0018](docs/adr/0018-run-instance-detalhe-da-task.md), [0019](docs/adr/0019-manifest-services-dict-com-depends-on.md), [0020](docs/adr/0020-bootstrap-via-sessao-claude-efemera.md).

### F5 — Mapa de worktrees + multi-repo

- `Repository` model + auto-detect (mono-repo + multi-repo); 1 task → N worktrees compartilham 1 sessão; worktrees auto-criadas no spawn, auto-removidas em `done`/`discarded`; órfãs detectáveis e removíveis.
- `GitWorktreeOps` Protocol + `SubprocessGitWorktreeOps` impl.
- `start_session` atomic 3-layer (FS + DB + WS) — rollback completo se qualquer camada falha.
- Hard-break `POST /api/sessions {worktree_id}` (legado) → 422.
- `task.branch` opcional (None deferred a primeira sessão; override aceita slug-style).
- ADRs: [0015](docs/adr/0015-project-multi-repo-com-auto-detect.md), [0016](docs/adr/0016-multi-repo-1-sessao-cwd-shared.md), [0017](docs/adr/0017-worktree-detalhe-da-task-sem-create-ui.md).

### F4 — Backlog kanban

- Kanban unificado cross-project com 5 colunas (`idea` / `ready` / `in_progress` / `review` / `done`); drag-and-drop via `@dnd-kit`.
- `Task` model com `Session.task_id NOT NULL`; criação/movimentação/discardar tasks com state machine.
- Quick session cria task implícita; "Iniciar sessão" disponível em qualquer task `ready+`.
- Drawer lateral pra Projetos + Worktrees; toast em delete-409.
- Coverage gate completo via auto-marker em `tests/conftest.py` (gotcha #11).
- ADRs: [0012](docs/adr/0012-task-id-not-null-em-session.md), [0013](docs/adr/0013-state-machine-da-task.md), [0014](docs/adr/0014-app-tsx-coordenador-kanban.md).

### F2 — Status semântico via hooks

- `/hooks/*` endpoints recebem Claude Code lifecycle hooks (`PreToolUse`, `PostToolUse`, `UserPromptSubmit`, `Stop`).
- Status semântico nos cards: `awaiting_response` / `idle` em tempo real via WS broadcast.
- `notify-send` desktop notifications opcional (`JARVIS_NOTIFY=on`).
- F3 cancelada e fundida em F2 (ver [ADR-0011](docs/adr/0011-f3-cancelada-merged-into-f2.md)).
- ADRs: [0007](docs/adr/0007-status-semantico-via-hooks.md), [0008](docs/adr/0008-terminal-emulator-detection.md), [0009](docs/adr/0009-token-registry-bound-to-session.md), [0010](docs/adr/0010-websocket-broadcast-pattern.md), [0011](docs/adr/0011-f3-cancelada-merged-into-f2.md).

### F1 — Spawn isolado

- `Project` + `Worktree` + `ClaudeSession` models.
- UI lista projects/worktrees; botão "Nova sessão" abre Claude Code dentro de ai-jail no terminal nativo do usuário.
- `SessionRuntime` Protocol (`AiJailRuntime` + `NullSessionRuntime` fake).
- ADRs: [0005](docs/adr/0005-spawn-isolado-via-ai-jail.md), [0006](docs/adr/0006-docker-cli-wrapper-sem-podman-abstraction.md).

### F0 — Esqueleto + harness

- `make up` sobe daemon + UI vazia; `make test-all` verde com sentinelas em unit/integration/e2e.
- Stack ortodoxa: Python 3.13 + FastAPI + SQLAlchemy 2 async + Alembic + Pydantic v2.
- UI: Vite 6 + React 19 + TanStack Query + Zustand + `exactOptionalPropertyTypes`.
- Testcontainers pra integration; Playwright pra E2E; coverage gates 100% backend + UI.
- ADRs: [0001](docs/adr/0001-plataforma-linux-only.md), [0002](docs/adr/0002-stack-do-daemon.md), [0003](docs/adr/0003-stack-da-ui.md), [0004](docs/adr/0004-tdd-iron-law-100pct-coverage.md).

### Estatísticas finais MVP

| Camada | Métrica |
|---|---|
| Backend tests | 456 (unit + integration) |
| UI tests | 251 |
| E2E skeletons | 9 (host-only via Playwright) |
| Coverage backend | 100% (2098 stmts) |
| Coverage UI | 100% |
| ADRs | 21 (0001 → 0021) |
| Phases | F0 → F7 ✅ |

### Gotchas documentadas

Ver [`gotchas.md`](gotchas.md) — 17 lições registradas durante o MVP, das mais críticas:

- **#9** ai-jail nested-mount inviável (E2E tem que rodar do host)
- **#11** auto-marker `pytest_collection_modifyitems` evita silenciamento de tests
- **#12** dnd-kit swallow onClick (PointerSensor.activationConstraint)
- **#15** ai-jail v0.10 CLI break (sem `run` subcommand)
- **#17** ai-jail `allow_tcp_ports=[]` não bloqueia loopback

---

[0.1.0-mvp]: https://github.com/marcosdid/J-arvis/releases/tag/v0.1.0-mvp
