# F4 — Backlog kanban (design spec)

- **Data:** 2026-05-09
- **Fase do roadmap:** F4 (`ARCHITECTURE.md` §11)
- **Pré-requisitos:** F1 + F2 concluídos. F3 cancelada (ADR-0011).
- **Decisões novas:** ADR-0012 (Task como entidade primária; Session
  obrigatoriamente filha de Task), ADR-0013 (kanban unificado
  cross-project com filtros), ADR-0014 (envelope WS estendido com
  `task_id` opcional — emenda aditiva ao ADR-0010).
- **Escopo recusado / deferido:**
  - **Master session orquestradora**: gerenciamento de tasks por uma
    sessão Claude "Mestre" com skills custom (`/refinar`, etc.) e
    lifecycle binding ao daemon. Vira fase **F9** futura, com
    brainstorm próprio. F4 é **100% manual**.
  - **Templates + permission_profile populados**: campos no schema
    em F4, mas valor `NULL` por padrão. F7 enche.
  - **Reabrir terminal de session viva**: deferido. F4 só tem
    "Iniciar sessão" (cria nova).

## 1. Objetivo

Hoje sessões são **órfãs** (vinculadas só a worktrees). O usuário
não consegue pensar em "trabalho a fazer" — só em "instâncias do
Claude rodando". F4 muda isso:

- Introduz `Task` como entidade primária (princípio §1.2 do
  `ARCHITECTURE.md`: task-first).
- Toda session passa a ter `task_id` obrigatório.
- UI ganha kanban unificado cross-project com 5 colunas e
  drag-and-drop entre estados.
- Quick session (clique numa worktree) continua funcionando — cria
  Task implícita silenciosamente.

**Demo de aceitação** *(em E2E: usando `NullSessionRuntime`;
manualmente: terminal nativo real abre conforme ADR-0008)*:

1. Usuário cria task `"Adicionar dark mode"` no projeto X via
   "+" da Backlog.
