# Pivot Go + Wails — J-arvis como app nativo Linux (design)

**Status:** spec em revisão, plan pending
**Data:** 2026-05-12
**Phase:** F10 (pivot estrutural após F9 fechar)
**Branch alvo:** `feat/f10-native-app` a partir de `feat/f9-ui-redesign`

## 1. Contexto

Após F9 fechar (UI redesign CIPHER com Tailwind v4 + shadcn), o J-arvis é um daemon Python FastAPI servido em `localhost:8000` com UI React renderizada por Vite em `localhost:5173`. O modelo "browser apontando pra localhost" foi correto pra prototipar mas começa a ranger:

1. **Sensação de "site"**, não app. Sem janela com bordas Ubuntu, sem ícone no dock, sem alt-tab limpo, sem system tray, sem shortcuts globais (`Super+J`). Usuário despachou: "browser é site, quero app."
2. **Integração OS rasa.** Notificações via `notify-send` são texto puro (sem actions), drag-from-Nautilus não existe, autostart só via configuração manual, single-instance só por convenção.
3. **Cerimônia de localhost-só-pra-mim.** HTTP em porta TCP + CORS + WebSocket reconnection backoff em ambiente onde só **um usuário, uma máquina, um processo de UI** existe. Single-user single-machine não justifica essa camada.

Esta spec define o **pivot pra app nativo Linux 100% em Go**, usando Wails como shell (WebView do sistema via `webkit2gtk`) e portando o daemon Python inteiro pra Go. **A UI React/Tailwind/shadcn/CIPHER do F9 é preservada intacta** — vive dentro do WebView sem mudanças visuais.

O escopo é **estrutural total**: substitui a stack de backend (Python → Go), elimina HTTP/WS da comunicação UI↔daemon (substituído por Wails bindings in-process), adiciona integração nativa com Ubuntu (tray, shortcuts globais, notificações ricas, drag-from-FM, single-instance lock).

## 2. Decisões arquiteturais

| # | Decisão | Motivação |
|---|---|---|
| 1 | **Go + Wails v2/v3** substituem Python+Vite-served-by-browser. Binário Go único contém shell nativo + webkit2gtk WebView (carrega UI React do F9) + todo o domínio. | Wails é "Tauri pra Go": curva mais suave que Rust, ecosystem maduro pras necessidades do J-arvis (SQLite, subprocess, PTY, Docker, file watcher, D-Bus), binário 10-30MB. UI React do F9 sobrevive 100% sem retrabalho visual. |
| 2 | **Monólito de processo** — sem sidecar Python, sem porta TCP pra UI, sem WebSocket pra UI. Tudo in-process. Front fala com Go via Wails bindings (function calls sync) + eventos via `runtime.EventsEmit/EventsOn`. | Atende motivações B (app de verdade), C (integração SO) e D (cerimônia desnecessária) da Q1 do brainstorming. Latência IPC vira zero (function call em vez de TCP+JSON). |
| 3 | **HTTP server interno mínimo** em `127.0.0.1:<porta efêmera>` exclusivo pra hooks do Claude POSTarem de dentro do ai-jail. "Porta efêmera" = `net.Listen("tcp", "127.0.0.1:0")` então lê a porta atribuída pelo kernel; escrita em `<worktree>/.claude/settings.json` antes do `ai-jail run`. Token UUID por sessão gerado em `SessionsAPI.Start`, registrado em memória, revogado em `SessionsAPI.Stop` (paridade com a lógica Python atual descrita em ARCHITECTURE.md §4). | Hooks do Claude (ADR-0009) são HTTP-based; única superfície de rede que sobrevive. Porta efêmera + bind localhost-only + token por sessão mantém isolamento. |
| 4 | **Hard cut migration** em `feat/f10-native-app`. Python coexiste no disco como referência durante o port; deletado em F10.8 (cleanup). Branches anteriores (`feat/f9-ui-redesign` → `main`) mantém a versão Python+Web funcional como fallback histórico. | Soft transition com flags `--transport=tcp|uds` duplicaria trabalho de teste por meses. Hard cut foca esforço, evita ambíguidade de "qual versão está rodando?". |
| 5 | **UI React do F9 preservada visualmente sem mudanças.** Mudanças concentradas em 3 arquivos: `ui/src/lib/api.ts` (re-imports pra Wails bindings), `ui/src/lib/ws.ts → events.ts` (Wails events), `MasterSidebar.tsx` (PTY via Wails events). TanStack Query, dnd-kit, xterm.js, design tokens CIPHER, Tailwind v4 config — todos intactos. | Investimento massivo no F9 que acabou de mergear. Preservar significa que o port é "trocar transport" pra UI, não "redesenhar UI". |
| 6 | **Close-to-tray lifecycle.** Fechar a janela esconde pro system tray, daemon segue rodando. Quit explícito (pelo tray menu) derruba tudo. | Master session F8 é persistente por design (`claude --resume`), Run instances F6 podem ter Docker rodando, sessões Claude dentro do ai-jail podem estar processando. Close acidental não deve matar trabalho em curso. Revisa ADR-0008. |
| 7 | **Wails bindings em vez de HTTP/WS pra UI↔daemon.** `fetch('/api/tasks')` → `await TasksAPI.List()`. `new WebSocket('/ws')` → `runtime.EventsOn('session.status', cb)`. Tipos TypeScript auto-gerados de structs Go via `wails generate`. | Function call in-process é mais rápido, mais simples, sem CORS, sem reconnect logic, sem JSON parse manual. Substitui ADR-0010. |
| 8 | **Docker via subprocess CLI**, não SDK Go. `os/exec` chamando binário `docker` mantém a interface `DockerOps` do F6. | SDK `docker/docker/client` tem versioning frágil com daemon Docker (negociação API version). CLI é mais estável e o que o Python faz hoje. |
| 9 | **PTY via `creack/pty`** pra master session e qualquer terminal embed. Bytes do PTY emitidos como Wails events (`master.pty.data`) e fanout pra WebView. | `creack/pty` é padrão de fato. Substitui o `PtyMultiplexer` Python do F8 — em monólito, fanout é trivialmente Wails events. |
| 10 | **MCP server JSON-RPC manual** se SDK Go não existir. Validar em F10.5 a disponibilidade do `mcp` SDK Go; se imaturo, implementar JSON-RPC 2.0 manual (é o que `mcp` Python faz por baixo). | Mantém paridade funcional do F8 sem risco de SDK terceiro instável. |
| 11 | **Migrations via `pressly/goose`**, SQL cru, substitui Alembic. Versões 0001-0006 do Alembic convertidas pra `*.sql` files numerados. | Goose é o `Alembic do Go`. SQL explícito é mais auditável que ORM-driven schema. |
| 12 | **SQLite via `modernc.org/sqlite`** (pure Go, sem cgo) em vez de `mattn/go-sqlite3` (cgo). | Sem cgo = build cross-platform trivial, binário sem dependências dinâmicas em libsqlite3. Performance é comparável pra workload single-user. |
| 13 | **Disciplina TDD + 100% coverage ADR-0004 mantida.** Traduzida pra `go test -race -coverprofile + golangci-lint + Playwright`. Mesma divisão 3 camadas (unit/integration/e2e). | Não há razão pra relaxar disciplina por trocar de linguagem. Exclusões `//go:build !test` em wrappers de Wails runtime análogo a `# pragma: no cover` Python. |

## 3. Pain points endereçados

Usuário marcou 3 motivações no brainstorming (Q1, multi-select):

1. **Sensação de app de verdade (B)** → resolvido por: shell Wails com janela nativa do Ubuntu (decorações do compositor, alt-tab, ícone no dock), system tray icon com menu, global shortcut `Super+J` pra focar, autostart configurável.
2. **Integração SO profunda (C)** → resolvido por: notificações via D-Bus `org.freedesktop.Notifications` com action buttons (click "[Focar]" → janela aparece + UI navega pra task), drag de pasta do Nautilus → cria projeto, single-instance lock, file watcher nativo (`fsnotify`).
3. **Cerimônia desnecessária (D)** → resolvido por: zero porta TCP exposta pra UI (Wails bindings são function calls in-process), zero JSON parsing manual (tipos gerados auto), zero CORS, zero WebSocket reconnection logic, zero "make up && abrir browser".

Distribuição (.deb/.AppImage) foi descartada como prioridade na Q1 — incluída como follow-up no F10.8 mas não como driver.

## 4. Arquitetura macro

### 4.1. Process tree em runtime

```
jarvis-app  (binário Go, ~30MB)
│
├── webkit2gtk WebView          ← UI React do F9 intacta
│   ├── chama métodos Go via Wails bindings (sync function call)
│   └── escuta eventos via runtime.EventsOn (pub/sub in-process)
│
├── Goroutines do domínio (tudo no mesmo processo):
│   ├── store    →  modernc.org/sqlite + goose migrations
│   ├── core     →  tasks, sessions, worktrees, catalog
│   ├── sandbox  →  ai-jail subprocess wrapper
│   ├── runtime  →  Run from Panel (docker CLI subprocess)
│   ├── master   →  PTY multiplexer (creack/pty)
│   └── events   →  Wails runtime.EventsEmit (broadcast tipado)
│
├── HTTP server interno (net/http, 127.0.0.1:<efêmera>)
│   └── /api/hooks/{event}/{token}  ← única superfície de rede
│       Por que existe: claude-code dentro do ai-jail POST aqui (ADR-0009).
│       Porta aleatória descoberta no boot, escrita no settings.json do jail.
│
├── ai-jail run -- claude       ← subprocessos (inalterado conceitualmente)
└── docker run --rm ...         ← subprocessos (inalterado conceitualmente)
```

### 4.2. Quem é dono do quê