2. Move card de Backlog (idea) → Backlog (ready) via dnd (transição
   `idea → ready` requer modal — ver §6.3 e #S7 abaixo).
3. Clica no card → modal abre → "▶ Iniciar sessão" → escolhe
   worktree `feature/dark-mode` → terminal nativo abre. Card
   auto-move pra In Progress.
4. Em paralelo, clica "▶ Quick session" numa worktree `feature/foo`
   → task implícita aparece direto em In Progress.
5. Filtra kanban por projeto X → tasks de outros projetos somem.
   Reload da página → filtro permanece.
6. Drag de card In Progress → Review → Done. (Drag de Done → Backlog
   é bloqueado: snap-back + toast.)

## 2. Decisões fechadas

| # | Decisão | Escolha | Justificativa |
|---|---|---|---|
| 1 | Vínculo Session↔Task | Obrigatório com auto-create na quick session (`Session.task_id NOT NULL`) | Honra task-first do ARCHITECTURE §1.2; mantém UX rápida via auto-task |
| 2 | Vínculo Task↔Worktree | Task é pura (sem `worktree_id`); Session traz worktree | Tasks no backlog não precisam de worktree alocada; zero estado a sincronizar |
| 3 | Layout do kanban | **Único cross-project**, com chip de projeto por card + filtros multi-select no header | Pivot do usuário durante brainstorm: "uma tag de projeto na task já resolve" |
| 4 | Colunas | 5: Backlog (idea+ready) \| In Progress \| Review \| Done \| Discarded | 6 colunas literais não cabem em laptop; idea/ready agrupados com sub-tag visual mantém spec |
| 5 | Drag-and-drop | `@dnd-kit/core@^6.3` + `@dnd-kit/sortable@^8` (versões com peer dep React 19 declarado) | Maintained; React 19 ok desde dnd-kit 6.3; keyboard a11y nativo; ~10kb gzip. Fallback: `@hello-pangea/dnd` (fork ativo do react-beautiful-dnd, mantido pela equipe Atlaskit ex-Atlassian) |
| 6 | Auto-transição em `start_session` | Força task → `in_progress` se em `idea`, `ready`, **ou `review`** (re-trabalho). No-op se já `in_progress`. **409** se em `done` ou `discarded` (precisa resurrect manual primeiro) | Iniciar = sinal claro de "estou trabalhando"; kanban deve refletir |
| 7 | Auto-transição em Stop hook | **Nenhuma**. Stop hook segue de F2 (muda status da Session, não da Task) | Sessão crashar não deve marcar task pronta pra review automaticamente |
| 8 | Política de session por task | 1 não-terminal ativa por task. Tentar segunda (sequencial ou concorrente) → 409 Conflict. SQLite serializa; em Postgres usa `SELECT … FOR UPDATE` | Histórico cumulativo no DB; UX não-ambígua |
| 9 | Mover task: API shape | `PATCH /api/tasks/{id}` com `{state}`. Server valida transição. PATCH com `{state: <atual>}` é no-op idempotente (200) | Mais REST; endpoint `/transition` dedicado é YAGNI |
| 10 | Quick session (compat) | Mantida. `POST /api/sessions {worktree_id}` cria Task implícita `"Quick session · <branch>"` em `in_progress` | Não quebra UX da F1; usuário pode renomear depois |
| 11 | Persistência de filtros | `localStorage["jarvis.kanban.filters"] = JSON.stringify(string[])` (lista de `project_id`s ativos). IDs inexistentes no servidor são silenciosamente ignorados ao ler | Single-user; sem estado server-side; sem estado-fantasma após delete de project |
| 12 | DELETE de task | **Não existe**. Soft-delete via `state: discarded` | Preserva histórico de sessions vinculadas |
| 13 | Resurrect de discarded | `discarded → idea` permitido | Custo zero; útil pra "voltei atrás" |
| 14 | Templates / perfis | Campos `template`, `permission_profile` no schema (`NULL` em F4). UI não pede; sem populate. F7 enche | Não promete o que F4 não entrega |
| 15 | Project picker / worktree mgmt | Drawer lateral acionado por botão "Projetos ▾" do header. Conteúdo = UI atual (lista projects, criar/deletar, listar/criar worktree, "▶ Quick session" por worktree) | Tira "duas telas"; mantém UX existente acessível sob demanda |
| 16 | WS event types novos | `task.created`, `task.updated`. Sem `task.deleted` (não há delete). Eventos `session.*` existentes ganham `task_id` no envelope (cf. §4.2) | Permite invalidar `tasks` em mudanças de status de session sem mapa client-side |
| 17 | Cor do chip de projeto | Determinística por hash do `project_id` mod 8. Paleta fixa: `#1f77b4 #ff7f0e #2ca02c #d62728 #9467bd #8c564b #e377c2 #17becf` (Tableau-10 reduzido) | Estável entre sessões; sem persistir cor no DB; sem clash com tema da UI |
| 18 | FK cascade em delete de project | `tasks.project_id ON DELETE RESTRICT` (alembic FK + check no `delete_project` core: bloqueia se `len(tasks) > 0` com mensagem "discard tasks first") | Evita destruição silenciosa de histórico; usuário decide |
| 19 | Envelope WS — emenda ADR-0014 | Adiciona campo top-level `task_id: str \| None = None` ao `WsEvent`. Eventos de session preenchem `session_id` e (a partir de F4) também `task_id` quando aplicável; eventos de task preenchem `task_id` e deixam `session_id=""`. Discriminador continua sendo `type` | Resolve smell do empty-string; backward-compatible (campo opcional novo) |
| 20 | i18n de erros | Backend retorna mensagens en-US (ops/logs/curl). Frontend mapeia pra pt-BR via `lib/errorMessages.ts` | Erros do servidor ficam grepáveis em logs; UX continua em pt-BR |

## 3. Arquitetura

### 3.1 Componentes novos / modificados

```
orchestrator/
├── core/
│   ├── tasks.py              NOVO    domínio: create_task, list_tasks,
│   │                                  get_task, update_task, transition,
│   │                                  ensure_task_for_quick_session
│   ├── sessions.py           EDIT    start_session ganha task_id (kw);
│   │                                  auto-transition; 409 se task tem
│   │                                  session ativa
│   └── projects.py           EDIT    delete_project bloqueia se há tasks
├── api/
│   ├── tasks.py              NOVO    POST/GET-list/GET-one/PATCH +
│   │                                  POST /tasks/{id}/sessions
│   └── sessions.py           EDIT    POST /sessions agora delega a
│                                     core.tasks.ensure_task_for_quick_session;
│                                     SessionRead ganha task_id
├── store/
│   └── models.py             EDIT    + Task; ClaudeSession.task_id NOT NULL
├── events/
│   └── envelope.py           EDIT    WsEvent.task_id (str | None);
│                                     factories task_created/task_updated;
│                                     session_* factories aceitam task_id
└── alembic/versions/
    └── 0003_tasks_and_session_task_link.py  NOVO  migration aditiva

ui/src/
├── components/
│   ├── Kanban.tsx            NOVO    layout cross-project, dnd-kit
│   ├── KanbanColumn.tsx      NOVO    coluna droppable + sortable
│   ├── TaskCard.tsx          NOVO    sortable item, mostra chip+title+sub-tag
│   ├── TaskDetailModal.tsx   NOVO    title/desc edit + history + iniciar +
│   │                                  Move-to dropdown (transições não-drag)
│   ├── ProjectFilters.tsx    NOVO    multi-select chips no header
│   ├── ProjectsDrawer.tsx    NOVO    drawer lateral; encapsula UI atual
│   └── NewTaskForm.tsx       NOVO    form inline no rodapé da Backlog
├── hooks/
│   ├── useTasks.ts           NOVO    query + invalidação por WS
│   └── useTaskMutations.ts   NOVO    create / patch / start session
├── lib/
│   ├── api.ts                EDIT    + createTask, listTasks, getTask,
│   │                                  patchTask, startTaskSession
│   ├── events.ts             EDIT    + task.created, task.updated;
│   │                                  session.* events ganham task_id
│   ├── errorMessages.ts      NOVO    map en→pt para erros conhecidos
│   ├── projectColor.ts       NOVO    hash → cor de paleta fixa (8 cores)
│   ├── transitions.ts        NOVO    isValidTransition(from, to);
│   │                                  resolveColumnState(column, fromState)
│   └── kanbanFilters.ts      NOVO    load/save de localStorage
└── App.tsx                   EDIT    layout reorganizado: header +
                                     filtros + Kanban; Projects/Worktrees
                                     viram drawer
```

### 3.2 Modelo de dados

**Tabela nova `tasks`:**

| Coluna | Tipo | Constraint | Notas |
|---|---|---|---|
| id | str(32) | PK | UUID hex |
| project_id | str(32) | FK → projects.id, NOT NULL, **ON DELETE RESTRICT** | Bloqueia delete de project com tasks |
| title | str(255) | NOT NULL, len ≥ 1 (sem whitespace-only) | |
| description | text | NOT NULL, default `""` | Sem hard limit; UI sugere 4000 chars |
| state | str(32) | NOT NULL, default `"idea"` | |
| template | str(64) | NULL | Populado em F7 |
| permission_profile | str(64) | NULL | Populado em F7 |
| created_at | datetime | NOT NULL, default UTC now | |
| updated_at | datetime | NOT NULL, default UTC now | Bumped em qualquer mudança |

**Mudança em `sessions`:**

| Coluna | Tipo | Antes | Depois |
|---|---|---|---|
| task_id | str(32) FK → tasks.id, **ON DELETE RESTRICT** | (não existia) | NOT NULL |

### 3.3 State machine (server-validated)

**Tabela canônica de transições válidas** (`is_valid_transition(from, to)`):

| De | Para |
|---|---|
| `idea` | `ready`, `discarded` |
| `ready` | `idea`, `in_progress`, `discarded` |
| `in_progress` | `review`, `discarded` |
| `review` | `in_progress`, `done`, `discarded` |
| `done` | (terminal — nenhuma) |
| `discarded` | `idea` (resurrect) |

Idempotência: `PATCH {state: <atual>}` retorna `200` com a row
inalterada (não conta como transição inválida).

Tentar transição não listada → `422 Unprocessable Entity`
`{"detail": "invalid transition: <from> → <to>"}`.

**Diagrama narrativo** (sem ASCII de setas; ler junto da tabela):

- Caminho feliz: `idea → ready → in_progress → review → done`.
- Voltas: `ready → idea` (re-priorizar), `review → in_progress`
  (re-trabalho).
- Saída lateral: qualquer estado **não-terminal** pode ir pra
  `discarded`. (`done` não — é terminal e não vira lixo.)
- Resurrect: `discarded → idea`. Único caminho de saída de
  `discarded`.

**Auto-transition em `start_session`** (chamada via REST `POST
/api/tasks/{id}/sessions` ou `POST /api/sessions {worktree_id}` quick
path):

```python
match task.state:
    case "idea" | "ready" | "review":
        task.state = "in_progress"      # auto-promote
    case "in_progress":
        pass                            # no-op; só verifica 1-active-lock
    case "done" | "discarded":
        raise HTTPException(409,
            "cannot start session: task is in terminal state")
```

Auto-promotion **emite `task.updated`** no WS (cf. §4.2).

### 3.4 1-session-ativa-por-task (concorrência)

`start_session(*, db, runtime, task_id, worktree_id, token_registry, base_url)`:

1. Lock no row de Task (SQLite serializa writes via per-connection
   lock; em Postgres futuro: `SELECT … FOR UPDATE`).
2. Conta sessions da task com `status NOT IN (DONE, ERROR)`.
3. Se ≥1 → `raise HTTPException(409, "task already has active session")`.
4. Auto-transition (cf. §3.3).
5. Cria Session vinculada (resto reutiliza F1 + F2: ai-jail spawn,
   token registry, hook URL).

**Race test obrigatório**: dispara 2 `POST` concorrentes via
`asyncio.gather`. Exatamente 1 retorna 201, o outro 409. (Cf.
`tests/integration/routes/test_task_session_race.py` em §7.2.)

### 3.5 Core API surface (signatures novas/alteradas)

```python
# orchestrator/core/tasks.py — NOVO

class TaskNotFoundError(Exception): ...
class InvalidTransitionError(Exception): ...
class TaskAlreadyHasActiveSessionError(Exception): ...
class TaskInTerminalStateError(Exception): ...

async def create_task(
    db: AsyncSession, *, project_id: str, title: str, description: str = ""
) -> Task: ...

async def list_tasks(
    db: AsyncSession, *, project_ids: Sequence[str] | None = None
) -> Sequence[Task]: ...

async def get_task(db: AsyncSession, task_id: str) -> Task: ...

async def update_task(
    db: AsyncSession,
    task_id: str,
    *,
    title: str | None = None,
    description: str | None = None,
    state: str | None = None,
) -> tuple[Task, str | None]:
    """Returns (task, previous_state).
    previous_state is non-None only when state actually changed."""

async def ensure_task_for_quick_session(
    db: AsyncSession, *, worktree_id: str
) -> Task:
    """Creates 'Quick session · <branch>' task in_progress, returns it."""


# orchestrator/core/sessions.py — EDIT

async def start_session(
    db: AsyncSession,
    runtime: SessionRuntime,
    *,
    task_id: str,                          # NOVO obrigatório
    worktree_id: str,
    token_registry: TokenRegistry | None = None,
    base_url: str | None = None,
) -> ClaudeSession: ...

# stop_session: assinatura inalterada

# orchestrator/core/projects.py — EDIT

class ProjectHasTasksError(Exception): ...

async def delete_project(db: AsyncSession, project_id: str) -> None:
    """Now raises ProjectHasTasksError if project has any task."""
```

API REST traduz `InvalidTransitionError → 422`,
`TaskAlreadyHasActiveSessionError → 409`,
`TaskInTerminalStateError → 409`,
`ProjectHasTasksError → 409`.

## 4. Contratos

### 4.1 REST

| Método | Path | Body | Resposta | Erros |
|---|---|---|---|---|
| POST | `/api/tasks` | `{project_id, title, description?}` | 201 + `TaskRead` | 422 (project_id inválido); 422 (title vazio/whitespace-only) |
| GET | `/api/tasks` | — | 200 + `TaskRead[]` | — |
| GET | `/api/tasks?project_ids=a,b,c` | — | 200 + `TaskRead[]` filtrado | — |
| GET | `/api/tasks/{id}` | — | 200 + `TaskRead` | 404 |
| PATCH | `/api/tasks/{id}` | `{title?, description?, state?}` | 200 + `TaskRead` | 404; 422 (transição inválida; title vazio) |
| POST | `/api/tasks/{id}/sessions` | `{worktree_id}` | 201 + `SessionRead` | 404 (task ou worktree); 409 (já tem ativa); 409 (state terminal) |
| POST | `/api/sessions` | `{worktree_id}` | 201 + `SessionRead` (compat — agora inclui `task_id`) | (cria task implícita atrás dos panos) |
| DELETE | `/api/projects/{id}` | — | 204 (inalterado) | 409 ("project has N tasks; discard them first") |

`TaskRead` schema:

```python
class TaskRead(BaseModel):
    id: str
    project_id: str
    title: str
    description: str
    state: str
    template: str | None
    permission_profile: str | None
    created_at: datetime
    updated_at: datetime
    active_session_id: str | None  # derived
```

`active_session_id` é computado server-side via JOIN +
GROUP BY (uma única query agregada para `list_tasks` —
sem N+1).

`SessionRead` ganha `task_id: str` (campo novo, retrocompatível).

### 4.2 WebSocket events (envelope ADR-0010 + emenda ADR-0014)

`WsEvent` ganha campo top-level `task_id: str | None = None`.
`session_id` continua `str` (preenche `""` para eventos sem
sessão associada).

```ts
// Novos types F4
| { type: "task.created";
    session_id: "";                            // sentinel
    task_id: string;                            // novo top-level
    payload: { project_id: string; title: string; state: string };
    at: string }
| { type: "task.updated";
    session_id: "";
    task_id: string;
    payload: { project_id: string; state: string;
               previous_state: string | null; title: string };
    at: string }

// F2 events (retrocompat) — agora carregam task_id
| { type: "session.status";
    session_id: string;
    task_id: string;                            // novo: id da task pai
    payload: { status: string; previous: string };
    at: string }
| { type: "session.tool_use";
    session_id: string;
    task_id: string;
    payload: { tool: string };
    at: string }
| { type: "session.stopped";
    session_id: string;
    task_id: string;
    payload: {};
    at: string }
```

UI dispatch:

```ts
"task.created" | "task.updated"  → invalidate queryKeys.tasks
"session.status"                 → invalidate queryKeys.sessions +
                                   queryKeys.tasks (re-fetch active_session_id)
"session.stopped"                → idem
```

Backend muda: `core.sessions` factories de `WsEvent.session_*`
recebem `task_id` como kwarg obrigatório. Migration mecânica.

### 4.3 Validação de transição (front + back)

- **Backend** é a verdade absoluta: PATCH com state inválido → 422.
- **Frontend** mantém `isValidTransition(from, to)` em
  `lib/transitions.ts` apenas pra **UX**: drag-drop em coluna inválida
  faz snap-back **antes** de chamar a API + toast. Reduz round-trips.
- Test obrigatório: snap-back assert `patchTask` **NÃO** foi chamado.

## 5. Migração

### 5.1 Migration `alembic/versions/0003_tasks_and_session_task_link.py`

```python
def upgrade() -> None:
    # 1. Cria tabela tasks
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.String(32),
                  sa.ForeignKey("projects.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("state", sa.String(32), nullable=False, server_default="idea"),
        sa.Column("template", sa.String(64), nullable=True),
        sa.Column("permission_profile", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # 2. Adiciona sessions.task_id NULLABLE inicialmente
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.add_column(sa.Column("task_id", sa.String(32),
                                      sa.ForeignKey("tasks.id",
                                                    ondelete="RESTRICT"),
                                      nullable=True))

    # 3. Pré-clean: remove sessions órfãs (sem worktree existente)
    #    Defensivo: SQLite default tem FK off, então órfãs são teoricamente possíveis.
    op.execute(
        "DELETE FROM sessions "
        "WHERE worktree_id NOT IN (SELECT id FROM worktrees)"
    )

    # 4. Backfill: pra cada session restante, cria task auto + vincula
    conn = op.get_bind()
    sessions = conn.execute(sa.text(
        "SELECT s.id, s.worktree_id, w.project_id, w.branch "
        "FROM sessions s JOIN worktrees w ON s.worktree_id = w.id"
    )).fetchall()
    for sess in sessions:
        task_id = uuid4().hex
        conn.execute(sa.text(
            "INSERT INTO tasks (id, project_id, title, description, "
            "state, created_at, updated_at) "
            "VALUES (:id, :pid, :title, '', 'in_progress', :now, :now)"
        ), {"id": task_id, "pid": sess.project_id,
            "title": f"Quick session · {sess.branch or '(detached)'}",
            "now": datetime.now(UTC)})
        conn.execute(sa.text(
            "UPDATE sessions SET task_id = :tid WHERE id = :sid"
        ), {"tid": task_id, "sid": sess.id})

    # 5. NOT NULL (post-backfill, todas as sessions têm task_id)
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.alter_column("task_id", nullable=False)
```

`downgrade`: drop FK + drop column `sessions.task_id`; drop table
`tasks`.

Em DEV (zero rows reais), backfill é no-op silencioso. Em produção
futura, é defensivo (orphan purge + auto-task creation).

**Roundtrip test obrigatório** (`tests/integration/test_migration_0003_roundtrip.py`):
upgrade → assert schema → downgrade → assert schema → upgrade →
assert schema parity. Mesmo padrão do test da `0002`.

## 6. UI / UX

### 6.1 Layout

```
┌────────────────────────────────────────────────────┐
│  J-arvis        [Projetos ▾]                        │
│  Filtros: ☑ projA  ☑ projB  ☐ projC                │
├────────────────────────────────────────────────────┤
│ ┌────────┬────────────┬────────┬──────┬──────────┐│
│ │Backlog │In Progress │ Review │ Done │Discarded ││
│ ├────────┼────────────┼────────┼──────┼──────────┤│
│ │● projA │● projB     │● projA │      │          ││
│ │"Dark.."│"API auth"  │"Login" │      │          ││
│ │ [idea] │ executing  │        │      │          ││
│ │        │            │        │      │          ││
│ │● projB │            │        │      │          ││
│ │"Sched."│            │        │      │          ││
│ │ [ready]│            │        │      │          ││
│ │   +    │            │        │      │          ││
│ └────────┴────────────┴────────┴──────┴──────────┘│
└────────────────────────────────────────────────────┘
```

- **Header**: título + botão "Projetos ▾" (abre drawer).
- **Filtros**: chips clicáveis por project. Estado em
  `localStorage["jarvis.kanban.filters"]` como `string[]`. Sem
  filtro = todos.
- **Cards**: chip colorido (●) com nome do project (cor por hash do
  `project_id` mod 8), título, sub-tag (`[idea]`/`[ready]` na
  Backlog; status da session ativa em In Progress; vazio nas
  demais).
- **+ Nova task**: rodapé da Backlog, formulário inline (project
  dropdown obrigatório, title obrigatório, description opcional,
  botão Criar). Task nasce em `idea`.

### 6.2 Modal (clique no card)

```
┌──────────────────────────────────────┐
│ ● projA · Dark mode             [✕]   │
├──────────────────────────────────────┤
│ Title: [Dark mode______________]      │
│ Description:                          │
│ ┌──────────────────────────────────┐ │
│ │ Implementar dark mode com prefer-│ │
│ │ scheme via CSS vars …            │ │
│ └──────────────────────────────────┘ │
│ Move to: [In Progress ▾]              │
│                                       │
│ Sessions (5 mais recentes):           │
│  • #abc12345 · 2026-05-09 14:32 ·    │
│    done                               │
│  • #def67890 · 2026-05-09 16:00 ·    │
│    executing  [Stop]                  │
│  [+ ver todas]                        │
│                                       │
│ Worktree: [feature/dark-mode ▾]       │
│         [▶ Iniciar sessão]            │
└──────────────────────────────────────┘
```

- Title/description inline-editáveis (debounced PATCH 500ms).
  Title vazio bloqueia salvamento (validação client-side espelha
  422 do backend).
- **Move to dropdown**: lista os estados válidos a partir do estado
  atual (cf. tabela §3.3). Único caminho pra `ready → idea`,
  `discarded → idea` resurrect, e qualquer transição que o drag-drop
  não cobre (mesmo-coluna em Backlog).
- Histórico de sessions: 5 mais recentes em ordem cronológica desc.
  Botão "ver todas" expande. Stop button só na ativa.
- Iniciar sessão: dropdown filtrado pelos worktrees do `project_id`
  da task. Disabled se task em `done` ou `discarded`. 409 vira toast
  legível ("Esta task já tem sessão ativa").

### 6.3 Drag-and-drop (dnd-kit)

- `<DndContext>` envolve o kanban; `<SortableContext>` por coluna.
- `<TaskCard>` é sortable item.
- **Resolução de coluna → estado canônico** (`resolveColumnState`):
  - Drag para Backlog → estado canônico **`ready`** (preserva a
    promoção anterior; `→ idea` só via modal).
  - Drag para In Progress → `in_progress`.
  - Drag para Review → `review`.
  - Drag para Done → `done`.
  - Drag para Discarded → `discarded`.
- **Reorder intra-column = no-op** (sem PATCH; só posicionamento
  visual via `useSortable`).
- `onDragEnd`:
  1. Resolve target column → estado canônico via `resolveColumnState`.
  2. Se igual ao atual, no-op.
  3. Chama `isValidTransition(from, to)`. Inválida → snap-back +
     toast "Transição não permitida". `patchTask` **NÃO** é
     chamado.
  4. Otimisticamente atualiza cache via `queryClient.setQueryData`.
  5. Dispara `patchTask({state})`. Erro → rollback + toast.
- Keyboard: dnd-kit's `KeyboardSensor` (Tab + Space + arrows). Spec
  obrigatório para a11y.
- **Pré-spike** (F4.0): instalar dnd-kit + renderizar lista
  sortable trivial em branch throwaway antes de iniciar F4.h. Se
  conflict de peer dep com React 19 não resolvido por
  `--legacy-peer-deps`, fallback para `@hello-pangea/dnd` é
  ativado e §6.3 reescrito.

## 7. Testes

### 7.1 Unit (Python)

| Arquivo | Cobertura |
|---|---|
| `tests/unit/test_task_state_machine.py` | `is_valid_transition` cross-product (6×6) + idempotent same-state |
| `tests/unit/test_task_crud.py` | `create_task` (com/sem description), `list_tasks` (com/sem `project_ids`), `get_task`, `update_task` (cada campo isoladamente) |
| `tests/unit/test_task_title_validation.py` | title vazio/whitespace-only rejeitado em `create_task` e `update_task` |
| `tests/unit/test_task_auto_transition.py` | `start_session` força `idea→in_progress`, `ready→in_progress`, `review→in_progress`, no-op em `in_progress`, 409 em `done`/`discarded` |
| `tests/unit/test_quick_session_creates_task.py` | `ensure_task_for_quick_session` cria task `"Quick session · <branch>"` |
| `tests/unit/test_session_per_task_lock.py` | 409 ao iniciar 2ª session ativa **sequencialmente** |
| `tests/unit/test_project_delete_blocked.py` | `delete_project` levanta `ProjectHasTasksError` quando há tasks |
| `tests/unit/test_ws_envelope_tasks.py` | `WsEvent.task_created/task_updated` factories; `session_*` factories aceitam `task_id` |

### 7.2 Integration

| Arquivo | Cobertura |
|---|---|
| `tests/integration/routes/test_tasks_route.py` | POST/GET-list/GET-one/PATCH paths inteiros, 404/422 paths, PATCH idempotent same-state retorna 200, resurrect `discarded → idea` |
| `tests/integration/routes/test_task_session_route.py` | POST `/tasks/{id}/sessions`, 409 paths (already-active + terminal-state), broadcast de `task.updated` em auto-transition |
| `tests/integration/routes/test_task_session_race.py` | 2 `POST` concorrentes via `asyncio.gather`: exatamente 1 ganha 201, outro 409 |
| `tests/integration/routes/test_quick_session_creates_task.py` | POST `/sessions {worktree_id}` cria task atrás dos panos; resposta inclui `task_id` |
| `tests/integration/routes/test_tasks_filter_project_ids.py` | `?project_ids=a,b` filtra cross-project |
| `tests/integration/routes/test_project_delete_409.py` | DELETE project com tasks → 409 com mensagem |
| `tests/integration/test_migration_0003_roundtrip.py` | upgrade→downgrade→upgrade preserva schema |

### 7.3 Vitest (UI)

| Arquivo | Cobertura |
|---|---|
| `ui/src/lib/transitions.test.ts` | `isValidTransition` cross-product; `resolveColumnState` por coluna |
| `ui/src/lib/projectColor.test.ts` | hash determinístico, paleta de 8 cores conhecidas |
| `ui/src/lib/kanbanFilters.test.ts` | load/save em `localStorage`, ids ausentes silenciosamente filtrados |
| `ui/src/lib/errorMessages.test.ts` | mapeia erros 409/422 conhecidos para pt-BR |
| `ui/src/components/TaskCard.test.tsx` | render com chip + sub-tag |
| `ui/src/components/Kanban.test.tsx` | dnd válido (move state), dnd inválido (snap-back **+ patchTask não chamado**), filtros aplicados, intra-column reorder não chama patchTask |
| `ui/src/components/TaskDetailModal.test.tsx` | edit debounced, Move-to dropdown lista só transições válidas, "iniciar sessão" disable em `done`/`discarded` |
| `ui/src/components/NewTaskForm.test.tsx` | submit cria task; title vazio bloqueia botão |
| `ui/src/hooks/useTasks.test.ts` | invalida em `task.created`/`task.updated`/`session.status` (via task_id) |

### 7.4 E2E (Playwright)

| Fluxo | Detalhe |
|---|---|
| Kanban happy path | Criar projeto + worktree → criar task → drag idea→ready (via modal) → "Iniciar sessão" (com `NullSessionRuntime`) → auto-In Progress → drag → Review → Done → assert localizações |
| Quick session cria task | Click "▶ Quick session" numa worktree → assert task aparece em In Progress com title `"Quick session · <branch>"` |
| Transição inválida | Tentar drag de Done → Backlog → snap-back + toast |
| Filtro multi-project + persistência | 2 projects, 4 tasks → filtra apenas projA → 2 tasks visíveis → reload → ainda filtrado |
| Duplo iniciar = 409 | Iniciar sessão + tentar iniciar segunda na mesma task → toast "já tem sessão ativa" |
| Project delete bloqueado | Tentar deletar project com tasks → toast "discard tasks first" |

## 8. Compatibilidade

- **F1 + F2 contratos**: 100% intactos no shape externo. Hooks, WS
  do tipo session, notify-send seguem idênticos. **Mudança aditiva
  no envelope WS**: `task_id` opcional aparece em todos os eventos
  (cf. ADR-0014); clients antigos ignoram.
- **POST `/api/sessions {worktree_id}`** mantido por compat — agora
  delega a `core.tasks.ensure_task_for_quick_session`. Resposta
  `SessionRead` ganha `task_id` (campo novo, retrocompatível).
- **DB**: zero rows existentes em produção; backfill da migration
  é defensivo pra dev local com possíveis órfãos.
- **`delete_project`** ganha contrato de erro novo (`409` se há
  tasks). Chamadores existentes (UI Projects) precisam atualizar
  pra exibir o toast — feito como parte de F4.j (ProjectsDrawer).

## 9. Riscos e questões em aberto

| # | Risco | Mitigação |
|---|---|---|
| 1 | dnd-kit + React 19: peer dep conflict | F4.0 (spike): instalar + sortable trivial. Versão alvo: `@dnd-kit/core@^6.3` e `@dnd-kit/sortable@^8`. Fallback: `@hello-pangea/dnd` (fork ativo do `react-beautiful-dnd`, pelo time Atlaskit) |
| 2 | Filter state em `localStorage` cresce sem limite se projects forem deletados | IDs inexistentes silenciosamente filtrados ao ler (cf. `kanbanFilters.ts`). Cleanup explícito é YAGNI |
| 3 | Race em `1-session-ativa-por-task` em SQLite | SQLite serializa writes (per-conn lock). Race test usa `asyncio.gather` em integration. Em Postgres futuro: `SELECT … FOR UPDATE` explícito |
| 4 | Histórico de sessions cresce sem limite na modal | Cap em 5 mais recentes + "ver todas" expand. Paginação real entra se virar dor (F4.5+) |
| 5 | E2E precisa rodar fora da jaula ai-jail (gotcha #9) | Mesma restrição de F2; user roda manual ou em CI |
| 6 | dnd em E2E (Playwright) | Playwright tem `dragTo` mas dnd-kit pode precisar `mouse.down/move/up` manual. Validar no F4.0 spike |
| 7 | `active_session_id` derivation custosa | `list_tasks` faz JOIN agregado (single query) — sem N+1. Documentar no `core/tasks.list_tasks` |

## 10. Cronograma estimado de tasks (writing-plans expandirá)

- **F4.0**: Spike dnd-kit + React 19 (~1h, branch throwaway). Se
  passa, segue F4.a. Se não, fallback `@hello-pangea/dnd` e §6.3
  reescrito.
- F4.a: Schema (Task + sessions.task_id) + migration `0003` +
  bootstrap + roundtrip test
- F4.b: `core/tasks.py` + state machine validation +
  `delete_project` bloqueado
- F4.c: `core/sessions.py` ajustes (`task_id` kw, auto-transition,
  1-active-lock + race test)
- F4.d: API routes `/api/tasks/*` + `/api/tasks/{id}/sessions`
- F4.e: Quick-session compat (`POST /api/sessions` cria task) +
  `SessionRead.task_id`
- F4.f: WS event types + factories (envelope `task_id`,
  `task_created`, `task_updated`, `session_*` updates) + ADR-0014
- F4.g: UI lib (transitions.ts, projectColor.ts, kanbanFilters.ts,
  errorMessages.ts, api.ts edits, events.ts edits)
- F4.h: Kanban + KanbanColumn + TaskCard + dnd integration
- F4.i: TaskDetailModal + NewTaskForm + ProjectFilters + Move-to
  dropdown
- F4.j: ProjectsDrawer (encapsula UI atual + toast em delete-409)
- F4.k: App.tsx layout reorg + useTasks hook + useSessionEvents
  estende (invalida tasks em `session.status`)
- F4.l: E2E flows + ARCHITECTURE update + ADR-0012/0013/0014 + nota
  no `docs/adr/README.md` + Demo manual