| Componente | Linguagem | Responsabilidade |
|---|---|---|
| Wails shell | Go | Window, tray, global shortcuts, single-instance lock, supervisão de processos filhos, ponte IPC, OS integration plugins |
| WebView | webkit2gtk | Renderiza UI React/Tailwind v4/shadcn do F9 sem mudança visual |
| Domain core | Go | Tasks, sessions, worktrees, run instances, master session, hooks parsing |
| Store | Go + SQLite | Persistência (`modernc.org/sqlite`), migrations (`goose`) |
| HTTP hook server | Go (`net/http`) | Recebe hooks do Claude (única superfície de rede; bind 127.0.0.1, porta efêmera) |

### 4.3. Transport: antes vs depois

| Operação | Hoje (Python+web) | Depois (Go+Wails) |
|---|---|---|
| Listar tasks | `fetch('/api/tasks')` | `await TasksAPI.List()` (Wails binding) |
| Criar task | `POST /api/tasks` + JSON | `await TasksAPI.Create(input)` (Wails binding) |
| Status update push | `new WebSocket('/ws')` + JSON parse | `runtime.EventsOn('session.status', cb)` (in-process event) |
| Master PTY write | `ws.send({type:'input', data})` | `await MasterAPI.Write(data)` (Wails binding) |
| Master PTY read | `ws.onmessage = (ev) => term.write(JSON.parse(ev.data).data)` | `runtime.EventsOn('master.pty.data', bytes => term.write(bytes))` |
| Daemon TCP porta UI | `localhost:8000` | **Não existe** |
| WebSocket pra UI | `localhost:5173/ws` (proxy vite) | **Não existe** |
| HTTP hook do Claude | `localhost:8000/api/hooks` | `127.0.0.1:<efêmera>/api/hooks` (única porta) |

### 4.4. Fluxo do usuário (abrir o app)

1. Click no ícone do J-arvis no menu Ubuntu (ou `Super+J`)
2. Janela aparece em ~300ms (Go cold start instantâneo)
3. UI renderiza com mesmo design CIPHER do F9 — indistinguível visualmente
4. Tray icon aparece no canto direito da bar do Ubuntu com tooltip live (`3 sessões ativas`)
5. Fechar a janela → some pro tray (daemon segue, master session viva, sessões Claude no jail seguem)
6. Quit pelo tray menu → SIGTERM nos children → cleanup → exit

## 5. Layout do repositório

### 5.1. Estrutura pós-F10

```
J-arvis/
├── go.mod                        # módulo: github.com/marcosdid/jarvis
├── go.sum
├── main.go                       # entry: wails.Run com config + bindings
├── wails.json                    # Wails config (frontend → "ui")
│
├── internal/                     # privado ao módulo (Go convention)
│   ├── api/                      # structs Wails-bound (cascas finas)
│   │   ├── tasks.go              #   → TasksAPI.{List,Create,Move,Discard,...}
│   │   ├── sessions.go           #   → SessionsAPI.{Start,Stop,Status,...}
│   │   ├── projects.go           #   → ProjectsAPI.{List,Create,Delete}
│   │   ├── master.go             #   → MasterAPI.{Write,Resize,Clear,Status}
│   │   ├── catalog.go            #   → CatalogAPI.Get
│   │   ├── runs.go               #   → RunsAPI.{Start,Stop,Status,Logs}
│   │   └── health.go             #   → HealthAPI.Snapshot (CPU/MEM/uptime/etc)
│   │
│   ├── core/                     # domínio puro (sem I/O)
│   │   ├── task.go               # entity Task + state machine
│   │   ├── session.go            # entity ClaudeSession + transitions
│   │   ├── worktree.go           # ops sobre worktree (puro)
│   │   ├── slug.go               # slugify pra branch (porta lib/slug.py)
│   │   ├── catalog.go            # template/perfil resolution
│   │   └── manifest.go           # parser .orchestrator/run.yml validation
│   │
│   ├── store/                    # persistência
│   │   ├── db.go                 # abre SQLite, pragmas (WAL, FK on)
│   │   ├── tasks.go              # CRUD com sqlx-like queries
│   │   ├── sessions.go
│   │   ├── projects.go
│   │   ├── repositories.go       # F5 multi-repo
│   │   ├── worktrees.go
│   │   ├── runs.go               # F6 RunInstance
│   │   ├── master.go             # F8 MasterSession singleton
│   │   └── migrations/           # *.sql files no formato goose
│   │       ├── 0001_init.sql
│   │       ├── 0002_task_template.sql
│   │       ├── ...
│   │       └── 0006_master_session.sql
│   │
│   ├── sandbox/                  # ai-jail wrapper
│   │   ├── runtime.go            # interface SessionRuntime (equiv Protocol Python)
│   │   ├── aijail.go             # impl real via os/exec
│   │   ├── fake.go               # impl pra testes determinísticos
│   │   └── settings.go           # escreve <worktree>/.claude/settings.json
│   │
│   ├── runtime/                  # Run from Panel
│   │   ├── manifest.go           # parser yaml + validation
│   │   ├── ports.go              # PortAllocator (31000-31999)
│   │   ├── docker.go             # CLI subprocess via os/exec
│   │   └── supervisor.go         # lifecycle building → seeding → ready
│   │
│   ├── master/                   # sessão master persistente F8
│   │   ├── session.go            # singleton lifecycle (claude --resume)
│   │   ├── pty.go                # PTY (creack/pty) + multiplexer
│   │   └── mcp.go                # MCP JSON-RPC server (SDK ou manual)
│   │
│   ├── hooks/                    # HTTP server pra hooks do Claude
│   │   ├── server.go             # net/http em 127.0.0.1:<efêmera>
│   │   ├── handlers.go           # /api/hooks/{event}/{token}
│   │   └── parser.go             # converte event → broadcast Wails
│   │
│   └── events/                   # bridge p/ Wails runtime
│       └── bus.go                # EventsEmit centralizado, types tipados
│
├── ui/                           # KEEP — React/Tailwind/shadcn do F9 intacto
│   ├── package.json
│   ├── vite.config.ts            # remover proxy /api e /ws (não usa mais)
│   └── src/
│       ├── App.tsx               # mudanças localizadas: api → Wails bindings
│       ├── lib/api.ts            # reescrito: importa do wailsjs/ gerado
│       ├── lib/events.ts         # novo: substitui ws.ts (15 linhas vs 55)
│       └── hooks/                # mantidos (lógica preservada)
│
├── build/                        # Wails build artifacts
│   ├── appicon.png
│   └── linux/                    # .deb/.AppImage configs (NFPM)
│
├── docs/                         # KEEP
│   ├── adr/                      # ADRs (vai adicionar 0026-0032)
│   └── superpowers/specs/        # design specs (este doc)
│
├── Makefile                      # UPDATE: targets Go (dev, build, test)
└── README.md                     # UPDATE: build instructions Go+Wails

# Removidos no F10.8 (hard cut final):
# - pyproject.toml, uv.lock
# - alembic/
# - orchestrator/
# - tests/ (Python — Go tests vivem co-localizados em *_test.go)
# - Dockerfile.orchestrator
```

### 5.2. Por que esse shape

1. **`internal/` Go-canonical** — pacotes privados ao módulo, não importáveis de fora. Compile-time enforcement.
2. **`api/` separado de `core/`** — métodos Wails-bound são *casca fina* sobre o domínio. `core/` testável sem Wails. Espelha a separação `orchestrator/api/` vs `orchestrator/core/` do Python.
3. **Interfaces em vez de Protocol** — `SessionRuntime` vira `interface{ Spawn(...); Kill(...) }`. Fake e Real implementam. Mesmo padrão de costuras do ADR-0004.
4. **Tests co-located** — convenção Go: `tasks.go` + `tasks_test.go` no mesmo diretório. Sem `tests/` separado.
5. **Migrations SQL cruas** — goose lê `internal/store/migrations/*.sql`. Sem ORM-driven schema. Mais explícito, mais auditável via git diff.
6. **`ui/` preservada** — único rename é remover proxy do `vite.config.ts` (não chama mais `/api` nem `/ws`).

### 5.3. Exemplo concreto — Wails binding

**Go side** (`internal/api/tasks.go`):

```go
package api

import (
    "context"
    "github.com/marcosdid/jarvis/internal/core"
    "github.com/marcosdid/jarvis/internal/events"
    "github.com/marcosdid/jarvis/internal/store"
)

type TasksAPI struct {
    repo *store.TasksRepo
    bus  *events.Bus
}

func NewTasksAPI(repo *store.TasksRepo, bus *events.Bus) *TasksAPI {
    return &TasksAPI{repo: repo, bus: bus}
}

func (a *TasksAPI) List(ctx context.Context, filters core.TaskFilters) ([]core.Task, error) {
    return a.repo.List(ctx, filters)
}

func (a *TasksAPI) Create(ctx context.Context, input core.CreateTaskInput) (*core.Task, error) {
    task, err := a.repo.Create(ctx, input)
    if err != nil {
        return nil, err
    }
    a.bus.Emit("task.created", task)
    return task, nil
}
```

**Front side** (`ui/src/lib/api.ts`):

```ts
import { TasksAPI } from '../../wailsjs/go/api/TasksAPI';

export const api = {
  listTasks: TasksAPI.List,
  createTask: TasksAPI.Create,
  // ...
};
```

Tipos de `core.Task`, `core.TaskFilters`, `core.CreateTaskInput` são **auto-gerados** pelo Wails como `.d.ts` em `wailsjs/go/models.ts`.

## 6. UI integration

### 6.1. O que não muda

- Todo o design system CIPHER, tokens em `tokens.css`, Tailwind v4 config
- Estrutura de componentes: `AppShell`, `Kanban`, `KanbanColumn`, `TaskCard`, `MasterSidebar`, `TaskDetailSheet`, `ProjectsDrawer`, dialogs
- TanStack Query: mesmas `useQuery({queryKey, queryFn})` — só muda o que `queryFn` chama por dentro
- xterm.js: continua sendo o renderer do terminal (com fix do `dimensions undefined` aplicado)
- dnd-kit: drag & drop do kanban continua
- shadcn primitives: Sheet, Dialog, Tabs, Tooltip continuam

### 6.2. O que muda (3 arquivos)

**`ui/src/lib/api.ts`** — passa de fetch wrappers pra Wails bindings re-exports (exemplo no §5.3).

**`ui/src/lib/ws.ts` → `ui/src/lib/events.ts`** — reescrito ~55 LOC → ~15 LOC:

```ts
import { EventsOn, EventsOff } from '../../wailsjs/runtime';
import type { WsEvent } from './events.types';

const EVENT_NAMES = [
  'session.status', 'session.tool_use', 'session.stopped',
  'task.created', 'task.updated', 'task.discarded',
  'run.status', 'master.system',
] as const;

export function subscribeEvents(onEvent: (event: WsEvent) => void): () => void {
  const offFns = EVENT_NAMES.map((name) => {
    EventsOn(name, (payload) => onEvent({ type: name, payload }));
    return () => EventsOff(name);
  });
  return () => offFns.forEach((fn) => fn());
}
```

Sem reconnection, sem backoff, sem `WsState` ('connecting'/'reconnecting'/'offline'). Wails events não falham enquanto o processo está vivo.

**`MasterSidebar.tsx`** — PTY transport (linhas 44-90 do componente atual):

```ts
import { EventsOn, EventsOff } from '../../wailsjs/runtime';
import { MasterAPI } from '../../wailsjs/go/api/MasterAPI';

useEffect(() => {
  const off = EventsOn('master.pty.data', (bytes: number[]) => {
    term.write(new Uint8Array(bytes));
  });
  term.onData((data) => MasterAPI.Write(data));
  term.onResize(({rows, cols}) => MasterAPI.Resize(rows, cols));
  return () => EventsOff('master.pty.data');
}, []);
```

Sem WebSocket, sem reconnect, sem ConnectionStatus.

### 6.3. Arquivos deletados

| Arquivo | Razão |
|---|---|
| `ui/src/lib/ws.ts` | Substituído por `events.ts` mais simples |
| `ui/src/stores/wsConnection.ts` | Estado connecting/reconnecting/offline não existe mais |
| `ui/src/hooks/useWebSocketRTT.ts` | RTT é zero em monolítico — slot do HUD vira `events/s` |
| `vite.config.ts` `server.proxy` | Wails dev server serve direto, sem proxy HTTP |

### 6.4. Slot do RTT no `MasterFooter`

Hoje o `MasterFooter` mostra `rtt: 12ms`. Substituído por **`events/s`** (decisão da Seção 3 do brainstorming):

- Contador de eventos Wails disparados pelo backend no último segundo
- Útil quando 3+ sessões estão ativas — vira indicador de carga
- Calculado em Go via ring buffer de timestamps em `internal/events/bus.go` (mesmo pacote que faz `EventsEmit` — bookkeeping local à origem), exposto via `runtime.EventsEmit('hud.events_per_sec', n)` a cada 1s

### 6.5. Dev workflow

| Comando | Hoje | Depois |
|---|---|---|
| Iniciar dev | `make up` (FastAPI + Vite + browser, 3 processos) | `wails dev` (1 processo: app aparece, WebView pointing pra Vite com HMR) |
| Hot reload React | ✓ via Vite | ✓ via Vite (mesma coisa, dentro da janela Wails) |
| Reload Go | n/a | watch mode do Wails reinicia o app (~1s) |
| Build prod | `make build` (vários artifacts) | `wails build` (1 binário em `build/bin/jarvis`) |
| Rodar tests | `make test-all` | `make test` (delegando Go + UI + Playwright) |

## 7. OS integration

### 7.1. MVP — features que entram no port

| Feature | Lib Go | Comportamento |
|---|---|---|
| System tray icon | Wails v3 systray (ou `getlantern/systray`) | Ícone fixo na bar do Ubuntu. Menu: "Mostrar janela", "Nova task...", "Quit". Tooltip live: `"3 sessões ativas, 1 awaiting"` |
| Close = hide to tray | `OnBeforeClose` handler do Wails | Fechar janela esconde (daemon segue rodando). `Quit` pelo tray menu derruba tudo. |
| Single-instance lock | **D-Bus name registration** (primário): `org.jarvis.App` via `godbus/dbus`; se o nome já está claimado, envia método "ShowWindow" pra instância existente e exit. Fallback: Wails plugin se D-Bus name claim falhar (cenário raro mas possível em headless/sessões D-Busless) | 2ª invocação do binário só foca a janela existente. |
| Global shortcut `Super+J` | `golang.design/x/hotkey` | Mostra/foca janela de qualquer lugar do desktop. Configurável depois. |
| Notificações ricas (com actions) | `godbus/dbus` direto em `org.freedesktop.Notifications` | Action buttons no toast. Click `[Focar]` → janela aparece + UI navega pra task. |
| Drag pasta do Nautilus → criar projeto | HTML5 drop event + `OnFileDrop` do Wails | Soltar pasta na `ProjectsDrawer` chama `ProjectsAPI.Create(path)` direto. |

### 7.2. Pós-MVP (F11+)

| Feature | Razão de adiar |
|---|---|
| Autostart on login | Precisa de UI de settings (não existe) |
| Protocol handler `jarvis://` | Útil pra deep-link mas baixo retorno hoje |
| Drop arquivo em TaskCard → anexar | Domínio de attachments não existe no modelo |
| Quick-add task via tray (sem abrir janela) | Útil mas precisa de mini-window — adicionar depois |

### 7.3. Notificações com actions — exemplo concreto

Hoje (Python): `notify-send "Task X precisa de você"` — texto simples, click não faz nada.

Depois (Go via D-Bus):

```go
notif := dbus.Notification{
    Summary: "fix-auth precisa de você",
    Body:    "Claude está aguardando resposta há 30s",
    Icon:    "/usr/share/icons/jarvis.png",
    Actions: []string{
        "focus",  "Focar janela",
        "snooze", "Lembrar em 5min",
    },
}
notif.OnAction(func(actionKey string) {
    if actionKey == "focus" {
        runtime.WindowShow(ctx)
        bus.Emit("task.focus", taskID)  // UI navega pra task
    }
})
```

Diferença de UX vs hoje é grande — uma click resolve o caminho que antes precisava abrir janela + procurar a task no kanban.

### 7.4. Tray menu visual

```
┌──────────────────────────────┐
│  ◉ J-arvis                   │
│  ────────────────────────    │
│  ▸ 3 sessões ativas          │ ← live stats line (tooltip dinâmico)
│  ▸ 1 awaiting response       │
│  ────────────────────────    │
│  Mostrar janela     Super+J  │
│  Nova task...                │
│  ────────────────────────    │
│  Quit J-arvis                │
└──────────────────────────────┘
```

## 8. Plano de migração F10

Cada sub-fase termina **demonstrável + verde** (ADR-0004 mantida). Python coexiste no disco até F10.8.

| Fase | Entrega demonstrável | Inclui | Estimativa |
|---|---|---|---|
| **F10.0 — Skeleton** | Janela Wails abre, F9 UI renderiza, `wails dev` funciona, `wails build` produz binário | `go.mod`, `main.go`, `wails.json`, healthcheck stub bind, CI Go+JS verdes | 1 sem |
| **F10.1 — Store + migrations** | (interno) `internal/store` lê/escreve SQLite, migrations goose convertidas das versões Alembic 0001-0006 | `modernc.org/sqlite`, `pressly/goose`, conexão + pragmas, repos básicos com tests | 1-2 sem |
| **F10.2 — Tasks vertical slice** | Kanban funciona: criar task, mover entre colunas, descartar, eventos refletem em outros panels | Port `core/task` + `store/tasks` + `api/TasksAPI`. UI: reescrever `lib/api.ts` + `useSessionEvents`. WS events → `bus.Emit` | 2-3 sem |
| **F10.3 — Projects + Worktrees** | Drawer "Projetos & Worktrees" funciona, multi-repo auto-detect (F5), worktree lifecycle | Port `core/project` + `core/worktree`. Git ops via `go-git/go-git` ou `os/exec` | 2-3 sem |
| **F10.4 — Sandbox + Sessions + Hooks** | Botão "Nova sessão" spawn claude no ai-jail, status semântico via hooks vira eventos no kanban | Port `sandbox/` (ai-jail wrapper) + `core/session` + HTTP hook server interno + settings.json writer + token-per-session generate/revoke lifecycle (paridade com ARCHITECTURE.md §4) | 3-4 sem ⚠️ alta variância (novo terreno; risco #1 e #7) |
| **F10.5 — Master session + Catalog + MCP** | Sidebar master funciona, MCP tools manipulam tasks, templates/perfis aplicam no spawn | Port `master/` (PTY mux com `creack/pty`) + `catalog/` (F7) + MCP server JSON-RPC | 3-4 sem ⚠️ alta variância (MCP SDK Go incerto; risco #1) |
| **F10.6 — Run from Panel** | ▶ Run sobe stack via Docker, chips de URL clicáveis, bootstrap por sessão Claude efêmera | Port `runtime/` com Docker CLI subprocess, manifest parser, port allocator, file watcher | 2-3 sem |
| **F10.7 — OS integration** | Tray + close-to-hide + Super+J + notif com actions + drag pasta + single-instance | Seção 7 inteira | 1-2 sem |
| **F10.8 — Cleanup + packaging** | `make build` produz `.deb`+`.AppImage`. Python e Alembic deletados. README+ARCHITECTURE atualizados. ADRs 0026-0032. | NFPM packaging, doc updates, hard delete dos arquivos Python | 1 sem |
| **Total estimado** | App nativo completo, F0-F9 portados | | **16-23 semanas (~4-5 meses focado)** |

### 8.1. Estado do Python durante o port

Durante F10.0 → F10.7 o daemon Python continua funcional na branch `main` (que aponta pra `feat/f9-ui-redesign` post-merge). Você pode rodar o J-arvis web normal pra trabalhar enquanto a versão Go ainda não tem todas as features.

Em F10.8 (cleanup) o Python é deletado da `feat/f10-native-app`. Quando essa branch mergeia pra `main`, ela perde Python. Histórico do git preserva a versão Python via tag `v0.9-python-final`.

### 8.2. Critério "demonstrável" por fase

Cada F10.x deve permitir o dogfood do J-arvis em alguma forma. Exemplo:

- F10.2 (Tasks slice): rodar `wails dev`, criar 3 tasks, mover entre colunas, fechar/abrir app, tasks persistem
- F10.4 (Sandbox + Sessions): rodar uma sessão Claude end-to-end via ai-jail, ver status mudando em tempo real no kanban
- F10.6 (Run from Panel): clicar ▶ Run em uma task, ver Docker subir, chip de URL aparecer, abrir no browser

Sem essa pressão, fácil acumular código sem feedback loop.

## 9. Disciplina de qualidade Go

ADR-0004 ("TDD iron-law + 100% cobertura, 3 camadas") **permanece como regra**. Tradução pra ecosistema Go:

### 9.1. Pirâmide de teste

| Camada | Comando | Escopo | Cobertura alvo |
|---|---|---|---|
| Unit | `go test -race ./internal/...` | Domínio puro + store via SQLite in-memory. Table-driven, fakes hand-written | 100% pós-exclusões |
| Integration | `go test -tags=integration -race ./...` | Real ai-jail + real Docker via `testcontainers-go`. Testa HTTP hook server end-to-end | 100% das rotas |
| E2E | `npx playwright test` | Playwright mantido. Roda contra `./build/bin/jarvis --headless` | 100% dos fluxos |
| Frontend unit | `npm test` (vitest) | Mantido — hooks/lib/stores da UI | 100% em hooks/lógica |

### 9.2. Tooling Go

| Ferramenta | Função |
|---|---|
| `go test -coverprofile` | Coverage gate |
| `gofmt -l .` | Formatting (zero tolerância) |
| `go vet ./...` | Stdlib static check |
| `staticcheck ./...` | Catches mais que vet |
| `golangci-lint run` | Agrega vet/staticcheck/errcheck/gosec/ineffassign |
| `goimports -w .` | Auto-import + format |

### 9.3. Costuras via interface (não SOLID-Lite, real)

```go
// internal/sandbox/runtime.go
type SessionRuntime interface {
    Spawn(ctx context.Context, wt Path, profile PermissionProfile) (JailHandle, error)
    Kill(ctx context.Context, h JailHandle) error
}

// internal/sandbox/aijail.go — impl real via os/exec
type AiJailRuntime struct { /* ... */ }
func (r *AiJailRuntime) Spawn(...) (JailHandle, error) { /* ... */ }

// internal/sandbox/fake.go — impl pra testes
type FakeRuntime struct {
    Spawned  []SpawnCall
    SpawnErr error
}
```

Mesmo padrão de Protocol Python via interfaces. Zero deps de gomock/mockery.

### 9.4. Coverage por pacote

| Pacote | Regra |
|---|---|
| `internal/core/` | 100% (puro, sem I/O) |
| `internal/store/` | 100% (SQLite temp file ou `:memory:`) |
| `internal/sandbox/`, `internal/runtime/`, `internal/master/` | 100% via fakes na unit; integration cobre o real. Padrão: `interface CmdRunner { Run(ctx, name string, args ...string) ([]byte, error) }` envolve `os/exec` — fake em unit retorna saídas determinísticas; impl real em integration. Espelha o pattern de `SessionRuntime` mostrado em §9.3 |
| `internal/api/` | 100% (cascas finas — testa via fakes de core+store) |
| `internal/hooks/` | 100% via `httptest` |
| `internal/events/` | Exclusão justificada — wrapper de Wails runtime |
| `main.go`, `app.go` | Exclusão justificada — Wails bootstrap (não rodável em test) |

Build tag `//go:build !test` em wrappers de Wails runtime permite exclusão limpa.

### 9.5. Pre-commit gate (CLAUDE.md global)

```bash
gofmt -l .           # exit 0 = nada a formatar
go vet ./...
golangci-lint run
go test -short ./internal/...
cd ui && npm run typecheck && npm test
```

Plus: code-review subagent (já documentado em `~/.claude/CLAUDE.md`) revisa staged diff antes do commit.

### 9.6. Makefile refeito

```makefile
.PHONY: dev build test test-unit test-int test-e2e lint clean

dev:        ; wails dev
build:      ; wails build -platform linux/amd64
test:       ; $(MAKE) lint && $(MAKE) test-unit && $(MAKE) test-int && $(MAKE) test-e2e

test-unit:  ; go test -race ./internal/... && cd ui && npm test
test-int:   ; go test -tags=integration -race ./internal/...
test-e2e:   ; npx playwright test

lint:       ; gofmt -l . && go vet ./... && golangci-lint run

clean:      ; rm -rf build/bin
```

## 10. Riscos identificados

| # | Risco | Mitigação |
|---|---|---|
| 1 | MCP SDK Go pode não existir ou estar imaturo | Plano B: JSON-RPC 2.0 manual em F10.5 — é o que `mcp` Python faz por baixo. Validar disponibilidade do SDK no início de F10.5. |
| 2 | Docker SDK Go versioning frágil com daemon Docker | Manter abordagem atual: `os/exec` chamando CLI `docker`. Preserva interface `DockerOps`. Decisão #8 dessa spec. |
| 3 | Master session transcript collision durante F10.5 (Python+Go side-by-side) | Single-instance lock garante 1 daemon por máquina. Quando F10.5 entra, F9 web fica desativado nessa branch. |
| 4 | Tailwind v4 + Wails build hook — front precisa buildar antes do embed | `wails.json` tem `frontend.build` hook configurável. Garantir `cd ui && npm run build` configurado desde F10.0. |
| 5 | webkit2gtk version skew Ubuntu 22.04 vs 24.04 | Testar nos LTS suportados; lockar features CSS a webkit2gtk 2.40+ (Ubuntu 22.04 LTS minimum). |
| 6 | Curva de Go (se sem track prévio) | Disciplina ADR-0004 (TDD + costuras via interface) guia código simples. Code-review subagent pega anti-patterns. Cada F10.x é pequena o suficiente pra absorver. |
| 7 | F8 MCP tools schema drift durante port | Snapshot do schema atual antes de F10.5; testes de integração validam `tools/list` paridade em nome + input_schema. |
| 8 | Perda de momentum em 4-5 meses sem features novas | Cada F10.x é demonstrável; usar o app durante o port (dogfood). F10.2 já dá kanban funcionando. |
| 9 | CI complexity durante port (Python + UI antes; Go + UI + Playwright depois) | Aceitar 2 caminhos verdes em paralelo durante F10.0-F10.7. F10.8 cleanup reduz pra 1 caminho. |
| 10 | `golang.design/x/hotkey` experimental | Plano B: remover global shortcut do MVP se quebrar; é nice-to-have, não crítico. |

## 11. ADRs novos a registrar

A criar em `docs/adr/`:

| ADR | Título | Substitui/refina |
|---|---|---|
| **0026** | Pivot pra Go+Wails monolítico nativo | Refina stack do daemon (ADR-0002) e da UI (ADR-0003) |
| **0027** | Close-to-tray lifecycle | Refina ADR-0008 (daemon morre quando user fecha → morre só com Quit explícito) |
| **0028** | Wails bindings em vez de HTTP/WS pra UI↔daemon | Substitui ADR-0010 (WS canal único) — IPC virou function call in-process |
| **0029** | Docker via subprocess CLI em vez de SDK Go | Decisão consciente; mantém interface `DockerOps` do F6 |
| **0030** | MCP server: SDK Go se disponível, fallback JSON-RPC manual | Refina ADR-0022 (master session MCP via SDK Python) |
| **0031** | Migrations: goose em vez de Alembic | Consequência operacional do port |
| **0032** | HTTP hook server interno em porta efêmera | Refina ADR-0009 (porta dinâmica + settings.json escrito no jail antes do run) |

Cada ADR segue formato `docs/adr/000N-<slug>.md` com contexto, alternativas e consequências.

## 12. O que NÃO muda

A pivot é **estrutural total** mas o produto continua sendo a mesma coisa. Preservados:

- **Visão** (PRODUCT.md §1) — orquestrador local de Claude Code, painel de bordo do dev
- **Diferenciações** (§3.1 sandbox-first, §3.2 task-first) — apostas que continuam de pé
- **Personas** (§4) — Solo Senior Dev, Tech Lead delegador, anti-persona macOS
- **Fluxos de uso** (§5) — golden path, quick session, master session, Run from Panel
- **Modelo de dados** — entities, states, relations (Task, Session, Project, Repository, Worktree, RunInstance, MasterSession)
- **Sandbox via ai-jail externo** (ADR-0001) — não muda; só o wrapper Python vira Go
- **Catálogo F7** — YAML + perfis de permissão
- **claude-mem integration** — segue como CLI externo, agora chamado via `os/exec` em Go
- **Identidade visual CIPHER** (ADR-0024) — design tokens, JetBrains Mono, magenta accent, corner brackets, HUD top bar, status bar tmux-style — tudo intacto via WebView
- **Component architecture F9** (ADR-0025) — AppShell rows-grid + folder-por-domínio — preservada

Isso é **só** mudança de stack — o produto continua sendo a mesma coisa, em forma nativa.

## 13. Próximos passos

1. **Spec review loop** (próximo) — dispatch spec-document-reviewer subagent contra este documento; fix issues até aprovação (max 3 iterações).
2. **User review gate** — usuário lê o spec aprovado, dá luz verde ou pede mudanças.
3. **Invoke `superpowers:writing-plans`** — criar plano de implementação detalhado a partir deste design. Plano define cada F10.x com tasks específicas, ordem de commit, critérios verde.
4. **Branch `feat/f10-native-app`** criada a partir de `feat/f9-ui-redesign`.
5. **Tag `v0.9-python-final`** marca a versão Python pre-port pra referência histórica.
6. **F10.0 começa** — skeleton Wails + CI verde.
