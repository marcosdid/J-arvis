# F4 — Backlog Kanban Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promover `Task` a entidade primária; Session vira filha obrigatória de Task; UI ganha kanban unificado cross-project com 5 colunas e drag-and-drop entre estados; quick session continua funcionando criando Task implícita.

**Architecture:** Backend adiciona tabela `tasks`, migration `0003`, módulo `core/tasks.py` com state machine server-validated, e rotas `/api/tasks/*`. `core/sessions.start_session` ganha `task_id` obrigatório + auto-transition + lock 1-active-per-task. Envelope WS estende-se com campo opcional `task_id` (ADR-0014, emenda aditiva ao ADR-0010). Frontend reorganiza-se em torno de Kanban cross-project com `@dnd-kit`; Projects/Worktrees viram drawer lateral. Erros backend em en-US, UI mapeia pra pt-BR.

**Tech Stack:** Python 3.13 + FastAPI + SQLAlchemy 2 async + Alembic + pytest/asyncio + httpx + testcontainers / React 19 + Vite 6 + TanStack Query + Zustand + `@dnd-kit/core`@^6.3 + `@dnd-kit/sortable`@^8 + Vitest + Playwright.

**Spec:** `docs/superpowers/specs/2026-05-09-f4-backlog-kanban-design.md`

---

## File Structure

### Backend (novos)

| Path | Responsabilidade |
|---|---|
| `orchestrator/core/tasks.py` | Domínio: `is_valid_transition`, `create_task`, `list_tasks`, `get_task`, `update_task`, `ensure_task_for_quick_session`, exceptions. |
| `orchestrator/api/tasks.py` | FastAPI router `/api/tasks/*` + `POST /api/tasks/{id}/sessions`. |
| `alembic/versions/0003_tasks_and_session_task_link.py` | Migration aditiva: tabela `tasks`, FK `sessions.task_id`, backfill defensivo. |
| `docs/adr/0012-task-como-entidade-primaria.md` | ADR. |
| `docs/adr/0013-kanban-unificado-cross-project.md` | ADR. |
| `docs/adr/0014-envelope-ws-task-id-opcional.md` | ADR (emenda aditiva ao ADR-0010). |

### Backend (modificados)

| Path | Mudança |
|---|---|
| `orchestrator/store/models.py` | + classe `Task`; `ClaudeSession.task_id` NOT NULL FK. |
| `orchestrator/core/sessions.py` | `start_session` ganha kwarg `task_id`; auto-transition; lock 1-active. |
| `orchestrator/core/projects.py` | `delete_project` levanta `ProjectHasTasksError` se há tasks. |
| `orchestrator/api/sessions.py` | `POST /sessions` delega a `ensure_task_for_quick_session`; `SessionRead.task_id`. |
| `orchestrator/api/projects.py` | DELETE traduz `ProjectHasTasksError` → 409. |
| `orchestrator/api/_deps.py` | (sem mudança esperada — `get_db_session` reutilizado). |
| `orchestrator/events/envelope.py` | `WsEvent.task_id: str \| None`; novos factories `task_created`/`task_updated`; `session_*` factories aceitam `task_id`. |
| `orchestrator/hooks/router.py` | Passa `task_id` aos broadcasts existentes. |
| `orchestrator/main.py` | Registra `tasks_router`. |

### Frontend (novos)

| Path | Responsabilidade |
|---|---|
| `ui/src/lib/transitions.ts` | `isValidTransition(from, to)` + `resolveColumnState(column, from)`. |
| `ui/src/lib/projectColor.ts` | hash → cor da paleta de 8. |
| `ui/src/lib/kanbanFilters.ts` | load/save em `localStorage["jarvis.kanban.filters"]`. |
| `ui/src/lib/errorMessages.ts` | map en→pt-BR de erros 409/422. |
| `ui/src/components/Kanban.tsx` | Layout cross-project, `<DndContext>`, render de 5 colunas. |
| `ui/src/components/KanbanColumn.tsx` | Coluna droppable + sortable. |
| `ui/src/components/TaskCard.tsx` | Sortable item, chip+title+sub-tag. |
| `ui/src/components/TaskDetailModal.tsx` | Title/desc edit + history + iniciar + Move-to dropdown. |
| `ui/src/components/NewTaskForm.tsx` | Form inline no rodapé da Backlog. |
| `ui/src/components/ProjectFilters.tsx` | Multi-select chips no header. |
| `ui/src/components/ProjectsDrawer.tsx` | Drawer lateral; encapsula UI atual + toast em delete-409. |
| `ui/src/hooks/useTasks.ts` | Query + invalidação por WS. |
| `ui/src/hooks/useTaskMutations.ts` | create / patch / start session. |

### Frontend (modificados)

| Path | Mudança |
|---|---|
| `ui/src/App.tsx` | Layout reorganizado: header + filtros + Kanban; Projects/Worktrees viram drawer. |
| `ui/src/lib/api.ts` | + `createTask`, `listTasks`, `getTask`, `patchTask`, `startTaskSession`. |
| `ui/src/lib/events.ts` | + types `task.created`, `task.updated`; `session.*` types ganham `task_id`. |
| `ui/src/lib/query-keys.ts` | + `tasks`, `tasks_for_project(id)`. |
| `ui/src/hooks/useSessionEvents.ts` | Estende para invalidar `tasks` em `session.status`. |
| `ui/package.json` | + `@dnd-kit/core`, `@dnd-kit/sortable`. |

### Documentos (modificados)

| Path | Mudança |
|---|---|
| `ARCHITECTURE.md` | §3 (data model: Task), §4 (sem mudança), §11 (F4 atualizado), §13 (rows ADR-0012/0013/0014). |
| `docs/adr/README.md` | Index das ADRs novas. |

### Tests

| Camada | Path |
|---|---|
| Unit Python | `tests/unit/test_task_state_machine.py`, `test_task_crud.py`, `test_task_title_validation.py`, `test_task_auto_transition.py`, `test_quick_session_creates_task.py`, `test_session_per_task_lock.py`, `test_project_delete_blocked.py`, `test_ws_envelope_tasks.py`. |
| Integration | `tests/integration/test_tasks_route.py`, `test_task_session_route.py`, `test_task_session_race.py`, `test_quick_session_creates_task.py`, `test_tasks_filter_project_ids.py`, `test_project_delete_409.py`, `tests/integration/test_migration_0003_roundtrip.py`. |
| E2E | `tests/e2e/test_kanban_e2e_flow.py`. |
| Vitest | `ui/src/lib/transitions.test.ts`, `projectColor.test.ts`, `kanbanFilters.test.ts`, `errorMessages.test.ts`, `ui/src/components/TaskCard.test.tsx`, `Kanban.test.tsx`, `TaskDetailModal.test.tsx`, `NewTaskForm.test.tsx`, `ProjectFilters.test.tsx`, `ProjectsDrawer.test.tsx`, `ui/src/hooks/useTasks.test.ts`. |

---

## Pre-flight corrections (READ BEFORE EXECUTING)

Plan review (iteração 1) levantou 7 críticos + 10 importantes. As correções abaixo **substituem** instruções equivalentes no corpo do plan. Aplicar **conforme cada task chega**, não em uma passada só.

### PFC-1 — Paths de integration tests (FLAT, sem `routes/`)

Os tests integration neste repo são todos em `tests/integration/test_*.py` (flat). **Ignore qualquer `tests/integration/routes/...` no plan body**. Use:

| Plan body diz | Use |
|---|---|
| `tests/integration/test_tasks_route.py` | `tests/integration/test_tasks_route.py` |
| `tests/integration/test_task_session_route.py` | `tests/integration/test_task_session_route.py` |
| `tests/integration/test_task_session_race.py` | `tests/integration/test_task_session_race.py` |
| `tests/integration/test_quick_session_creates_task.py` | `tests/integration/test_quick_session_creates_task.py` |
| `tests/integration/test_tasks_filter_project_ids.py` | `tests/integration/test_tasks_filter_project_ids.py` |
| `tests/integration/test_project_delete_409.py` | `tests/integration/test_project_delete_409.py` |

### PFC-2 — Padrão de integration test (sem fixtures globais novas)

Os exemplos de teste no plan body usam fixtures `client`, `project_id`, `worktree_id`, `ws_collector`, `two_projects` que **não existem** em `tests/integration/conftest.py` (que tem só `db` e `runtime`/`FakeSessionRuntime`). Em vez de criar essas fixtures, **siga o padrão de `tests/integration/test_sessions_api.py`**: cada test cria seu próprio `AsyncClient` + seed via helpers `_make_repo` + `_create_project_and_worktree`. Esses helpers já existem em `test_sessions_api.py`; copie-os ou extraia pra `conftest.py` como funções (não fixtures), no início do F4.d:

```python
# Add to tests/integration/conftest.py — module-level helpers, NOT fixtures
import os
import subprocess
from pathlib import Path

from httpx import AsyncClient


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True, capture_output=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.com",
        },
    )


def make_repo(parent: Path, name: str = "repo") -> Path:
    repo = parent / name
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    (repo / "f").write_text("x", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "-c", "commit.gpgsign=false", "commit", "-m", "init")
    return repo


async def create_project_and_worktree(
    client: AsyncClient, repo: Path
) -> tuple[str, str]:
    project = (await client.post("/api/projects", json={"name": repo.name, "path": str(repo)})).json()
    worktrees = (await client.get(f"/api/projects/{project['id']}/worktrees")).json()
    return project["id"], worktrees[0]["id"]
```

Tests integration então ficam:

```python
async def test_post_task_201(db: Database, runtime, tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        pid, wid = await create_project_and_worktree(client, repo)
        r = await client.post("/api/tasks", json={"project_id": pid, "title": "T"})
        assert r.status_code == 201
```

WS event collection: existe um padrão em `tests/integration/test_ws_endpoint.py` que conecta um WS via `httpx.AsyncClient.websocket_connect` e drena. Reutilize esse padrão em vez de inventar `ws_collector`.

### PFC-3 — `core.worktrees.create_worktree` não existe; seed via models

**Não importe `from tests.unit.test_session_token_lifecycle import _seed_worktree  # ou inlinar — ver PFC-3`** em qualquer test (F4.c, F4.e, e onde mais aparecer). O módulo `core/worktrees.py` só tem `list_project_worktrees`. Em unit tests, seed direto via SQLAlchemy — **importante**: `Project.id`/`Worktree.id` só ficam populados após `commit + refresh`. Pattern correto:

```python
from orchestrator.store.models import Project, Worktree

async def _seed_project_and_worktree(db_session, tmp_path) -> tuple[str, str]:
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / ".git").mkdir()
    # 1. Cria Project, commit, refresh → p.id passa de None pra UUID
    p = Project(name="p", path=str(repo))
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    # 2. Agora cria Worktree com p.id já populado
    w = Worktree(project_id=p.id, path=str(repo), branch="main")
    db_session.add(w)
    await db_session.commit()
    await db_session.refresh(w)
    return p.id, w.id
```

Padrão idêntico ao `_seed_worktree` em `tests/unit/test_session_token_lifecycle.py:23-33`. Reusar quando possível.

Em integration tests, use o caminho via REST (cf. PFC-2, `create_project_and_worktree`).

### PFC-4 — F1/F2 ripple do `start_session` keyword-only

F4.c muda `start_session` de positional → keyword-only (`*, task_id, worktree_id, …`). Isso quebra:

| Arquivo | Linhas | Fix |
|---|---|---|
| `tests/unit/test_session_token_lifecycle.py` | 44-50, 64-70 | Substitui `start_session(db, runtime, worktree_id, ...)` por `start_session(db, runtime, task_id=t.id, worktree_id=worktree_id, ...)` + seed de `Task` antes do call |
| `tests/integration/test_session_lifecycle_with_hooks.py` | (verificar) | Mesma coisa se chama `start_session` direto. Provavelmente passa pela API REST e fica OK |
| `tests/integration/test_sessions_api.py` | (passa pela API) | Provavelmente OK; API delega a `ensure_task_for_quick_session` em F4.e — depois desse F4.e a compat volta |

**Adicionar como sub-step F4.c.10b** (entre Steps 10 e 11):

```bash
# Atualizar callers F1/F2 que ainda passam positional:
# 1. tests/unit/test_session_token_lifecycle.py:
#    - Antes de cada start_session(), criar task via:
#         t = await create_task(db_session, project_id=pid, title="seed")
#    - Trocar start_session(db, runtime, worktree_id, …) por
#         start_session(db, runtime, task_id=t.id, worktree_id=worktree_id, …)
# 2. Rodar uv run pytest tests/unit/test_session_token_lifecycle.py -v
#    Expected: passa.
```

### PFC-5 — `_build_task_read` N+1 violação spec §4.1

O plan body F4.d Step 3 escreve `_build_task_read` que faz 1 query por task pra resolver `active_session_id`. Spec §4.1 explicitamente diz "single query agregada — sem N+1". Substituir o loop em `get_tasks` por:

```python
@router.get("", response_model=list[TaskRead])
async def get_tasks(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    project_ids: Annotated[str | None, Query()] = None,
) -> list[TaskRead]:
    ids = project_ids.split(",") if project_ids else None
    rows = await list_tasks(db, project_ids=ids)
    if not rows:
        return []
    # Single LEFT JOIN agregado: task → primeira session não-terminal
    stmt = (
        select(ClaudeSession.task_id, func.min(ClaudeSession.id).label("active_id"))
        .where(
            ClaudeSession.task_id.in_([r.id for r in rows]),
            ClaudeSession.status.notin_(["done", "error"]),
        )
        .group_by(ClaudeSession.task_id)
    )
    active_by_task = dict((await db.execute(stmt)).all())
    return [
        TaskRead.model_validate(r).model_copy(
            update={"active_session_id": active_by_task.get(r.id)}
        )
        for r in rows
    ]
```

`get_task_route` (single) pode manter o lookup individual (não é N+1 — é 1+1).

### PFC-6 — `task.created` deve disparar no quick-session path

F4.f deve **explicitamente** broadcast `task.created` em `api/sessions.py::post_session` após `ensure_task_for_quick_session` retornar. Adicionar como sub-step F4.f.7b:

```python
# orchestrator/api/sessions.py — em post_session, após ensure_task_for_quick_session:
broadcaster = request.app.state.ws_broadcaster
if broadcaster is not None:
    await broadcaster.publish(WsEvent.task_created(
        task_id=task.id, project_id=task.project_id,
        title=task.title, state=task.state,
    ))
```

E adicionar test integration: quick-session broadcast inclui `task.created` E `session.status` (com `task_id` preenchido).

### PFC-7 — DnD `over.id` collision entre coluna e card (F4.h)

Plan body F4.h Step 7 usa `useDroppable({id: name})` — mesma namespace de `useSortable({id: task.id})`. Quando arrastar `t1` sobre `t2` (mesma coluna), `over.id === 't2'`, não o nome da coluna → `resolveColumnState('t2', ...)` joga `unknown kanban column`.

**Fix obrigatório**: prefixar IDs de coluna com `column:`:

```tsx
// KanbanColumn.tsx
const { setNodeRef } = useDroppable({ id: `column:${name}` });
// data-testid não muda

// Kanban.tsx onDragEnd — resolver coluna via prefixo OU via lookup do task
function onDragEnd(e: DragEndEvent): void {
  const taskId = String(e.active.id);
  const overId = e.over ? String(e.over.id) : null;
  if (!overId) return;
  let columnName: string;
  if (overId.startsWith('column:')) {
    columnName = overId.slice('column:'.length);
  } else {
    // overId é um task.id; achar a coluna do task atual
    const overTask = taskById.get(overId);
    if (!overTask) return;
    columnName = stateToColumn(overTask.state);
  }
  handleDragEnd(taskId, columnName);
}

function stateToColumn(state: string): string {
  if (state === 'idea' || state === 'ready') return 'Backlog';
  if (state === 'in_progress') return 'In Progress';
  if (state === 'review') return 'Review';
  if (state === 'done') return 'Done';
  return 'Discarded';
}
```

### PFC-8 — `core/projects.py` `delete_project` imports no topo

Plan body F4.b Step 13 sugere imports locais dentro de `delete_project` ("evita ciclo"). Não há ciclo. Mover pra topo:

```python
# orchestrator/core/projects.py — top imports (após existing)
from sqlalchemy import func, select
from orchestrator.store.models import Project, Task

# delete_project usa esses sem import local
```

### PFC-9 — F4.d falta race test (spec §7.2 row 3)

Adicionar nova sub-task **F4.d Step 9b** (depois de Step 9, antes de Step 11 commit):

```python
# tests/integration/test_task_session_race.py
import asyncio
import pytest
from httpx import ASGITransport, AsyncClient
from pathlib import Path

from orchestrator.main import create_app
from orchestrator.store.database import Database
from tests.integration.conftest import (
    FakeSessionRuntime, make_repo, create_project_and_worktree,
)


@pytest.mark.integration
async def test_two_concurrent_starts_one_wins_one_409(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path
) -> None:
    repo = make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        pid, wid = await create_project_and_worktree(client, repo)
        t = (await client.post("/api/tasks", json={
            "project_id": pid, "title": "T",
        })).json()
        rs = await asyncio.gather(
            client.post(f"/api/tasks/{t['id']}/sessions", json={"worktree_id": wid}),
            client.post(f"/api/tasks/{t['id']}/sessions", json={"worktree_id": wid}),
        )
        statuses = sorted(r.status_code for r in rs)
        assert statuses == [201, 409]
```

### PFC-10 — Test seam `test:dragEnd` deve gatear ambiente

F4.h Step 8 monta `window.addEventListener('test:dragEnd', ...)` sem dep array e sem gate de ambiente — vaza pra produção. Trocar por:

```tsx
// Kanban.tsx — useEffect
useEffect(() => {
  if (import.meta.env.MODE !== 'test') return;
  function fromCustom(ev: Event): void {
    const detail = (ev as CustomEvent).detail;
    handleDragEnd(detail.taskId, detail.column);
  }
  window.addEventListener('test:dragEnd', fromCustom);
  return () => window.removeEventListener('test:dragEnd', fromCustom);
}, []);   // dep array vazio: registra/desregistra uma vez
```

(`handleDragEnd` lê do closure — em produção não importa porque o effect não roda; em testes Vitest define `import.meta.env.MODE === 'test'`.)

### PFC-11 — `WsEvent.session_status` factory: preservar tipos `str` (não loosen)

F2 já tipa `new_status: str, previous_status: str` (StrEnum subclass de str → passa direto). F4.f não deve dropar essas annotations nem inserir `str()` cast. Manter tipos.

### PFC-12 — Migration test fixture path absoluto

F4.a Step 1 `Config("alembic.ini")` é cwd-relative. Trocar por:

```python
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def alembic_config(tmp_path: Path) -> Config:
    db_url = f"sqlite:///{tmp_path / 'roundtrip.db'}"
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg
```

### PFC-13 — `useTaskWsInvalidator` não usar (dead code)

F4.h Step 4 define `useTaskWsInvalidator` mas nunca conecta. F4.k Step 1 estende `useSessionEvents` direto — então `useTaskWsInvalidator` é dead code. **Remover do plan**: deletar a função inteira. Tasks/sessões invalidam tudo via `useSessionEvents` extendido.

### PFC-14 — `resolveColumnState` segundo arg unused

`resolveColumnState(column, _from)` ignora o segundo arg. Remover da signature: `resolveColumnState(column: string): string`. Tests ajustam assinatura.

### PFC-15 — Hook router task_id sem re-fetch

F4.f Step 5 propõe `_resolve_session_and_task` que faz `db.get(ClaudeSession, sid)` de novo. O handler já tem o row em escopo via `update_status` ou similar. Refatorar pra ler `row.task_id` do row já buscado em `_summary` ou no próprio `update_status`. Em F4.f, modificar `update_status` pra retornar (prev, new, task_id) ou modificar `_summary` pra retornar task_id também.

Mais simples: dentro de cada handler de hook (`hook_notification`, `hook_pretooluse`, `hook_stop`), após `_resolve_or_404`, fazer um `await db.get(ClaudeSession, sid)` **uma única vez** e reusar o `row.task_id` em todos os broadcasts daquele handler.

---

## Disciplina

- **TDD strict** (RED → GREEN → REFACTOR → COMMIT). Não escrever produção sem teste falhando.
- **Coverage**: 100% no código novo, **dotted-module form** (`--cov=orchestrator.core.tasks` NÃO `--cov=orchestrator/core/tasks` — gotcha do F2).
- **`# pragma: no cover`** apenas em: defesa de plataforma; branches inacessíveis; registro condicional em `_build_production_app`.
- **Code-review subagent antes de cada commit** (per global CLAUDE.md). Dispatch via `Agent(subagent_type="superpowers:code-reviewer", ...)`.
- Cada `git commit` usa HEREDOC, sem `--no-verify`.
- Comandos pytest sempre `uv run pytest …`. Vitest `pnpm --dir ui exec vitest …`.
- **Decomposição**: cada Task abaixo = uma sub-fase F4.X. Ordem **obrigatória** F4.0 → F4.l (dependências de migração + tipos + componentes). F4.0 é spike validatório.
- **Branch atual**: `claude/fresh-start-cleanup-XDaHV` (continuação do F2).
- **Naming i18n**: backend errors **en-US** (logs/curl); UI traduz via `lib/errorMessages.ts` pra pt-BR.

---

## Task 0 — F4.0: Spike `@dnd-kit` + React 19 (validation gate)

**Objetivo:** validar que `@dnd-kit/core@^6.3` + `@dnd-kit/sortable@^8` instalam sem peer dep conflict no ecossistema React 19 + Vite 6 atuais. Se passar: usa dnd-kit; se falhar: aborta plan e troca pra `@hello-pangea/dnd` na próxima iteração.

**Files:**
- (throwaway) `ui/src/__spike__/SortableSpike.tsx`
- Modify: `ui/package.json`

- [ ] **Step 1: Verificar React/Vite versions atuais**

```bash
cat ui/package.json | grep -E '"react"|"react-dom"|"vite"'
```

Esperado: `"react": "^19...", "react-dom": "^19...", "vite": "^6..."`.

- [ ] **Step 2: Instalar dnd-kit**

```bash
pnpm --dir ui add @dnd-kit/core@^6.3 @dnd-kit/sortable@^8
```

Esperado: instala sem error de peer deps. Se aparecer `ERR_PNPM_PEER_DEP_ISSUES` referente a React 19, abortar e notar no §9 da spec.

- [ ] **Step 3: Componente sortable trivial**

```tsx
// ui/src/__spike__/SortableSpike.tsx
import { DndContext, closestCenter } from '@dnd-kit/core';
import {
  SortableContext, useSortable, verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { useState } from 'react';

function Item({ id }: { id: string }) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id });
  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      {...attributes}
      {...listeners}
    >
      {id}
    </li>
  );
}

export function SortableSpike() {
  const [items, setItems] = useState(['a', 'b', 'c']);
  return (
    <DndContext
      collisionDetection={closestCenter}
      onDragEnd={(e) => {
        const { active, over } = e;
        if (!over || active.id === over.id) return;
        setItems((xs) => {
          const oldIdx = xs.indexOf(String(active.id));
          const newIdx = xs.indexOf(String(over.id));
          const next = xs.slice();
          next.splice(oldIdx, 1);
          next.splice(newIdx, 0, String(active.id));
          return next;
        });
      }}
    >
      <SortableContext items={items} strategy={verticalListSortingStrategy}>
        <ul>{items.map((id) => <Item key={id} id={id} />)}</ul>
      </SortableContext>
    </DndContext>
  );
}
```

- [ ] **Step 4: Adicionar render temporário em App.tsx**

Apenas pra confirmar que monta sem crash. Linha temporária:
```tsx
import { SortableSpike } from './__spike__/SortableSpike';
// dentro de App: <SortableSpike />
```

- [ ] **Step 5: pnpm build e dev verificam**

```bash
pnpm --dir ui run build
pnpm --dir ui run dev   # smoke test manual (Ctrl-C após confirmar render)
```

Esperado: build OK; dev render mostra lista a/b/c sortable via mouse.

- [ ] **Step 6: Cleanup do spike + lock-in das versões**

Remover `__spike__/SortableSpike.tsx`, remover render temporário em `App.tsx`. Manter dependências em `package.json`.

- [ ] **Step 7: Code review subagent**

Prompt: "Review staged: ui/package.json + ui/pnpm-lock.yaml. Confirm dnd-kit versions are compatible with React 19 + Vite 6 in this repo. Confirm no spike file leaked."

- [ ] **Step 8: Commit**

```bash
git add ui/package.json ui/pnpm-lock.yaml
git commit -m "$(cat <<'EOF'
chore(F4.0): add @dnd-kit/core@^6.3 + @dnd-kit/sortable@^8 (spike validated)

Pre-spike confirmou que dnd-kit instala em React 19 + Vite 6 sem peer
dep conflict. Render trivial sortable funcional. Próximas tasks F4.h
podem usar.
EOF
)"
```

**Falha-aborto**: se Step 2 ou Step 5 falharem, parar plan, abrir issue de fallback `@hello-pangea/dnd`, refazer §6.3 do spec.

---

## Task 1 — F4.a: Schema `tasks` + migration `0003` + bootstrap

**Objetivo:** criar tabela `tasks`, adicionar `sessions.task_id` NOT NULL, com backfill defensivo + roundtrip test.

**Files:**
- Modify: `orchestrator/store/models.py`
- Create: `alembic/versions/0003_tasks_and_session_task_link.py`
- Create: `tests/integration/test_migration_0003_roundtrip.py`

- [ ] **Step 1: Teste de roundtrip falhando**

```python
# tests/integration/test_migration_0003_roundtrip.py
"""Roundtrip da migration 0003: upgrade → downgrade → upgrade."""
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


@pytest.fixture
def alembic_config(tmp_path: Path) -> Config:
    db_url = f"sqlite:///{tmp_path / 'roundtrip.db'}"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _columns(engine, table: str) -> set[str]:
    return {c["name"] for c in inspect(engine).get_columns(table)}


def test_migration_0003_roundtrip(alembic_config: Config) -> None:
    db_url = alembic_config.get_main_option("sqlalchemy.url")
    engine = create_engine(db_url)

    command.upgrade(alembic_config, "0003")
    assert "tasks" in inspect(engine).get_table_names()
    assert "task_id" in _columns(engine, "sessions")
    cols_after_up = _columns(engine, "sessions")

    command.downgrade(alembic_config, "0002")
    assert "tasks" not in inspect(engine).get_table_names()
    assert "task_id" not in _columns(engine, "sessions")

    command.upgrade(alembic_config, "0003")
    assert _columns(engine, "sessions") == cols_after_up
```

- [ ] **Step 2: RED**

Run: `uv run pytest tests/integration/test_migration_0003_roundtrip.py -v`
Expected: erro porque `0003` não existe.

- [ ] **Step 3: Adicionar Task ao models.py**

```python
# orchestrator/store/models.py — append after ClaudeSession class
class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text(), nullable=False, default="")
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="idea")
    template: Mapped[str | None] = mapped_column(String(64), nullable=True)
    permission_profile: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now)
```

E adicionar `from sqlalchemy import Text` no topo se ainda não tiver.

- [ ] **Step 4: Adicionar `task_id` em ClaudeSession**

```python
# orchestrator/store/models.py — dentro de ClaudeSession
task_id: Mapped[str] = mapped_column(
    ForeignKey("tasks.id", ondelete="RESTRICT"), nullable=False
)
```

Importante: deixar **antes** dos campos opcionais; o NOT NULL será garantido pela migration.

- [ ] **Step 5: Migration `0003`**

```python
# alembic/versions/0003_tasks_and_session_task_link.py
"""tasks + session.task_id

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-09
"""
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "project_id", sa.String(32),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("state", sa.String(32), nullable=False, server_default="idea"),
        sa.Column("template", sa.String(64), nullable=True),
        sa.Column("permission_profile", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    with op.batch_alter_table("sessions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "task_id", sa.String(32),
                sa.ForeignKey("tasks.id", ondelete="RESTRICT"),
                nullable=True,
            )
        )

    # Pré-clean: remove sessions órfãs (worktree deletada)
    op.execute(
        "DELETE FROM sessions "
        "WHERE worktree_id NOT IN (SELECT id FROM worktrees)"
    )

    # Backfill: pra cada session, cria task implícita
    conn = op.get_bind()
    sessions = conn.execute(sa.text(
        "SELECT s.id, s.worktree_id, w.project_id, w.branch "
        "FROM sessions s JOIN worktrees w ON s.worktree_id = w.id"
    )).fetchall()
    for sess in sessions:
        task_id = uuid4().hex
        now = datetime.now(UTC)
        conn.execute(sa.text(
            "INSERT INTO tasks "
            "(id, project_id, title, description, state, created_at, updated_at) "
            "VALUES (:id, :pid, :title, '', 'in_progress', :now, :now)"
        ), {
            "id": task_id, "pid": sess.project_id,
            "title": f"Quick session · {sess.branch or '(detached)'}",
            "now": now,
        })
        conn.execute(sa.text(
            "UPDATE sessions SET task_id = :tid WHERE id = :sid"
        ), {"tid": task_id, "sid": sess.id})

    with op.batch_alter_table("sessions") as batch_op:
        batch_op.alter_column("task_id", nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.drop_column("task_id")
    op.drop_table("tasks")
```

- [ ] **Step 6: GREEN no roundtrip**

Run: `uv run pytest tests/integration/test_migration_0003_roundtrip.py -v`
Expected: 1 passed.

- [ ] **Step 7: Confirmar bootstrap em DEV**

```bash
rm -f jarvis.db
uv run python -c "
import asyncio
from orchestrator.store.database import Database
async def main():
    db = Database('sqlite+aiosqlite:///./jarvis.db')
    await db.bootstrap()
asyncio.run(main())
"
sqlite3 jarvis.db ".schema tasks" | head -5
sqlite3 jarvis.db "PRAGMA table_info(sessions);" | grep task_id
rm jarvis.db
```

Esperado: schema da tabela `tasks` aparece; coluna `task_id` em sessions.

- [ ] **Step 8: Code review subagent**

Prompt: "Review the staged diff for orchestrator/store/models.py + alembic/versions/0003_tasks_and_session_task_link.py + tests/integration/test_migration_0003_roundtrip.py. Verify: (1) FK ondelete=RESTRICT in both Python model and migration; (2) backfill skips orphan sessions before NOT NULL alter; (3) downgrade is symmetric; (4) Task model has all spec §3.2 columns with correct nullability."

- [ ] **Step 9: Commit**

```bash
git add orchestrator/store/models.py alembic/versions/0003_tasks_and_session_task_link.py tests/integration/test_migration_0003_roundtrip.py
git commit -m "$(cat <<'EOF'
feat(F4.a): tabela tasks + sessions.task_id NOT NULL via migration 0003

- Task model com FK projects.id ON DELETE RESTRICT
- ClaudeSession.task_id FK NOT NULL ON DELETE RESTRICT
- Migration aditiva: cria tasks, adiciona task_id NULLABLE, purga
  sessions órfãs, backfilla com task implícita "Quick session · …",
  depois NOT NULL
- Roundtrip test (0002 ↔ 0003) passa
EOF
)"
```

---

## Task 2 — F4.b: `core/tasks.py` + state machine + `delete_project` blocking

**Objetivo:** implementar domínio de tasks (CRUD + transições server-validated) + `delete_project` que bloqueia se há tasks.

**Files:**
- Create: `orchestrator/core/tasks.py`
- Modify: `orchestrator/core/projects.py`
- Create: `tests/unit/test_task_state_machine.py`
- Create: `tests/unit/test_task_crud.py`
- Create: `tests/unit/test_task_title_validation.py`
- Create: `tests/unit/test_project_delete_blocked.py`

- [ ] **Step 1: Test state machine (puro)**

```python
# tests/unit/test_task_state_machine.py
import pytest

from orchestrator.core.tasks import is_valid_transition

VALID = {
    ("idea", "ready"), ("idea", "discarded"),
    ("ready", "idea"), ("ready", "in_progress"), ("ready", "discarded"),
    ("in_progress", "review"), ("in_progress", "discarded"),
    ("review", "in_progress"), ("review", "done"), ("review", "discarded"),
    ("discarded", "idea"),
}
ALL_STATES = ["idea", "ready", "in_progress", "review", "done", "discarded"]


@pytest.mark.parametrize("frm,to", sorted(VALID))
def test_valid_transitions(frm: str, to: str) -> None:
    assert is_valid_transition(frm, to) is True


def test_same_state_is_valid_idempotent() -> None:
    for s in ALL_STATES:
        assert is_valid_transition(s, s) is True


@pytest.mark.parametrize(
    "frm,to",
    [(f, t) for f in ALL_STATES for t in ALL_STATES
     if (f, t) not in VALID and f != t],
)
def test_invalid_transitions(frm: str, to: str) -> None:
    assert is_valid_transition(frm, to) is False
```

- [ ] **Step 2: RED state machine**

Run: `uv run pytest tests/unit/test_task_state_machine.py -v`
Expected: ImportError em `orchestrator.core.tasks`.

- [ ] **Step 3: Esqueleto `core/tasks.py` com state machine**

```python
# orchestrator/core/tasks.py
"""Task domain: CRUD + state machine + lifecycle policies."""
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.store.models import Project, Task

_VALID_TRANSITIONS: frozenset[tuple[str, str]] = frozenset({
    ("idea", "ready"), ("idea", "discarded"),
    ("ready", "idea"), ("ready", "in_progress"), ("ready", "discarded"),
    ("in_progress", "review"), ("in_progress", "discarded"),
    ("review", "in_progress"), ("review", "done"), ("review", "discarded"),
    ("discarded", "idea"),
})


def is_valid_transition(frm: str, to: str) -> bool:
    if frm == to:
        return True
    return (frm, to) in _VALID_TRANSITIONS


class TaskNotFoundError(Exception):
    pass


class InvalidTransitionError(Exception):
    pass


class TaskAlreadyHasActiveSessionError(Exception):
    pass


class TaskInTerminalStateError(Exception):
    pass


class InvalidTaskTitleError(Exception):
    pass


class ProjectNotFoundForTaskError(Exception):
    pass
```

- [ ] **Step 4: GREEN state machine**

Run: `uv run pytest tests/unit/test_task_state_machine.py -v`
Expected: ~30 passed (cross-product valid + invalid + idempotent).

- [ ] **Step 5: Test CRUD**

```python
# tests/unit/test_task_crud.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.core.projects import create_project
from orchestrator.core.tasks import (
    TaskNotFoundError, create_task, get_task, list_tasks, update_task,
)
from orchestrator.store.database import Database


@pytest.fixture
async def db_session(tmp_path):
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'crud.db'}")
    await db.bootstrap()
    async with db.session() as s:
        yield s


async def _seed_project(s: AsyncSession, tmp_path) -> str:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    p = await create_project(s, "proj", str(repo))
    return p.id


async def test_create_task_with_title_only(db_session, tmp_path) -> None:
    pid = await _seed_project(db_session, tmp_path)
    t = await create_task(db_session, project_id=pid, title="Hello")
    assert t.id and t.title == "Hello" and t.description == ""
    assert t.state == "idea" and t.template is None


async def test_list_tasks_no_filter(db_session, tmp_path) -> None:
    pid = await _seed_project(db_session, tmp_path)
    await create_task(db_session, project_id=pid, title="A")
    await create_task(db_session, project_id=pid, title="B")
    rows = await list_tasks(db_session)
    assert {t.title for t in rows} == {"A", "B"}


async def test_list_tasks_filter_project_ids(db_session, tmp_path) -> None:
    pid_a = await _seed_project(db_session, tmp_path)
    repo_b = tmp_path / "repoB"
    repo_b.mkdir()
    (repo_b / ".git").mkdir()
    pb = await create_project(db_session, "B", str(repo_b))
    await create_task(db_session, project_id=pid_a, title="A1")
    await create_task(db_session, project_id=pb.id, title="B1")
    rows = await list_tasks(db_session, project_ids=[pid_a])
    assert [t.title for t in rows] == ["A1"]


async def test_get_task_not_found_raises(db_session) -> None:
    with pytest.raises(TaskNotFoundError):
        await get_task(db_session, "nonexistent")


async def test_update_task_title(db_session, tmp_path) -> None:
    pid = await _seed_project(db_session, tmp_path)
    t = await create_task(db_session, project_id=pid, title="A")
    new, prev_state = await update_task(db_session, t.id, title="A2")
    assert new.title == "A2" and prev_state is None


async def test_update_task_state_returns_previous(db_session, tmp_path) -> None:
    pid = await _seed_project(db_session, tmp_path)
    t = await create_task(db_session, project_id=pid, title="X")
    new, prev_state = await update_task(db_session, t.id, state="ready")
    assert new.state == "ready" and prev_state == "idea"


async def test_update_task_same_state_is_noop(db_session, tmp_path) -> None:
    pid = await _seed_project(db_session, tmp_path)
    t = await create_task(db_session, project_id=pid, title="X")
    new, prev_state = await update_task(db_session, t.id, state="idea")
    assert new.state == "idea" and prev_state is None
```

- [ ] **Step 6: RED CRUD**

Run: `uv run pytest tests/unit/test_task_crud.py -v`
Expected: ImportError em `create_task`/`list_tasks`.

- [ ] **Step 7: Implementar CRUD em `core/tasks.py`**

Append:

```python
async def create_task(
    db: AsyncSession,
    *,
    project_id: str,
    title: str,
    description: str = "",
) -> Task:
    if not title or not title.strip():
        raise InvalidTaskTitleError("title cannot be empty or whitespace-only")
    project = await db.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundForTaskError(f"project not found: {project_id}")
    row = Task(project_id=project_id, title=title, description=description)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def list_tasks(
    db: AsyncSession,
    *,
    project_ids: Sequence[str] | None = None,
) -> Sequence[Task]:
    stmt = select(Task)
    if project_ids:
        stmt = stmt.where(Task.project_id.in_(project_ids))
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_task(db: AsyncSession, task_id: str) -> Task:
    row = await db.get(Task, task_id)
    if row is None:
        raise TaskNotFoundError(f"task not found: {task_id}")
    return row


async def update_task(
    db: AsyncSession,
    task_id: str,
    *,
    title: str | None = None,
    description: str | None = None,
    state: str | None = None,
) -> tuple[Task, str | None]:
    row = await get_task(db, task_id)
    await db.refresh(row)
    previous_state: str | None = None

    if title is not None:
        if not title.strip():
            raise InvalidTaskTitleError("title cannot be empty")
        row.title = title
    if description is not None:
        row.description = description
    if state is not None:
        if not is_valid_transition(row.state, state):
            raise InvalidTransitionError(
                f"invalid transition: {row.state} → {state}"
            )
        if state != row.state:
            previous_state = row.state
            row.state = state

    row.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(row)
    return row, previous_state
```

- [ ] **Step 8: GREEN CRUD**

Run: `uv run pytest tests/unit/test_task_crud.py -v`
Expected: 7 passed.

- [ ] **Step 9: Test title validation isolado**

```python
# tests/unit/test_task_title_validation.py
import pytest

from orchestrator.core.tasks import (
    InvalidTaskTitleError, create_task, update_task,
)


@pytest.mark.parametrize("bad", ["", "   ", "\t\n  "])
async def test_create_task_rejects_blank_title(db_session, tmp_path, bad: str) -> None:
    from orchestrator.core.projects import create_project
    repo = tmp_path / "r"; repo.mkdir(); (repo / ".git").mkdir()
    p = await create_project(db_session, "p", str(repo))
    with pytest.raises(InvalidTaskTitleError):
        await create_task(db_session, project_id=p.id, title=bad)


async def test_update_task_rejects_blank_title(db_session, tmp_path) -> None:
    from orchestrator.core.projects import create_project
    repo = tmp_path / "r"; repo.mkdir(); (repo / ".git").mkdir()
    p = await create_project(db_session, "p", str(repo))
    t = await create_task(db_session, project_id=p.id, title="OK")
    with pytest.raises(InvalidTaskTitleError):
        await update_task(db_session, t.id, title="   ")
```

Reutiliza fixture `db_session` do `test_task_crud.py` — extrair pra `tests/unit/conftest.py` se necessário (provavelmente sim).

- [ ] **Step 10: Extrair fixture `db_session` pra `tests/unit/conftest.py`**

```python
# tests/unit/conftest.py — append (criar se não existir)
import pytest

from orchestrator.store.database import Database


@pytest.fixture
async def db_session(tmp_path):
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'unit.db'}")
    await db.bootstrap()
    async with db.session() as s:
        yield s
```

Remover fixture local de `test_task_crud.py`.

- [ ] **Step 11: GREEN title validation**

Run: `uv run pytest tests/unit/test_task_title_validation.py tests/unit/test_task_crud.py -v`
Expected: todos verdes.

- [ ] **Step 12: Test `delete_project` blocking**

```python
# tests/unit/test_project_delete_blocked.py
import pytest

from orchestrator.core.projects import (
    ProjectHasTasksError, create_project, delete_project,
)
from orchestrator.core.tasks import create_task


async def test_delete_project_with_tasks_raises(db_session, tmp_path) -> None:
    repo = tmp_path / "r"; repo.mkdir(); (repo / ".git").mkdir()
    p = await create_project(db_session, "p", str(repo))
    await create_task(db_session, project_id=p.id, title="T")
    with pytest.raises(ProjectHasTasksError):
        await delete_project(db_session, p.id)


async def test_delete_project_without_tasks_ok(db_session, tmp_path) -> None:
    repo = tmp_path / "r"; repo.mkdir(); (repo / ".git").mkdir()
    p = await create_project(db_session, "p", str(repo))
    await delete_project(db_session, p.id)
```

- [ ] **Step 13: Implementar guard em `core/projects.py`**

```python
# orchestrator/core/projects.py — add new exception + modify delete_project
class ProjectHasTasksError(Exception):
    pass


async def delete_project(session: AsyncSession, project_id: str) -> None:
    project = await session.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError(f"project not found: {project_id}")
    # Local import: evita ciclo (core.tasks importa core.projects nunca?
    # Hoje não, mas seguramos com import local pra garantir).
    from orchestrator.store.models import Task
    from sqlalchemy import select, func
    count = (await session.execute(
        select(func.count()).select_from(Task).where(Task.project_id == project_id)
    )).scalar_one()
    if count > 0:
        raise ProjectHasTasksError(
            f"project has {count} task(s); discard them before deleting"
        )
    await session.delete(project)
    await session.commit()
```

- [ ] **Step 14: GREEN delete_project**

Run: `uv run pytest tests/unit/test_project_delete_blocked.py -v`
Expected: 2 passed.

- [ ] **Step 15: Coverage check de `core/tasks` + `core/projects`**

Run:
```bash
uv run pytest tests/unit/test_task_state_machine.py tests/unit/test_task_crud.py tests/unit/test_task_title_validation.py tests/unit/test_project_delete_blocked.py \
  --cov=orchestrator.core.tasks --cov=orchestrator.core.projects --cov-report=term-missing
```
Expected: 100% em `core.tasks` e `core.projects` (linhas alteradas).

- [ ] **Step 16: Code review subagent**

Prompt: "Review staged diff: orchestrator/core/tasks.py (NEW), orchestrator/core/projects.py (delete_project guard), tests/unit/test_task_state_machine.py + test_task_crud.py + test_task_title_validation.py + test_project_delete_blocked.py + tests/unit/conftest.py. Check: (1) is_valid_transition matches spec §3.3 table exactly; (2) update_task returns (row, previous_state) only when state actually changed; (3) ProjectHasTasksError message is en-US (per spec decision #20); (4) no SQL string concat (use ORM); (5) title validation rejects whitespace-only."

- [ ] **Step 17: Commit**

```bash
git add orchestrator/core/tasks.py orchestrator/core/projects.py tests/unit/test_task_state_machine.py tests/unit/test_task_crud.py tests/unit/test_task_title_validation.py tests/unit/test_project_delete_blocked.py tests/unit/conftest.py
git commit -m "$(cat <<'EOF'
feat(F4.b): core/tasks (state machine + CRUD) + delete_project blocking

- is_valid_transition pure function (5 valid + idempotent same-state)
- create_task / list_tasks / get_task / update_task com validação
  server-side de title e transição
- delete_project levanta ProjectHasTasksError quando há tasks
- 100% coverage em core.tasks + core.projects (paths novos)
EOF
)"
```

---

## Task 3 — F4.c: `core/sessions.py` ajustes (auto-transition + 1-active-lock)

**Objetivo:** `start_session` ganha kwarg `task_id` obrigatório, auto-transiciona task pra `in_progress`, e bloqueia se task já tem session ativa.

**Files:**
- Modify: `orchestrator/core/sessions.py`
- Create: `tests/unit/test_task_auto_transition.py`
- Create: `tests/unit/test_session_per_task_lock.py`
- Create: `tests/unit/test_quick_session_creates_task.py`

- [ ] **Step 1: Test auto-transition**

```python
# tests/unit/test_task_auto_transition.py
import pytest

from orchestrator.core.projects import create_project
from orchestrator.core.sessions import (
    TaskInTerminalStateError, start_session,
)
from orchestrator.core.tasks import create_task, update_task
from tests.unit.test_session_token_lifecycle import _seed_worktree  # ou inlinar — ver PFC-3
from orchestrator.sandbox.null import NullSessionRuntime


@pytest.fixture
async def setup(db_session, tmp_path):
    repo = tmp_path / "r"; repo.mkdir(); (repo / ".git").mkdir()
    p = await create_project(db_session, "p", str(repo))
    w = await create_worktree(db_session, p.id, str(repo), "main")
    runtime = NullSessionRuntime()
    return db_session, runtime, p, w


@pytest.mark.parametrize("initial_state", ["idea", "ready", "review"])
async def test_start_session_auto_transitions_to_in_progress(setup, initial_state):
    db, runtime, p, w = setup
    t = await create_task(db, project_id=p.id, title="T")
    if initial_state != "idea":
        if initial_state == "review":
            await update_task(db, t.id, state="ready")
            await update_task(db, t.id, state="in_progress")
            await update_task(db, t.id, state="review")
        else:
            await update_task(db, t.id, state=initial_state)
    await start_session(db, runtime, task_id=t.id, worktree_id=w.id)
    refreshed = await db.get(type(t), t.id)
    await db.refresh(refreshed)
    assert refreshed.state == "in_progress"


async def test_start_session_in_progress_is_noop(setup):
    db, runtime, p, w = setup
    t = await create_task(db, project_id=p.id, title="T")
    await update_task(db, t.id, state="ready")
    await update_task(db, t.id, state="in_progress")
    await start_session(db, runtime, task_id=t.id, worktree_id=w.id)
    await db.refresh(t)
    assert t.state == "in_progress"


@pytest.mark.parametrize("terminal_state", ["done", "discarded"])
async def test_start_session_in_terminal_state_raises(setup, terminal_state):
    db, runtime, p, w = setup
    t = await create_task(db, project_id=p.id, title="T")
    # Drive task to terminal
    if terminal_state == "done":
        await update_task(db, t.id, state="ready")
        await update_task(db, t.id, state="in_progress")
        await update_task(db, t.id, state="review")
        await update_task(db, t.id, state="done")
    else:
        await update_task(db, t.id, state="discarded")
    with pytest.raises(TaskInTerminalStateError):
        await start_session(db, runtime, task_id=t.id, worktree_id=w.id)
```

(Esse teste assume `core.worktrees.create_worktree`. Se a função não existir nesse formato no F1, ajustar para o seed correto via models direto.)

- [ ] **Step 2: RED auto-transition**

Run: `uv run pytest tests/unit/test_task_auto_transition.py -v`
Expected: erro porque `start_session` ainda não aceita `task_id` ou `TaskInTerminalStateError` não existe.

- [ ] **Step 3: Modificar `core/sessions.py`**

```python
# Add no topo:
from sqlalchemy import select, func
from orchestrator.core.tasks import (
    TaskAlreadyHasActiveSessionError, TaskInTerminalStateError,
    TaskNotFoundError, get_task,
)

# Modify start_session:
async def start_session(
    session: AsyncSession,
    runtime: SessionRuntime,
    *,
    task_id: str,
    worktree_id: str,
    token_registry: TokenRegistry | None = None,
    base_url: str | None = None,
) -> ClaudeSession:
    task = await get_task(session, task_id)
    await session.refresh(task)
    if task.state in ("done", "discarded"):
        raise TaskInTerminalStateError(
            f"cannot start session: task is in terminal state '{task.state}'"
        )

    active_count = (await session.execute(
        select(func.count()).select_from(ClaudeSession).where(
            ClaudeSession.task_id == task_id,
            ClaudeSession.status.notin_([SessionStatus.DONE, SessionStatus.ERROR]),
        )
    )).scalar_one()
    if active_count > 0:
        raise TaskAlreadyHasActiveSessionError(
            "task already has active session"
        )

    worktree = await session.get(Worktree, worktree_id)
    if worktree is None:
        raise WorktreeNotFoundError(f"worktree not found: {worktree_id}")

    # Auto-transition (idea/ready/review → in_progress)
    if task.state in ("idea", "ready", "review"):
        task.state = "in_progress"
        from datetime import UTC, datetime
        task.updated_at = datetime.now(UTC)

    token = generate_token() if token_registry is not None else None
    handle = await runtime.spawn(Path(worktree.path), token=token, base_url=base_url)
    row = ClaudeSession(
        worktree_id=worktree_id,
        task_id=task_id,
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
```

- [ ] **Step 4: GREEN auto-transition**

Run: `uv run pytest tests/unit/test_task_auto_transition.py -v`
Expected: 5 passed (3 paramétricos + 1 noop + 2 terminal).

- [ ] **Step 5: Test 1-active-lock (sequencial)**

```python
# tests/unit/test_session_per_task_lock.py
import pytest

from orchestrator.core.projects import create_project
from orchestrator.core.sessions import (
    TaskAlreadyHasActiveSessionError, start_session, stop_session,
)
from orchestrator.core.tasks import create_task
from tests.unit.test_session_token_lifecycle import _seed_worktree  # ou inlinar — ver PFC-3
from orchestrator.sandbox.null import NullSessionRuntime


async def test_second_active_session_raises(db_session, tmp_path):
    repo = tmp_path / "r"; repo.mkdir(); (repo / ".git").mkdir()
    p = await create_project(db_session, "p", str(repo))
    w = await create_worktree(db_session, p.id, str(repo), "main")
    t = await create_task(db_session, project_id=p.id, title="T")
    runtime = NullSessionRuntime()
    await start_session(db_session, runtime, task_id=t.id, worktree_id=w.id)
    with pytest.raises(TaskAlreadyHasActiveSessionError):
        await start_session(db_session, runtime, task_id=t.id, worktree_id=w.id)


async def test_after_stop_can_start_again(db_session, tmp_path):
    repo = tmp_path / "r"; repo.mkdir(); (repo / ".git").mkdir()
    p = await create_project(db_session, "p", str(repo))
    w = await create_worktree(db_session, p.id, str(repo), "main")
    t = await create_task(db_session, project_id=p.id, title="T")
    runtime = NullSessionRuntime()
    s1 = await start_session(db_session, runtime, task_id=t.id, worktree_id=w.id)
    await stop_session(db_session, runtime, s1.id)
    # Should not raise
    await start_session(db_session, runtime, task_id=t.id, worktree_id=w.id)
```

- [ ] **Step 6: GREEN 1-active-lock**

Run: `uv run pytest tests/unit/test_session_per_task_lock.py -v`
Expected: 2 passed.

- [ ] **Step 7: Test `ensure_task_for_quick_session`**

```python
# tests/unit/test_quick_session_creates_task.py
from orchestrator.core.projects import create_project
from orchestrator.core.tasks import ensure_task_for_quick_session
from tests.unit.test_session_token_lifecycle import _seed_worktree  # ou inlinar — ver PFC-3


async def test_ensure_task_for_quick_session_creates_in_progress(db_session, tmp_path):
    repo = tmp_path / "r"; repo.mkdir(); (repo / ".git").mkdir()
    p = await create_project(db_session, "p", str(repo))
    w = await create_worktree(db_session, p.id, str(repo), "feature/foo")
    task = await ensure_task_for_quick_session(db_session, worktree_id=w.id)
    assert task.title == "Quick session · feature/foo"
    assert task.state == "in_progress"
    assert task.project_id == p.id


async def test_ensure_task_for_quick_session_detached(db_session, tmp_path):
    repo = tmp_path / "r"; repo.mkdir(); (repo / ".git").mkdir()
    p = await create_project(db_session, "p", str(repo))
    w = await create_worktree(db_session, p.id, str(repo), None)
    task = await ensure_task_for_quick_session(db_session, worktree_id=w.id)
    assert task.title == "Quick session · (detached)"
```

- [ ] **Step 8: Implementar `ensure_task_for_quick_session`**

Append em `core/tasks.py`:

```python
async def ensure_task_for_quick_session(
    db: AsyncSession,
    *,
    worktree_id: str,
) -> Task:
    """Create an implicit task for a quick (worktree-driven) session."""
    from orchestrator.store.models import Worktree
    worktree = await db.get(Worktree, worktree_id)
    if worktree is None:
        raise ProjectNotFoundForTaskError(f"worktree not found: {worktree_id}")
    branch = worktree.branch or "(detached)"
    title = f"Quick session · {branch}"
    row = Task(
        project_id=worktree.project_id,
        title=title,
        description="",
        state="in_progress",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row
```

- [ ] **Step 9: GREEN ensure_task_for_quick_session**

Run: `uv run pytest tests/unit/test_quick_session_creates_task.py -v`
Expected: 2 passed.

- [ ] **Step 10: Coverage check `core.sessions` + `core.tasks`**

```bash
uv run pytest tests/unit/test_task_auto_transition.py tests/unit/test_session_per_task_lock.py tests/unit/test_quick_session_creates_task.py \
  --cov=orchestrator.core.sessions --cov=orchestrator.core.tasks --cov-report=term-missing
```
Expected: 100% em ambos.

- [ ] **Step 11: Re-rodar todos os unit tests pra garantir não-regressão**

```bash
uv run pytest tests/unit -q
```
Expected: tudo verde, incluindo os F2 tests (que dependem de `start_session`).

⚠️ **Se falhar**: F2 tests podem precisar ajuste pra passar `task_id`. Crie task de seed nos fixtures dos testes F2 que chamam `start_session`. Ajustar `tests/unit/test_session_token_lifecycle.py` em particular.

- [ ] **Step 12: Code review subagent**

Prompt: "Review staged: orchestrator/core/sessions.py (start_session signature change with task_id kwarg + auto-transition + active lock) + tests/unit/test_task_auto_transition.py + test_session_per_task_lock.py + test_quick_session_creates_task.py + ensure_task_for_quick_session in core/tasks.py. Check: (1) auto-transition only fires for {idea, ready, review}; (2) active-lock count uses notin_(DONE, ERROR) — not status='executing'; (3) ensure_task_for_quick_session uses worktree.project_id correctly; (4) F2 tests still pass (no regression)."

- [ ] **Step 13: Commit**

```bash
git add orchestrator/core/sessions.py orchestrator/core/tasks.py tests/unit/test_task_auto_transition.py tests/unit/test_session_per_task_lock.py tests/unit/test_quick_session_creates_task.py
git commit -m "$(cat <<'EOF'
feat(F4.c): start_session com task_id + auto-transition + 1-active-lock

- start_session(*, task_id, worktree_id, …) signature obrigatória
- Auto-promove task de {idea,ready,review} → in_progress
- 409-equivalente (TaskAlreadyHasActiveSessionError) na 2ª session ativa
- 409-equivalente (TaskInTerminalStateError) em done/discarded
- ensure_task_for_quick_session cria task implícita do worktree
EOF
)"
```

---

## Task 4 — F4.d: API routes `/api/tasks/*` + `POST /api/tasks/{id}/sessions`

**Objetivo:** expor o domínio via REST. POST/GET-list/GET-one/PATCH + endpoint de criação de session via task.

**Files:**
- Create: `orchestrator/api/tasks.py`
- Modify: `orchestrator/main.py`
- Create: `tests/integration/test_tasks_route.py`
- Create: `tests/integration/test_task_session_route.py`
- Create: `tests/integration/test_tasks_filter_project_ids.py`
- Create: `tests/integration/test_project_delete_409.py`

- [ ] **Step 1: Test POST /api/tasks (sucesso + 422)**

```python
# tests/integration/test_tasks_route.py
import pytest
from httpx import AsyncClient


async def test_post_task_201(client: AsyncClient, project_id: str) -> None:
    r = await client.post("/api/tasks", json={
        "project_id": project_id, "title": "Adicionar dark mode",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "Adicionar dark mode"
    assert body["state"] == "idea"


async def test_post_task_422_blank_title(client: AsyncClient, project_id: str) -> None:
    r = await client.post("/api/tasks", json={
        "project_id": project_id, "title": "   ",
    })
    assert r.status_code == 422


async def test_post_task_422_bad_project(client: AsyncClient) -> None:
    r = await client.post("/api/tasks", json={
        "project_id": "nonexistent", "title": "X",
    })
    assert r.status_code == 422


async def test_get_tasks_empty_list(client: AsyncClient) -> None:
    r = await client.get("/api/tasks")
    assert r.status_code == 200 and r.json() == []


async def test_get_task_404(client: AsyncClient) -> None:
    r = await client.get("/api/tasks/nonexistent")
    assert r.status_code == 404


async def test_patch_task_state_valid(client: AsyncClient, project_id: str) -> None:
    created = (await client.post("/api/tasks", json={
        "project_id": project_id, "title": "T",
    })).json()
    r = await client.patch(f"/api/tasks/{created['id']}", json={"state": "ready"})
    assert r.status_code == 200 and r.json()["state"] == "ready"


async def test_patch_task_state_invalid(client: AsyncClient, project_id: str) -> None:
    created = (await client.post("/api/tasks", json={
        "project_id": project_id, "title": "T",
    })).json()
    # idea → done não é transição válida
    r = await client.patch(f"/api/tasks/{created['id']}", json={"state": "done"})
    assert r.status_code == 422


async def test_patch_task_state_idempotent(client: AsyncClient, project_id: str) -> None:
    created = (await client.post("/api/tasks", json={
        "project_id": project_id, "title": "T",
    })).json()
    r = await client.patch(f"/api/tasks/{created['id']}", json={"state": "idea"})
    assert r.status_code == 200 and r.json()["state"] == "idea"


async def test_patch_task_resurrect_discarded_to_idea(
    client: AsyncClient, project_id: str
) -> None:
    created = (await client.post("/api/tasks", json={
        "project_id": project_id, "title": "T",
    })).json()
    await client.patch(f"/api/tasks/{created['id']}", json={"state": "discarded"})
    r = await client.patch(f"/api/tasks/{created['id']}", json={"state": "idea"})
    assert r.status_code == 200 and r.json()["state"] == "idea"
```

(Fixtures `client` e `project_id` extraídas em `tests/integration/conftest.py`. Se ainda não existem, criar com base nos padrões F1.)

- [ ] **Step 2: RED**

Run: `uv run pytest tests/integration/test_tasks_route.py -v`
Expected: 404 ou ImportError (rota não existe).

- [ ] **Step 3: Implementar `orchestrator/api/tasks.py`**

```python
# orchestrator/api/tasks.py
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.api._deps import get_db_session
from orchestrator.core.sessions import (
    TaskAlreadyHasActiveSessionError, WorktreeNotFoundError,
    start_session,
)
from orchestrator.core.tasks import (
    InvalidTaskTitleError, InvalidTransitionError,
    ProjectNotFoundForTaskError, TaskInTerminalStateError,
    TaskNotFoundError, create_task, get_task, list_tasks, update_task,
)
from orchestrator.store.models import ClaudeSession


class TaskCreatePayload(BaseModel):
    project_id: str
    title: str
    description: str = ""


class TaskPatchPayload(BaseModel):
    title: str | None = None
    description: str | None = None
    state: str | None = None


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
    active_session_id: str | None

    model_config = {"from_attributes": True}


class TaskSessionCreatePayload(BaseModel):
    worktree_id: str


router = APIRouter(prefix="/tasks", tags=["tasks"])


async def _build_task_read(db: AsyncSession, task) -> TaskRead:
    active = (await db.execute(
        select(ClaudeSession.id).where(
            ClaudeSession.task_id == task.id,
            ClaudeSession.status.notin_(["done", "error"]),
        ).limit(1)
    )).scalar_one_or_none()
    payload = TaskRead.model_validate(task)
    return payload.model_copy(update={"active_session_id": active})


@router.post("", status_code=201, response_model=TaskRead)
async def post_task(
    payload: TaskCreatePayload,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TaskRead:
    try:
        row = await create_task(
            db,
            project_id=payload.project_id,
            title=payload.title,
            description=payload.description,
        )
    except (InvalidTaskTitleError, ProjectNotFoundForTaskError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return await _build_task_read(db, row)


@router.get("", response_model=list[TaskRead])
async def get_tasks(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    project_ids: Annotated[str | None, Query()] = None,
) -> list[TaskRead]:
    ids = project_ids.split(",") if project_ids else None
    rows = await list_tasks(db, project_ids=ids)
    return [await _build_task_read(db, r) for r in rows]


@router.get("/{task_id}", response_model=TaskRead)
async def get_task_route(
    task_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TaskRead:
    try:
        row = await get_task(db, task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return await _build_task_read(db, row)


@router.patch("/{task_id}", response_model=TaskRead)
async def patch_task(
    task_id: str,
    payload: TaskPatchPayload,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TaskRead:
    try:
        row, _prev = await update_task(
            db, task_id,
            title=payload.title,
            description=payload.description,
            state=payload.state,
        )
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (InvalidTransitionError, InvalidTaskTitleError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return await _build_task_read(db, row)


@router.post("/{task_id}/sessions", status_code=201)
async def post_task_session(
    task_id: str,
    payload: TaskSessionCreatePayload,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    runtime = request.app.state.runtime
    registry = request.app.state.token_registry
    base_url = request.app.state.hook_base_url
    try:
        sess = await start_session(
            db, runtime,
            task_id=task_id,
            worktree_id=payload.worktree_id,
            token_registry=registry,
            base_url=base_url,
        )
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorktreeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (TaskAlreadyHasActiveSessionError, TaskInTerminalStateError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    from orchestrator.api.sessions import SessionRead
    return SessionRead.model_validate(sess)
```

- [ ] **Step 4: Registrar router em `main.py`**

```python
# orchestrator/main.py — em create_app:
from orchestrator.api.tasks import router as tasks_router
# …
if database is not None:
    …
    app.include_router(tasks_router, prefix="/api")
    …
```

- [ ] **Step 5: GREEN test_tasks_route**

Run: `uv run pytest tests/integration/test_tasks_route.py -v`
Expected: 9 passed.

- [ ] **Step 6: Test POST /api/tasks/{id}/sessions (409 paths)**

```python
# tests/integration/test_task_session_route.py
import pytest
from httpx import AsyncClient


async def test_post_task_session_201(
    client: AsyncClient, project_id: str, worktree_id: str
) -> None:
    t = (await client.post("/api/tasks", json={
        "project_id": project_id, "title": "T",
    })).json()
    r = await client.post(
        f"/api/tasks/{t['id']}/sessions",
        json={"worktree_id": worktree_id},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["task_id"] == t["id"]


async def test_post_task_session_409_double_start(
    client: AsyncClient, project_id: str, worktree_id: str
) -> None:
    t = (await client.post("/api/tasks", json={
        "project_id": project_id, "title": "T",
    })).json()
    await client.post(
        f"/api/tasks/{t['id']}/sessions",
        json={"worktree_id": worktree_id},
    )
    r = await client.post(
        f"/api/tasks/{t['id']}/sessions",
        json={"worktree_id": worktree_id},
    )
    assert r.status_code == 409


async def test_post_task_session_409_terminal_state(
    client: AsyncClient, project_id: str, worktree_id: str
) -> None:
    t = (await client.post("/api/tasks", json={
        "project_id": project_id, "title": "T",
    })).json()
    await client.patch(f"/api/tasks/{t['id']}", json={"state": "discarded"})
    r = await client.post(
        f"/api/tasks/{t['id']}/sessions",
        json={"worktree_id": worktree_id},
    )
    assert r.status_code == 409


async def test_post_task_session_404_task(
    client: AsyncClient, worktree_id: str
) -> None:
    r = await client.post(
        "/api/tasks/nonexistent/sessions",
        json={"worktree_id": worktree_id},
    )
    assert r.status_code == 404


async def test_post_task_session_auto_transitions_idea_to_in_progress(
    client: AsyncClient, project_id: str, worktree_id: str
) -> None:
    t = (await client.post("/api/tasks", json={
        "project_id": project_id, "title": "T",
    })).json()
    assert t["state"] == "idea"
    await client.post(
        f"/api/tasks/{t['id']}/sessions",
        json={"worktree_id": worktree_id},
    )
    r = await client.get(f"/api/tasks/{t['id']}")
    assert r.json()["state"] == "in_progress"
```

- [ ] **Step 7: GREEN test_task_session_route**

Run: `uv run pytest tests/integration/test_task_session_route.py -v`
Expected: 5 passed.

- [ ] **Step 8: Test filtro `?project_ids=`**

```python
# tests/integration/test_tasks_filter_project_ids.py
async def test_filter_returns_only_listed_projects(
    client: AsyncClient, two_projects
) -> None:
    pa, pb = two_projects
    await client.post("/api/tasks", json={"project_id": pa, "title": "A1"})
    await client.post("/api/tasks", json={"project_id": pb, "title": "B1"})
    r = await client.get(f"/api/tasks?project_ids={pa}")
    assert {t["title"] for t in r.json()} == {"A1"}
```

(Fixture `two_projects` pode ser inline ou compartilhada via conftest.)

- [ ] **Step 9: Test DELETE project com tasks → 409**

```python
# tests/integration/test_project_delete_409.py
async def test_delete_project_with_tasks_returns_409(
    client: AsyncClient, project_id: str
) -> None:
    await client.post("/api/tasks", json={"project_id": project_id, "title": "T"})
    r = await client.delete(f"/api/projects/{project_id}")
    assert r.status_code == 409
    assert "task" in r.json()["detail"].lower()
```

E modificar `orchestrator/api/projects.py` pra capturar `ProjectHasTasksError` → 409:

```python
# orchestrator/api/projects.py — dentro de delete_project_route
from orchestrator.core.projects import ProjectHasTasksError
…
try:
    await delete_project(session, project_id)
except ProjectNotFoundError as exc:
    raise HTTPException(status_code=404, detail=str(exc)) from exc
except ProjectHasTasksError as exc:
    raise HTTPException(status_code=409, detail=str(exc)) from exc
```

- [ ] **Step 10: GREEN filter + delete-409**

Run: `uv run pytest tests/integration/test_tasks_filter_project_ids.py tests/integration/test_project_delete_409.py -v`
Expected: ambos passam.

- [ ] **Step 11: Coverage check**

```bash
uv run pytest tests/integration/test_tasks_route.py tests/integration/test_task_session_route.py tests/integration/test_tasks_filter_project_ids.py tests/integration/test_project_delete_409.py \
  --cov=orchestrator.api.tasks --cov=orchestrator.api.projects --cov-report=term-missing
```
Expected: 100% em api.tasks e linhas alteradas em api.projects.

- [ ] **Step 12: Code review subagent**

Prompt: "Review staged: orchestrator/api/tasks.py (NEW), orchestrator/api/projects.py (delete_project route 409 handling), orchestrator/main.py (router registration), 4 integration test files. Verify: (1) all 5 spec §4.1 endpoints exist with correct status codes; (2) error mapping (404 for not found, 422 for validation/transition, 409 for conflict); (3) `?project_ids=a,b,c` parses CSV correctly; (4) `_build_task_read` derives `active_session_id` via single query (no N+1)."

- [ ] **Step 13: Commit**

```bash
git add orchestrator/api/tasks.py orchestrator/api/projects.py orchestrator/main.py tests/integration/test_tasks_route.py tests/integration/test_task_session_route.py tests/integration/test_tasks_filter_project_ids.py tests/integration/test_project_delete_409.py
git commit -m "$(cat <<'EOF'
feat(F4.d): API REST /api/tasks/* + POST /api/tasks/{id}/sessions

- POST/GET-list/GET-one/PATCH com 422/404 paths
- ?project_ids=a,b filtra cross-project
- POST /api/tasks/{id}/sessions com 404/409 paths
- DELETE project com tasks retorna 409 com mensagem clara
- TaskRead.active_session_id derivado server-side
EOF
)"
```

---

## Task 5 — F4.e: Quick session compat (`POST /api/sessions` cria task) + `SessionRead.task_id`

**Objetivo:** manter compat de F1 (`POST /api/sessions {worktree_id}`); agora cria task implícita silenciosamente. `SessionRead` ganha `task_id`.

**Files:**
- Modify: `orchestrator/api/sessions.py`
- Create: `tests/integration/test_quick_session_creates_task.py`

- [ ] **Step 1: Test compat**

```python
# tests/integration/test_quick_session_creates_task.py
async def test_quick_session_creates_implicit_task(
    client: AsyncClient, project_id: str, worktree_id: str
) -> None:
    r = await client.post("/api/sessions", json={"worktree_id": worktree_id})
    assert r.status_code == 201
    body = r.json()
    assert "task_id" in body and body["task_id"]
    # Task implícita visível no GET /api/tasks
    tasks = (await client.get("/api/tasks")).json()
    titles = [t["title"] for t in tasks]
    assert any(t.startswith("Quick session ·") for t in titles)
    # E está em in_progress
    implicit = next(t for t in tasks if t["title"].startswith("Quick session"))
    assert implicit["state"] == "in_progress"
```

- [ ] **Step 2: RED**

Run: `uv run pytest tests/integration/test_quick_session_creates_task.py -v`
Expected: KeyError em `task_id` (SessionRead ainda não tem).

- [ ] **Step 3: Modificar `api/sessions.py`**

```python
# orchestrator/api/sessions.py
class SessionRead(BaseModel):
    id: str
    task_id: str          # NOVO
    worktree_id: str
    status: str
    pid: int | None
    jail_id: str | None
    started_at: datetime
    ended_at: datetime | None

    model_config = {"from_attributes": True}


@router.post("", status_code=201, response_model=SessionRead)
async def post_session(
    payload: SessionCreatePayload,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    runtime: Annotated[SessionRuntime, Depends(resolve_runtime)],
) -> SessionRead:
    from orchestrator.core.tasks import ensure_task_for_quick_session
    registry = request.app.state.token_registry
    base_url = request.app.state.hook_base_url
    try:
        task = await ensure_task_for_quick_session(
            session, worktree_id=payload.worktree_id
        )
        row = await start_session(
            session, runtime,
            task_id=task.id,
            worktree_id=payload.worktree_id,
            token_registry=registry,
            base_url=base_url,
        )
    except WorktreeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SessionRead.model_validate(row)
```

- [ ] **Step 4: GREEN**

Run: `uv run pytest tests/integration/test_quick_session_creates_task.py -v`
Expected: passa.

- [ ] **Step 5: Re-rodar todos os integration tests**

```bash
uv run pytest tests/integration -q
```
Expected: tudo verde, incluindo F1 + F2 (que ainda usam `POST /api/sessions`).

⚠️ **Se F2 quebrar**: o lifecycle test pode não esperar `task_id` em SessionRead. Se isso falhar, adicionar `assert "task_id" in body` em vez de `assert body == {"id": …}`.

- [ ] **Step 6: Coverage**

```bash
uv run pytest tests/integration/test_quick_session_creates_task.py \
  --cov=orchestrator.api.sessions --cov-report=term-missing
```

- [ ] **Step 7: Code review**

Prompt: "Review orchestrator/api/sessions.py — verify SessionRead grew task_id without breaking F1/F2 callers. POST /api/sessions delegates to ensure_task_for_quick_session before start_session. Confirm error handling chain doesn't leak ProjectNotFoundForTaskError."

- [ ] **Step 8: Commit**

```bash
git add orchestrator/api/sessions.py tests/integration/test_quick_session_creates_task.py
git commit -m "$(cat <<'EOF'
feat(F4.e): POST /api/sessions cria task implícita; SessionRead.task_id

- ensure_task_for_quick_session é chamado antes de start_session
- task implícita "Quick session · <branch>" em in_progress
- SessionRead expõe task_id pra UI poder navegar pro card
- compat F1: contrato externo de POST /api/sessions inalterado salvo
  pelo campo novo task_id na resposta
EOF
)"
```

---

## Task 6 — F4.f: WS envelope `task_id` + factories `task.created/updated` + ADR-0014

**Objetivo:** estender `WsEvent` com `task_id` opcional; adicionar factories `task_created`/`task_updated`; atualizar `session_*` factories pra carregar `task_id`; broadcastar nos endpoints relevantes; criar ADR-0014.

**Files:**
- Modify: `orchestrator/events/envelope.py`
- Modify: `orchestrator/api/tasks.py` (broadcast em POST/PATCH/POST-sessions)
- Modify: `orchestrator/api/sessions.py` (broadcast em quick session)
- Modify: `orchestrator/hooks/router.py` (passa task_id em factories session_*)
- Modify: `orchestrator/core/sessions.py` (não precisa — broadcast fica no router)
- Create: `tests/unit/test_ws_envelope_tasks.py`
- Create: `docs/adr/0014-envelope-ws-task-id-opcional.md`

- [ ] **Step 1: Teste do envelope**

```python
# tests/unit/test_ws_envelope_tasks.py
from orchestrator.events.envelope import WsEvent


def test_task_created_factory() -> None:
    e = WsEvent.task_created(
        task_id="t1", project_id="p1", title="X", state="idea"
    )
    d = e.to_dict()
    assert d["type"] == "task.created"
    assert d["task_id"] == "t1"
    assert d["session_id"] == ""
    assert d["payload"] == {
        "project_id": "p1", "title": "X", "state": "idea",
    }


def test_task_updated_factory() -> None:
    e = WsEvent.task_updated(
        task_id="t1", project_id="p1", title="X",
        new_state="ready", previous_state="idea",
    )
    d = e.to_dict()
    assert d["type"] == "task.updated"
    assert d["task_id"] == "t1"
    assert d["payload"]["state"] == "ready"
    assert d["payload"]["previous_state"] == "idea"


def test_session_status_factory_carries_task_id() -> None:
    from orchestrator.core.sessions import SessionStatus
    e = WsEvent.session_status(
        session_id="s1", task_id="t1",
        new_status=SessionStatus.IDLE, previous_status=SessionStatus.EXECUTING,
    )
    d = e.to_dict()
    assert d["session_id"] == "s1"
    assert d["task_id"] == "t1"


def test_session_tool_use_factory_carries_task_id() -> None:
    e = WsEvent.session_tool_use(session_id="s1", task_id="t1", tool="Bash")
    assert e.to_dict()["task_id"] == "t1"


def test_session_stopped_factory_carries_task_id() -> None:
    e = WsEvent.session_stopped(session_id="s1", task_id="t1")
    assert e.to_dict()["task_id"] == "t1"
```

- [ ] **Step 2: RED**

Run: `uv run pytest tests/unit/test_ws_envelope_tasks.py -v`
Expected: AttributeError em `task_created` ou TypeError porque `session_status` não aceita `task_id`.

- [ ] **Step 3: Modificar `events/envelope.py`**

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
    task_id: str | None = None      # NOVO

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "payload": self.payload,
            "at": self.at,
        }

    @classmethod
    def session_status(
        cls, *, session_id: str, task_id: str,
        new_status, previous_status,
    ) -> "WsEvent":
        return cls(
            type="session.status",
            session_id=session_id,
            task_id=task_id,
            payload={"status": str(new_status), "previous": str(previous_status)},
        )

    @classmethod
    def session_tool_use(cls, *, session_id: str, task_id: str, tool: str) -> "WsEvent":
        return cls(
            type="session.tool_use",
            session_id=session_id, task_id=task_id,
            payload={"tool": tool},
        )

    @classmethod
    def session_stopped(cls, *, session_id: str, task_id: str) -> "WsEvent":
        return cls(
            type="session.stopped",
            session_id=session_id, task_id=task_id,
            payload={},
        )

    @classmethod
    def task_created(
        cls, *, task_id: str, project_id: str, title: str, state: str,
    ) -> "WsEvent":
        return cls(
            type="task.created",
            session_id="",
            task_id=task_id,
            payload={"project_id": project_id, "title": title, "state": state},
        )

    @classmethod
    def task_updated(
        cls, *, task_id: str, project_id: str, title: str,
        new_state: str, previous_state: str | None,
    ) -> "WsEvent":
        return cls(
            type="task.updated",
            session_id="",
            task_id=task_id,
            payload={
                "project_id": project_id, "title": title,
                "state": new_state, "previous_state": previous_state,
            },
        )
```

- [ ] **Step 4: GREEN envelope test**

Run: `uv run pytest tests/unit/test_ws_envelope_tasks.py -v`
Expected: 5 passed.

- [ ] **Step 5: Atualizar callers de `session_*` factories**

`orchestrator/hooks/router.py` agora precisa do `task_id`. Modificar `_resolve_or_404` pra também resolver task_id, ou buscar inline:

```python
# orchestrator/hooks/router.py — em hook_notification, hook_pretooluse, hook_stop
async def _resolve_session_and_task(
    db: AsyncSession, sid: str
) -> tuple[str, str]:
    from orchestrator.store.models import ClaudeSession
    row = await db.get(ClaudeSession, sid)
    if row is None:  # pragma: no cover
        raise HTTPException(status_code=404)
    return sid, row.task_id

# Onde antes:
#   await broadcaster.publish(WsEvent.session_status(session_id=sid, …))
# Agora:
#   _, tid = await _resolve_session_and_task(db, sid)
#   await broadcaster.publish(WsEvent.session_status(session_id=sid, task_id=tid, …))
```

(Aplicar pra os 3 endpoints de hooks.)

- [ ] **Step 6: Re-rodar F2 tests**

```bash
uv run pytest tests/unit/test_ws_envelope.py tests/integration/test_hooks_routes.py -v
```
Expected: tudo verde.

⚠️ Se F2 quebrar: ajustar tests do F2 que invocam `WsEvent.session_*` direto pra passar `task_id`. Em production code só F4 chama; mas tests podem passar literais.

- [ ] **Step 7: Adicionar broadcasts nas rotas de tasks**

`orchestrator/api/tasks.py` — após `create_task` retornar:

```python
broadcaster = request.app.state.ws_broadcaster
if broadcaster is not None:
    await broadcaster.publish(WsEvent.task_created(
        task_id=row.id, project_id=row.project_id,
        title=row.title, state=row.state,
    ))
```

(Adicionar `request: Request` no signature; importar `WsEvent`.)

Após `update_task`:

```python
if previous_state is not None:   # state realmente mudou
    if broadcaster is not None:
        await broadcaster.publish(WsEvent.task_updated(
            task_id=row.id, project_id=row.project_id,
            title=row.title, new_state=row.state,
            previous_state=previous_state,
        ))
```

Após `start_session` em `post_task_session`, broadcast `task.updated` se auto-transition mudou state. Para isso, comparar `task.state` antes e depois (pode persistir o `previous` no objeto retornado do core, ou re-fetch).

Mais simples: capturar antes de `start_session`:

```python
prev_task = await get_task(db, task_id)
prev_state = prev_task.state
sess = await start_session(...)
post_task = await get_task(db, task_id)
if post_task.state != prev_state:
    if broadcaster is not None:
        await broadcaster.publish(WsEvent.task_updated(
            task_id=task_id, project_id=post_task.project_id,
            title=post_task.title, new_state=post_task.state,
            previous_state=prev_state,
        ))
```

- [ ] **Step 8: Test integration: PATCH dispara `task.updated`**

```python
# tests/integration/test_tasks_route.py — append
async def test_patch_state_broadcasts_task_updated(
    client: AsyncClient, project_id: str, ws_collector
) -> None:
    t = (await client.post("/api/tasks", json={
        "project_id": project_id, "title": "T",
    })).json()
    await client.patch(f"/api/tasks/{t['id']}", json={"state": "ready"})
    events = await ws_collector.drain()
    types = [e["type"] for e in events]
    assert "task.created" in types
    assert "task.updated" in types
```

(Fixture `ws_collector` precisa existir — F2 já tem padrão similar; reutilizar/extrair pra `tests/integration/conftest.py`.)

- [ ] **Step 9: Test auto-transition broadcasts task.updated**

```python
# tests/integration/test_task_session_route.py — append
async def test_start_session_broadcasts_task_updated(
    client: AsyncClient, project_id: str, worktree_id: str, ws_collector
) -> None:
    t = (await client.post("/api/tasks", json={
        "project_id": project_id, "title": "T",
    })).json()
    await ws_collector.drain()  # zera buffer
    await client.post(
        f"/api/tasks/{t['id']}/sessions",
        json={"worktree_id": worktree_id},
    )
    events = await ws_collector.drain()
    updated = [e for e in events if e["type"] == "task.updated"]
    assert any(e["payload"]["state"] == "in_progress"
               and e["payload"]["previous_state"] == "idea"
               for e in updated)
```

- [ ] **Step 10: GREEN broadcast tests**

Run: `uv run pytest tests/integration/routes -k "broadcast or task_updated" -v`
Expected: passa.

- [ ] **Step 11: Criar ADR-0014**

```markdown
# ADR-0014: Envelope WS com `task_id` opcional (emenda aditiva ao ADR-0010)

- **Status:** Accepted
- **Data:** 2026-05-09
- **Decisores:** Marcos

## Contexto

F4 introduz eventos WS de Task (`task.created`, `task.updated`).
ADR-0010 fixou o envelope `{type, session_id, payload, at}` em F2.
Eventos de task não têm `session_id` natural, e a UI precisa
identificar qual Task atualizar quando recebe `session.status`.

## Decisão

Adiciona campo top-level **opcional** `task_id: str | None = None`
ao `WsEvent`. Backward-compatible:

- Eventos F2 (`session.status`/`tool_use`/`stopped`) ganham
  `task_id` preenchido a partir de `ClaudeSession.task_id`.
- Eventos F4 (`task.*`) preenchem `task_id` e deixam `session_id=""`.

Discriminador continua sendo `type`. Clientes antigos que ignoram
campos desconhecidos seguem funcionando (TypeScript permissive
parse no cliente, Python dataclass cria default `None`).

## Alternativas consideradas

1. **Top-level genérico `entity_id`** (rejeitada): quebra contrato
   F2; força mudar todo cliente.
2. **`session_id=""` sentinela sem `task_id`** (rejeitada): obriga
   UI a manter mapa `session_id → task_id` próprio; smell.
3. **Canal WS separado pra tasks** (`/ws/tasks`): contradiz ADR-0010
   "canal único".

## Consequências

**Positivas**
- UI invalida `tasks` cache via `task_id` em qualquer evento (session
  ou task) — sem mapa client-side.
- ADR-0010 contracts intactos; campo opcional novo é aditivo puro.

**Negativas**
- Mais um campo no payload. ~10 bytes por evento. Aceitável.

## Referências

- ADR-0010 (envelope WS canal único)
- Spec F4: `docs/superpowers/specs/2026-05-09-f4-backlog-kanban-design.md` §4.2
```

- [ ] **Step 12: Atualizar `docs/adr/README.md`**

```markdown
| [0014](0014-envelope-ws-task-id-opcional.md) | Envelope WS com `task_id` opcional (emenda aditiva ao ADR-0010) | Accepted | 2026-05-09 |
```

- [ ] **Step 13: Coverage**

```bash
uv run pytest tests/unit/test_ws_envelope_tasks.py tests/integration/routes -k "broadcast or task_updated or quick_session" \
  --cov=orchestrator.events.envelope --cov=orchestrator.api.tasks --cov-report=term-missing
```

- [ ] **Step 14: Code review**

Prompt: "Review staged: orchestrator/events/envelope.py (+ task_id field, + 2 factories, session_* factories accept task_id), orchestrator/hooks/router.py (resolves task_id from db), orchestrator/api/tasks.py (broadcasts task.created and task.updated; auto-transition broadcast), orchestrator/api/sessions.py (broadcasts task.created from quick session), ADR-0014. Verify: (1) WsEvent.to_dict includes task_id always; (2) session_* factories require task_id (kw-only); (3) task.updated.payload.previous_state is None when state didn't change (idempotent PATCH); (4) ADR-0014 honest about being purely additive."

- [ ] **Step 15: Commit**

```bash
git add orchestrator/events/envelope.py orchestrator/api/tasks.py orchestrator/api/sessions.py orchestrator/hooks/router.py tests/unit/test_ws_envelope_tasks.py tests/integration/test_tasks_route.py tests/integration/test_task_session_route.py docs/adr/0014-envelope-ws-task-id-opcional.md docs/adr/README.md
git commit -m "$(cat <<'EOF'
feat(F4.f): WS envelope ganha task_id; factories task.created/updated; ADR-0014

- WsEvent.task_id (str | None) top-level — emenda aditiva ao ADR-0010
- Factories WsEvent.task_created e WsEvent.task_updated
- session_* factories ganham kwarg task_id obrigatório
- POST/PATCH /api/tasks/* + auto-transition disparam broadcasts
- Hooks router resolve task_id da session pra preencher session_*
- ADR-0014 documenta a decisão; README.md indexado
EOF
)"
```

---

## Task 7 — F4.g: UI lib utilities (transitions, projectColor, kanbanFilters, errorMessages, api/events)

**Objetivo:** preparar todas as funções utilitárias do frontend antes dos componentes. TDD-friendly: tudo testável em isolation com Vitest.

**Files:**
- Create: `ui/src/lib/transitions.ts`
- Create: `ui/src/lib/projectColor.ts`
- Create: `ui/src/lib/kanbanFilters.ts`
- Create: `ui/src/lib/errorMessages.ts`
- Modify: `ui/src/lib/api.ts`
- Modify: `ui/src/lib/events.ts`
- Modify: `ui/src/lib/query-keys.ts`
- Tests: `ui/src/lib/transitions.test.ts`, `projectColor.test.ts`, `kanbanFilters.test.ts`, `errorMessages.test.ts`, `events.test.ts` (estende), `api.test.ts` (estende)

- [ ] **Step 1: Test transitions**

```ts
// ui/src/lib/transitions.test.ts
import { describe, expect, it } from 'vitest';
import { isValidTransition, resolveColumnState } from './transitions';

const VALID: Array<[string, string]> = [
  ['idea', 'ready'], ['idea', 'discarded'],
  ['ready', 'idea'], ['ready', 'in_progress'], ['ready', 'discarded'],
  ['in_progress', 'review'], ['in_progress', 'discarded'],
  ['review', 'in_progress'], ['review', 'done'], ['review', 'discarded'],
  ['discarded', 'idea'],
];
const STATES = ['idea', 'ready', 'in_progress', 'review', 'done', 'discarded'];

describe('isValidTransition', () => {
  for (const [f, t] of VALID) {
    it(`allows ${f} → ${t}`, () => {
      expect(isValidTransition(f, t)).toBe(true);
    });
  }
  for (const f of STATES) {
    it(`allows ${f} → ${f} (idempotent)`, () => {
      expect(isValidTransition(f, f)).toBe(true);
    });
  }
  it('rejects done → ready', () => {
    expect(isValidTransition('done', 'ready')).toBe(false);
  });
});

describe('resolveColumnState', () => {
  it.each([
    ['Backlog', 'in_progress', 'ready'],
    ['Backlog', 'idea', 'ready'],
    ['In Progress', 'ready', 'in_progress'],
    ['Review', 'in_progress', 'review'],
    ['Done', 'review', 'done'],
    ['Discarded', 'idea', 'discarded'],
  ])('column %s with from=%s → %s', (col, from, expected) => {
    expect(resolveColumnState(col, from)).toBe(expected);
  });
});
```

- [ ] **Step 2: RED transitions**

Run: `pnpm --dir ui exec vitest run src/lib/transitions.test.ts`
Expected: cannot find module.

- [ ] **Step 3: Implementar transitions.ts**

```ts
// ui/src/lib/transitions.ts
const VALID = new Set([
  'idea→ready', 'idea→discarded',
  'ready→idea', 'ready→in_progress', 'ready→discarded',
  'in_progress→review', 'in_progress→discarded',
  'review→in_progress', 'review→done', 'review→discarded',
  'discarded→idea',
]);

export function isValidTransition(from: string, to: string): boolean {
  if (from === to) return true;
  return VALID.has(`${from}→${to}`);
}

const COLUMN_TO_STATE: Record<string, string> = {
  Backlog: 'ready',
  'In Progress': 'in_progress',
  Review: 'review',
  Done: 'done',
  Discarded: 'discarded',
};

export function resolveColumnState(column: string, _from: string): string {
  const target = COLUMN_TO_STATE[column];
  if (!target) throw new Error(`unknown kanban column: ${column}`);
  return target;
}
```

- [ ] **Step 4: GREEN**

Run: `pnpm --dir ui exec vitest run src/lib/transitions.test.ts`
Expected: 18+ passed.

- [ ] **Step 5: Test projectColor**

```ts
// ui/src/lib/projectColor.test.ts
import { describe, expect, it } from 'vitest';
import { projectColor, PALETTE } from './projectColor';

describe('projectColor', () => {
  it('returns one of the 8 palette colors', () => {
    expect(PALETTE).toHaveLength(8);
    const c = projectColor('any-uuid-here');
    expect(PALETTE).toContain(c);
  });
  it('is deterministic for the same id', () => {
    const a = projectColor('xyz');
    const b = projectColor('xyz');
    expect(a).toBe(b);
  });
  it('distributes different ids across colors', () => {
    const colors = new Set(
      Array.from({ length: 32 }, (_, i) => projectColor(`id-${i}`))
    );
    expect(colors.size).toBeGreaterThanOrEqual(4);
  });
});
```

- [ ] **Step 6: Implementar projectColor.ts**

```ts
// ui/src/lib/projectColor.ts
export const PALETTE = [
  '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728',
  '#9467bd', '#8c564b', '#e377c2', '#17becf',
] as const;

export function projectColor(id: string): string {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
  }
  return PALETTE[hash % PALETTE.length]!;
}
```

- [ ] **Step 7: GREEN projectColor**

Run: `pnpm --dir ui exec vitest run src/lib/projectColor.test.ts`
Expected: 3 passed.

- [ ] **Step 8: Test + impl kanbanFilters**

```ts
// ui/src/lib/kanbanFilters.test.ts
import { afterEach, describe, expect, it } from 'vitest';
import { loadFilters, saveFilters } from './kanbanFilters';

afterEach(() => localStorage.clear());

describe('kanbanFilters', () => {
  it('load returns empty when nothing saved', () => {
    expect(loadFilters()).toEqual([]);
  });
  it('saves and loads array of project ids', () => {
    saveFilters(['a', 'b']);
    expect(loadFilters()).toEqual(['a', 'b']);
  });
  it('filters out ids not in the known set on read', () => {
    saveFilters(['a', 'gone']);
    expect(loadFilters(new Set(['a']))).toEqual(['a']);
  });
  it('ignores corrupted JSON gracefully', () => {
    localStorage.setItem('jarvis.kanban.filters', '{not json}');
    expect(loadFilters()).toEqual([]);
  });
});
```

```ts
// ui/src/lib/kanbanFilters.ts
const KEY = 'jarvis.kanban.filters';

export function loadFilters(known?: Set<string>): string[] {
  const raw = localStorage.getItem(KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    const ids = parsed.filter((x): x is string => typeof x === 'string');
    return known ? ids.filter((id) => known.has(id)) : ids;
  } catch {
    return [];
  }
}

export function saveFilters(ids: string[]): void {
  localStorage.setItem(KEY, JSON.stringify(ids));
}
```

- [ ] **Step 9: Test + impl errorMessages**

```ts
// ui/src/lib/errorMessages.test.ts
import { describe, expect, it } from 'vitest';
import { translateError } from './errorMessages';

describe('translateError', () => {
  it('maps "task already has active session" to pt-BR', () => {
    expect(translateError('task already has active session'))
      .toContain('sessão ativa');
  });
  it('maps "invalid transition: …" to pt-BR', () => {
    expect(translateError('invalid transition: idea → done'))
      .toContain('Transição');
  });
  it('returns raw message for unknown errors', () => {
    expect(translateError('mystery error')).toBe('mystery error');
  });
});
```

```ts
// ui/src/lib/errorMessages.ts
const RULES: Array<[RegExp, string]> = [
  [/^task already has active session$/i, 'Esta task já tem sessão ativa.'],
  [/^cannot start session: task is in terminal state/i,
    'Não dá pra iniciar sessão: task em estado terminal.'],
  [/^invalid transition:/i, 'Transição não permitida.'],
  [/^title cannot be empty/i, 'Título não pode ser vazio.'],
  [/^project has \d+ task/i, 'Descarte as tasks deste projeto antes de excluí-lo.'],
];

export function translateError(message: string): string {
  for (const [pattern, pt] of RULES) {
    if (pattern.test(message)) return pt;
  }
  return message;
}
```

- [ ] **Step 10: Estender query-keys.ts**

```ts
// ui/src/lib/query-keys.ts
export const queryKeys = {
  // … existing
  tasks: ['tasks'] as const,
  tasksForProject: (projectId: string) => ['tasks', { projectId }] as const,
};
```

- [ ] **Step 11: Estender api.ts**

```ts
// ui/src/lib/api.ts — append
export type Task = {
  id: string;
  project_id: string;
  title: string;
  description: string;
  state: string;
  template: string | null;
  permission_profile: string | null;
  created_at: string;
  updated_at: string;
  active_session_id: string | null;
};

export const api = {
  // … existing functions
  async listTasks(projectIds?: string[]): Promise<Task[]> {
    const qs = projectIds?.length
      ? `?project_ids=${encodeURIComponent(projectIds.join(','))}`
      : '';
    return fetchJson(`/api/tasks${qs}`);
  },
  async getTask(id: string): Promise<Task> {
    return fetchJson(`/api/tasks/${id}`);
  },
  async createTask(input: { project_id: string; title: string; description?: string }): Promise<Task> {
    return fetchJson('/api/tasks', { method: 'POST', body: JSON.stringify(input) });
  },
  async patchTask(id: string, patch: Partial<Pick<Task, 'title' | 'description' | 'state'>>): Promise<Task> {
    return fetchJson(`/api/tasks/${id}`, { method: 'PATCH', body: JSON.stringify(patch) });
  },
  async startTaskSession(taskId: string, worktreeId: string): Promise<Session> {
    return fetchJson(`/api/tasks/${taskId}/sessions`, {
      method: 'POST',
      body: JSON.stringify({ worktree_id: worktreeId }),
    });
  },
};
```

(Adapte `fetchJson` ao padrão existente do api.ts. SessionRead também ganhou `task_id`; estender o type `Session`.)

- [ ] **Step 12: Estender events.ts**

```ts
// ui/src/lib/events.ts
export type WsEvent =
  | {
      type: 'session.status'; session_id: string; task_id: string | null;
      payload: { status: string; previous: string }; at: string;
    }
  | {
      type: 'session.tool_use'; session_id: string; task_id: string | null;
      payload: { tool: string }; at: string;
    }
  | {
      type: 'session.stopped'; session_id: string; task_id: string | null;
      payload: Record<string, never>; at: string;
    }
  | {
      type: 'task.created'; session_id: ''; task_id: string;
      payload: { project_id: string; title: string; state: string }; at: string;
    }
  | {
      type: 'task.updated'; session_id: ''; task_id: string;
      payload: {
        project_id: string; title: string;
        state: string; previous_state: string | null;
      }; at: string;
    };

export type WsHandlers = {
  [K in WsEvent['type']]?: (event: Extract<WsEvent, { type: K }>) => void;
};

export function dispatch(event: WsEvent, handlers: WsHandlers): void {
  const handler = handlers[event.type] as ((e: WsEvent) => void) | undefined;
  if (handler) handler(event);
}
```

Tests `events.test.ts` precisam atualização — incluir tipos novos.

- [ ] **Step 13: Estender events.test.ts**

```ts
// ui/src/lib/events.test.ts — append
it('dispatches task.created', () => {
  const calls: WsEvent[] = [];
  dispatch(
    { type: 'task.created', session_id: '', task_id: 't1',
      payload: { project_id: 'p', title: 'T', state: 'idea' },
      at: '2026' },
    { 'task.created': (e) => calls.push(e) },
  );
  expect(calls).toHaveLength(1);
});

it('dispatches task.updated', () => {
  const calls: WsEvent[] = [];
  dispatch(
    { type: 'task.updated', session_id: '', task_id: 't1',
      payload: {
        project_id: 'p', title: 'T',
        state: 'ready', previous_state: 'idea',
      },
      at: '2026' },
    { 'task.updated': (e) => calls.push(e) },
  );
  expect(calls).toHaveLength(1);
});
```

- [ ] **Step 14: Rodar todos os Vitest tests**

```bash
pnpm --dir ui exec vitest run
```
Expected: tudo verde, incluindo F2 que provavelmente precisa adicionar `task_id` aos mocks.

- [ ] **Step 15: Code review**

Prompt: "Review staged: ui/src/lib/{transitions,projectColor,kanbanFilters,errorMessages}.ts + extensions to api.ts, events.ts, query-keys.ts, plus all .test.ts. Verify: (1) WsEvent discriminated union includes task_id; (2) errorMessages handles all 5 error types from spec §4.1; (3) projectColor palette matches spec decision #17 hex codes; (4) kanbanFilters silently drops unknown ids; (5) api.ts patchTask accepts only title|description|state."

- [ ] **Step 16: Commit**

```bash
git add ui/src/lib/transitions.ts ui/src/lib/projectColor.ts ui/src/lib/kanbanFilters.ts ui/src/lib/errorMessages.ts ui/src/lib/api.ts ui/src/lib/events.ts ui/src/lib/query-keys.ts ui/src/lib/transitions.test.ts ui/src/lib/projectColor.test.ts ui/src/lib/kanbanFilters.test.ts ui/src/lib/errorMessages.test.ts ui/src/lib/events.test.ts
git commit -m "$(cat <<'EOF'
feat(F4.g): UI lib utilities (transitions, projectColor, kanbanFilters, errorMessages) + api/events extends

- transitions.ts: isValidTransition + resolveColumnState
- projectColor.ts: paleta de 8 cores Tableau-10 reduzida; hash determinístico
- kanbanFilters.ts: load/save em localStorage com filter de IDs ausentes
- errorMessages.ts: en→pt-BR para 5 tipos de erro do backend
- api.ts: createTask/listTasks/getTask/patchTask/startTaskSession
- events.ts: task.created/updated; session.* ganham task_id
- query-keys.ts: + tasks, tasksForProject
EOF
)"
```

---

## Task 8 — F4.h: Kanban + KanbanColumn + TaskCard + dnd integration

**Objetivo:** componente principal do kanban e drag-drop. Maior task UI.

**Files:**
- Create: `ui/src/components/Kanban.tsx`
- Create: `ui/src/components/KanbanColumn.tsx`
- Create: `ui/src/components/TaskCard.tsx`
- Create: `ui/src/components/TaskCard.test.tsx`
- Create: `ui/src/components/Kanban.test.tsx`
- Create: `ui/src/hooks/useTasks.ts`
- Create: `ui/src/hooks/useTaskMutations.ts`

- [ ] **Step 1: TaskCard — RED**

```tsx
// ui/src/components/TaskCard.test.tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { TaskCard } from './TaskCard';

const baseTask = {
  id: 't1', project_id: 'p1', title: 'Adicionar dark mode',
  description: '', state: 'idea',
  template: null, permission_profile: null,
  created_at: '2026', updated_at: '2026', active_session_id: null,
};
const projects = new Map([['p1', { id: 'p1', name: 'projA', path: '/p' }]]);

describe('TaskCard', () => {
  it('renders title and project chip', () => {
    render(<TaskCard task={baseTask} projects={projects} />);
    expect(screen.getByText('Adicionar dark mode')).toBeInTheDocument();
    expect(screen.getByText('projA')).toBeInTheDocument();
  });
  it('renders sub-tag idea on Backlog state', () => {
    render(<TaskCard task={baseTask} projects={projects} />);
    expect(screen.getByText('idea')).toBeInTheDocument();
  });
  it('renders ready sub-tag', () => {
    render(<TaskCard task={{ ...baseTask, state: 'ready' }} projects={projects} />);
    expect(screen.getByText('ready')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Implementar TaskCard**

```tsx
// ui/src/components/TaskCard.tsx
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import type { Task, Project } from '../lib/api';
import { projectColor } from '../lib/projectColor';

type Props = {
  task: Task;
  projects: Map<string, Project>;
  onClick?: () => void;
};

export function TaskCard({ task, projects, onClick }: Props) {
  const { attributes, listeners, setNodeRef, transform, transition } =
    useSortable({ id: task.id });
  const project = projects.get(task.project_id);
  const subTag =
    task.state === 'idea' || task.state === 'ready' ? task.state : null;

  return (
    <div
      ref={setNodeRef}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
      }}
      className="task-card"
      data-task-id={task.id}
      onClick={onClick}
      {...attributes}
      {...listeners}
    >
      <span
        className="project-chip"
        style={{ backgroundColor: projectColor(task.project_id) }}
      >
        ● {project?.name ?? task.project_id.slice(0, 6)}
      </span>
      <h4>{task.title}</h4>
      {subTag && <span className="sub-tag">{subTag}</span>}
    </div>
  );
}
```

(Estilos CSS são detalhe — bare minimum em `App.css` ou similar.)

- [ ] **Step 3: GREEN TaskCard**

Run: `pnpm --dir ui exec vitest run src/components/TaskCard.test.tsx`
Expected: 3 passed.

- [ ] **Step 4: useTasks hook**

```ts
// ui/src/hooks/useTasks.ts
import { useQuery, type QueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { api, type Task } from '../lib/api';
import { dispatch, type WsEvent } from '../lib/events';
import { queryKeys } from '../lib/query-keys';

export function useTasks(projectIds: string[] | undefined) {
  return useQuery({
    queryKey: projectIds?.length
      ? ['tasks', { projectIds }]
      : queryKeys.tasks,
    queryFn: () => api.listTasks(projectIds),
  });
}

export function useTaskWsInvalidator(queryClient: QueryClient) {
  // separate hook composed by useSessionEvents
  return (event: WsEvent) => {
    dispatch(event, {
      'task.created': () => queryClient.invalidateQueries({ queryKey: queryKeys.tasks }),
      'task.updated': () => queryClient.invalidateQueries({ queryKey: queryKeys.tasks }),
      'session.status': () => queryClient.invalidateQueries({ queryKey: queryKeys.tasks }),
      'session.stopped': () => queryClient.invalidateQueries({ queryKey: queryKeys.tasks }),
    });
  };
}
```

- [ ] **Step 5: useTaskMutations hook**

```ts
// ui/src/hooks/useTaskMutations.ts
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';
import { queryKeys } from '../lib/query-keys';

export function useCreateTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.createTask,
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.tasks }),
  });
}

export function usePatchTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Parameters<typeof api.patchTask>[1] }) =>
      api.patchTask(id, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.tasks }),
  });
}

export function useStartTaskSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ taskId, worktreeId }: { taskId: string; worktreeId: string }) =>
      api.startTaskSession(taskId, worktreeId),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.tasks }),
  });
}
```

- [ ] **Step 6: Kanban + KanbanColumn — RED**

```tsx
// ui/src/components/Kanban.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import { Kanban } from './Kanban';

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual('../lib/api');
  return {
    ...actual,
    api: {
      listTasks: vi.fn().mockResolvedValue([
        { id: 't1', project_id: 'p1', title: 'A', state: 'idea',
          description: '', template: null, permission_profile: null,
          created_at: '', updated_at: '', active_session_id: null },
        { id: 't2', project_id: 'p1', title: 'B', state: 'in_progress',
          description: '', template: null, permission_profile: null,
          created_at: '', updated_at: '', active_session_id: 's1' },
      ]),
      patchTask: vi.fn(),
      listProjects: vi.fn().mockResolvedValue([{ id: 'p1', name: 'projA', path: '/p' }]),
    },
  };
});

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient();
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('Kanban', () => {
  it('renders 5 columns', async () => {
    wrap(<Kanban filters={[]} />);
    expect(await screen.findByText('Backlog')).toBeInTheDocument();
    expect(screen.getByText('In Progress')).toBeInTheDocument();
    expect(screen.getByText('Review')).toBeInTheDocument();
    expect(screen.getByText('Done')).toBeInTheDocument();
    expect(screen.getByText('Discarded')).toBeInTheDocument();
  });

  it('places idea task in Backlog and in_progress in In Progress', async () => {
    wrap(<Kanban filters={[]} />);
    await screen.findByText('A');
    const backlog = screen.getByTestId('column-Backlog');
    const inprog = screen.getByTestId('column-In Progress');
    expect(backlog).toContainElement(screen.getByText('A'));
    expect(inprog).toContainElement(screen.getByText('B'));
  });

  it('does NOT call patchTask when transition is invalid (snap-back)', async () => {
    const { api } = await import('../lib/api');
    wrap(<Kanban filters={[]} />);
    await screen.findByText('A');
    // Simulate dnd-kit drag of task in 'idea' → Done column.
    // Using internal trigger via window.__dndKitInvalidDragEnd or
    // direct call to onDragEnd handler is needed here.
    // (see implementation Step 7)
    fireEvent(window, new CustomEvent('test:dragEnd', {
      detail: { taskId: 't1', column: 'Done' },
    }));
    expect(api.patchTask).not.toHaveBeenCalled();
  });

  it('calls patchTask when transition is valid', async () => {
    const { api } = await import('../lib/api');
    wrap(<Kanban filters={[]} />);
    await screen.findByText('A');
    fireEvent(window, new CustomEvent('test:dragEnd', {
      detail: { taskId: 't1', column: 'Backlog' },  // idea → ready (canonical of Backlog)
    }));
    expect(api.patchTask).toHaveBeenCalledWith('t1', { state: 'ready' });
  });
});
```

(O `test:dragEnd` event é hook de testing — implementação no componente abaixo escuta esse evento sintético em ambiente de teste.)

- [ ] **Step 7: Implementar KanbanColumn**

```tsx
// ui/src/components/KanbanColumn.tsx
import { useDroppable } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { TaskCard } from './TaskCard';
import type { Task, Project } from '../lib/api';

type Props = {
  name: string;
  tasks: Task[];
  projects: Map<string, Project>;
  onCardClick?: (id: string) => void;
};

export function KanbanColumn({ name, tasks, projects, onCardClick }: Props) {
  const { setNodeRef } = useDroppable({ id: name });
  return (
    <div
      ref={setNodeRef}
      className="kanban-column"
      data-testid={`column-${name}`}
    >
      <h3>{name}</h3>
      <SortableContext
        items={tasks.map((t) => t.id)}
        strategy={verticalListSortingStrategy}
      >
        {tasks.map((t) => (
          <TaskCard
            key={t.id} task={t} projects={projects}
            onClick={() => onCardClick?.(t.id)}
          />
        ))}
      </SortableContext>
    </div>
  );
}
```

- [ ] **Step 8: Implementar Kanban**

```tsx
// ui/src/components/Kanban.tsx
import { DndContext, closestCenter, type DragEndEvent } from '@dnd-kit/core';
import { useEffect, useState } from 'react';
import { useTasks } from '../hooks/useTasks';
import { usePatchTask } from '../hooks/useTaskMutations';
import { useQuery } from '@tanstack/react-query';
import { api, type Task, type Project } from '../lib/api';
import { isValidTransition, resolveColumnState } from '../lib/transitions';
import { translateError } from '../lib/errorMessages';
import { queryKeys } from '../lib/query-keys';
import { KanbanColumn } from './KanbanColumn';

const COLUMNS = ['Backlog', 'In Progress', 'Review', 'Done', 'Discarded'] as const;

function bucketize(tasks: Task[]): Record<string, Task[]> {
  const buckets: Record<string, Task[]> = Object.fromEntries(
    COLUMNS.map((c) => [c, []])
  );
  for (const t of tasks) {
    if (t.state === 'idea' || t.state === 'ready') buckets.Backlog.push(t);
    else if (t.state === 'in_progress') buckets['In Progress'].push(t);
    else if (t.state === 'review') buckets.Review.push(t);
    else if (t.state === 'done') buckets.Done.push(t);
    else if (t.state === 'discarded') buckets.Discarded.push(t);
  }
  return buckets;
}

type Props = {
  filters: string[];
  onCardClick?: (id: string) => void;
};

export function Kanban({ filters, onCardClick }: Props) {
  const tasks = useTasks(filters.length ? filters : undefined);
  const projects = useQuery({
    queryKey: queryKeys.projects,
    queryFn: api.listProjects,
  });
  const patch = usePatchTask();
  const [error, setError] = useState<string | null>(null);

  const projectMap = new Map(projects.data?.map((p) => [p.id, p]) ?? []);
  const taskById = new Map(tasks.data?.map((t) => [t.id, t]) ?? []);
  const buckets = bucketize(tasks.data ?? []);

  function handleDragEnd(taskId: string, column: string): void {
    const task = taskById.get(taskId);
    if (!task) return;
    const target = resolveColumnState(column, task.state);
    if (target === task.state) return;            // no-op
    if (!isValidTransition(task.state, target)) {
      setError('Transição não permitida.');
      return;
    }
    patch.mutate(
      { id: taskId, patch: { state: target } },
      { onError: (err) => setError(translateError(String(err))) },
    );
  }

  function onDragEnd(e: DragEndEvent): void {
    const taskId = String(e.active.id);
    const column = e.over ? String(e.over.id) : null;
    if (!column) return;
    handleDragEnd(taskId, column);
  }

  useEffect(() => {
    function fromCustom(ev: Event): void {
      const detail = (ev as CustomEvent).detail;
      handleDragEnd(detail.taskId, detail.column);
    }
    window.addEventListener('test:dragEnd', fromCustom);
    return () => window.removeEventListener('test:dragEnd', fromCustom);
  });

  return (
    <>
      {error && <div role="alert" className="toast">{error}</div>}
      <DndContext collisionDetection={closestCenter} onDragEnd={onDragEnd}>
        <div className="kanban">
          {COLUMNS.map((col) => (
            <KanbanColumn
              key={col} name={col}
              tasks={buckets[col]} projects={projectMap}
              onCardClick={onCardClick}
            />
          ))}
        </div>
      </DndContext>
    </>
  );
}
```

- [ ] **Step 9: GREEN Kanban tests**

Run: `pnpm --dir ui exec vitest run src/components/Kanban.test.tsx`
Expected: 4 passed.

- [ ] **Step 10: Coverage**

```bash
pnpm --dir ui exec vitest run --coverage src/components/TaskCard.test.tsx src/components/Kanban.test.tsx
```
Expected: 100% em `Kanban.tsx`, `KanbanColumn.tsx`, `TaskCard.tsx`, `useTasks.ts`, `useTaskMutations.ts`.

- [ ] **Step 11: Code review**

Prompt: "Review staged: ui/src/components/{Kanban,KanbanColumn,TaskCard}.tsx + ui/src/hooks/{useTasks,useTaskMutations}.ts + tests. Verify: (1) bucketize correctly maps states to columns; (2) onDragEnd calls handleDragEnd which uses isValidTransition AND resolveColumnState; (3) snap-back path does NOT call patchTask; (4) test:dragEnd custom-event seam is clearly marked as test-only and doesn't bypass dnd-kit in production; (5) react keys, accessibility roles."

- [ ] **Step 12: Commit**

```bash
git add ui/src/components/Kanban.tsx ui/src/components/KanbanColumn.tsx ui/src/components/TaskCard.tsx ui/src/components/TaskCard.test.tsx ui/src/components/Kanban.test.tsx ui/src/hooks/useTasks.ts ui/src/hooks/useTaskMutations.ts
git commit -m "$(cat <<'EOF'
feat(F4.h): Kanban + KanbanColumn + TaskCard + dnd-kit integration

- 5 colunas, bucketização por state (idea+ready agrupados em Backlog)
- DndContext + SortableContext por coluna
- onDragEnd resolve state canônico da coluna; snap-back NÃO chama patchTask
- TaskCard: chip de projeto colorido + sub-tag idea/ready em Backlog
- Hooks useTasks (query + WS-invalidate) e useTaskMutations
EOF
)"
```

---

## Task 9 — F4.i: TaskDetailModal + NewTaskForm + ProjectFilters

**Objetivo:** modal de detalhe da task com edit + Move-to + iniciar sessão; form inline pra criar task; filtros de projeto.

**Files:**
- Create: `ui/src/components/TaskDetailModal.tsx`
- Create: `ui/src/components/TaskDetailModal.test.tsx`
- Create: `ui/src/components/NewTaskForm.tsx`
- Create: `ui/src/components/NewTaskForm.test.tsx`
- Create: `ui/src/components/ProjectFilters.tsx`
- Create: `ui/src/components/ProjectFilters.test.tsx`

- [ ] **Step 1: TaskDetailModal — RED**

```tsx
// ui/src/components/TaskDetailModal.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import { TaskDetailModal } from './TaskDetailModal';

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual('../lib/api');
  return {
    ...actual,
    api: {
      getTask: vi.fn().mockResolvedValue({
        id: 't1', project_id: 'p1', title: 'X', description: 'D',
        state: 'ready', template: null, permission_profile: null,
        created_at: '', updated_at: '', active_session_id: null,
      }),
      patchTask: vi.fn().mockResolvedValue({}),
      startTaskSession: vi.fn().mockResolvedValue({}),
      listWorktrees: vi.fn().mockResolvedValue([
        { id: 'w1', project_id: 'p1', branch: 'main', path: '/r' },
      ]),
    },
  };
});

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient();
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('TaskDetailModal', () => {
  it('lists only valid Move-to states from current state ready', async () => {
    wrap(<TaskDetailModal taskId="t1" onClose={() => {}} />);
    await screen.findByDisplayValue('X');
    const select = screen.getByLabelText(/move to/i) as HTMLSelectElement;
    const opts = Array.from(select.options).map((o) => o.value);
    // ready → idea, in_progress, discarded
    expect(opts).toEqual(expect.arrayContaining(['idea', 'in_progress', 'discarded']));
    expect(opts).not.toContain('done');
  });

  it('disables iniciar sessão when state is done', async () => {
    const { api } = await import('../lib/api');
    (api.getTask as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      id: 't1', project_id: 'p1', title: 'X', description: '',
      state: 'done', template: null, permission_profile: null,
      created_at: '', updated_at: '', active_session_id: null,
    });
    wrap(<TaskDetailModal taskId="t1" onClose={() => {}} />);
    const btn = await screen.findByRole('button', { name: /iniciar sessão/i });
    expect(btn).toBeDisabled();
  });

  it('debounces title PATCH', async () => {
    const { api } = await import('../lib/api');
    wrap(<TaskDetailModal taskId="t1" onClose={() => {}} />);
    const input = await screen.findByDisplayValue('X');
    fireEvent.change(input, { target: { value: 'Y' } });
    fireEvent.change(input, { target: { value: 'Y2' } });
    await waitFor(
      () => expect(api.patchTask).toHaveBeenCalledTimes(1),
      { timeout: 1000 },
    );
    expect(api.patchTask).toHaveBeenLastCalledWith('t1', { title: 'Y2' });
  });
});
```

- [ ] **Step 2: Implementar TaskDetailModal**

```tsx
// ui/src/components/TaskDetailModal.tsx
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { isValidTransition } from '../lib/transitions';
import { usePatchTask, useStartTaskSession } from '../hooks/useTaskMutations';
import { translateError } from '../lib/errorMessages';

const ALL_STATES = ['idea', 'ready', 'in_progress', 'review', 'done', 'discarded'];

type Props = { taskId: string; onClose: () => void };

export function TaskDetailModal({ taskId, onClose }: Props) {
  const task = useQuery({
    queryKey: ['task', taskId],
    queryFn: () => api.getTask(taskId),
  });
  const worktrees = useQuery({
    queryKey: ['worktrees', task.data?.project_id],
    queryFn: () => api.listWorktrees(task.data!.project_id),
    enabled: !!task.data,
  });
  const patch = usePatchTask();
  const start = useStartTaskSession();
  const qc = useQueryClient();

  const [titleDraft, setTitleDraft] = useState('');
  const [descDraft, setDescDraft] = useState('');
  const [selectedWorktree, setSelectedWorktree] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (task.data) {
      setTitleDraft(task.data.title);
      setDescDraft(task.data.description);
    }
  }, [task.data?.id]);

  // Debounced PATCH for title/description
  useEffect(() => {
    if (!task.data) return;
    if (titleDraft === task.data.title && descDraft === task.data.description) return;
    if (!titleDraft.trim()) return; // não permite blank
    const tid = setTimeout(() => {
      patch.mutate({
        id: taskId,
        patch: {
          ...(titleDraft !== task.data!.title ? { title: titleDraft } : {}),
          ...(descDraft !== task.data!.description ? { description: descDraft } : {}),
        },
      });
    }, 500);
    return () => clearTimeout(tid);
  }, [titleDraft, descDraft]);

  if (!task.data) return null;
  const t = task.data;

  const moveTargets = ALL_STATES.filter(
    (s) => s !== t.state && isValidTransition(t.state, s)
  );

  const isTerminal = t.state === 'done' || t.state === 'discarded';

  return (
    <div role="dialog" className="modal" aria-label={t.title}>
      <button onClick={onClose} aria-label="close">✕</button>
      <input
        aria-label="title"
        value={titleDraft}
        onChange={(e) => setTitleDraft(e.target.value)}
      />
      <textarea
        aria-label="description"
        value={descDraft}
        onChange={(e) => setDescDraft(e.target.value)}
      />
      <label>
        Move to:
        <select
          value=""
          onChange={(e) => {
            if (!e.target.value) return;
            patch.mutate({ id: taskId, patch: { state: e.target.value } });
          }}
        >
          <option value="">—</option>
          {moveTargets.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </label>

      <h4>Sessions</h4>
      {/* lista cronológica simplificada — F4.i fica em scaffold */}
      {/* ... */}

      <label>
        Worktree:
        <select
          value={selectedWorktree}
          onChange={(e) => setSelectedWorktree(e.target.value)}
        >
          <option value="">—</option>
          {(worktrees.data ?? []).map((w) => (
            <option key={w.id} value={w.id}>{w.branch ?? '(detached)'}</option>
          ))}
        </select>
      </label>
      <button
        disabled={isTerminal || !selectedWorktree}
        onClick={() =>
          start.mutate(
            { taskId, worktreeId: selectedWorktree },
            { onError: (err) => setError(translateError(String(err))) },
          )
        }
      >
        ▶ Iniciar sessão
      </button>
      {error && <p role="alert">{error}</p>}
    </div>
  );
}
```

- [ ] **Step 3: GREEN modal**

Run: `pnpm --dir ui exec vitest run src/components/TaskDetailModal.test.tsx`
Expected: 3 passed.

- [ ] **Step 4: NewTaskForm — test + impl**

```tsx
// ui/src/components/NewTaskForm.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import { NewTaskForm } from './NewTaskForm';

const projects = [{ id: 'p1', name: 'projA', path: '/p' }];

vi.mock('../lib/api', () => ({
  api: {
    createTask: vi.fn().mockResolvedValue({}),
  },
}));

function wrap(ui: React.ReactElement) {
  return render(<QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>);
}

describe('NewTaskForm', () => {
  it('disables submit when title is blank', () => {
    wrap(<NewTaskForm projects={projects} />);
    expect(screen.getByRole('button', { name: /criar/i })).toBeDisabled();
  });

  it('calls createTask on submit', async () => {
    const { api } = await import('../lib/api');
    wrap(<NewTaskForm projects={projects} />);
    fireEvent.change(screen.getByLabelText(/título/i), { target: { value: 'A' } });
    fireEvent.change(screen.getByLabelText(/projeto/i), { target: { value: 'p1' } });
    fireEvent.click(screen.getByRole('button', { name: /criar/i }));
    expect(api.createTask).toHaveBeenCalledWith({
      project_id: 'p1', title: 'A', description: '',
    });
  });
});
```

```tsx
// ui/src/components/NewTaskForm.tsx
import { useState, type FormEvent } from 'react';
import type { Project } from '../lib/api';
import { useCreateTask } from '../hooks/useTaskMutations';

type Props = { projects: Project[] };

export function NewTaskForm({ projects }: Props) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [projectId, setProjectId] = useState(projects[0]?.id ?? '');
  const create = useCreateTask();

  const canSubmit = title.trim().length > 0 && projectId;

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    create.mutate(
      { project_id: projectId, title, description },
      { onSuccess: () => { setTitle(''); setDescription(''); } },
    );
  }

  return (
    <form onSubmit={onSubmit} aria-label="new-task">
      <label>
        Projeto:
        <select value={projectId} onChange={(e) => setProjectId(e.target.value)}>
          {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      </label>
      <input
        aria-label="título"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Título"
      />
      <textarea
        aria-label="descrição"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
      />
      <button type="submit" disabled={!canSubmit || create.isPending}>
        Criar
      </button>
    </form>
  );
}
```

- [ ] **Step 5: GREEN NewTaskForm**

Run: `pnpm --dir ui exec vitest run src/components/NewTaskForm.test.tsx`
Expected: 2 passed.

- [ ] **Step 6: ProjectFilters**

```tsx
// ui/src/components/ProjectFilters.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ProjectFilters } from './ProjectFilters';

const projects = [
  { id: 'p1', name: 'projA', path: '/a' },
  { id: 'p2', name: 'projB', path: '/b' },
];

describe('ProjectFilters', () => {
  it('toggles a project on click', () => {
    const onChange = vi.fn();
    render(<ProjectFilters projects={projects} active={[]} onChange={onChange} />);
    fireEvent.click(screen.getByText('projA'));
    expect(onChange).toHaveBeenCalledWith(['p1']);
  });

  it('renders all projects with active highlight', () => {
    render(<ProjectFilters projects={projects} active={['p1']} onChange={() => {}} />);
    expect(screen.getByText('projA').className).toMatch(/active/);
    expect(screen.getByText('projB').className).not.toMatch(/active/);
  });
});
```

```tsx
// ui/src/components/ProjectFilters.tsx
import type { Project } from '../lib/api';

type Props = {
  projects: Project[];
  active: string[];
  onChange: (next: string[]) => void;
};

export function ProjectFilters({ projects, active, onChange }: Props) {
  const set = new Set(active);
  return (
    <div className="project-filters">
      {projects.map((p) => {
        const on = set.has(p.id);
        return (
          <button
            key={p.id}
            className={on ? 'chip active' : 'chip'}
            onClick={() =>
              onChange(on ? active.filter((x) => x !== p.id) : [...active, p.id])
            }
          >
            {p.name}
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 7: GREEN ProjectFilters**

Run: `pnpm --dir ui exec vitest run src/components/ProjectFilters.test.tsx`
Expected: 2 passed.

- [ ] **Step 8: Coverage**

```bash
pnpm --dir ui exec vitest run --coverage src/components/TaskDetailModal.test.tsx src/components/NewTaskForm.test.tsx src/components/ProjectFilters.test.tsx
```
Expected: 100% nos arquivos novos.

- [ ] **Step 9: Code review**

Prompt: "Review staged: TaskDetailModal.tsx, NewTaskForm.tsx, ProjectFilters.tsx + tests. Verify: (1) modal Move-to dropdown filters by isValidTransition; (2) Iniciar sessão button is disabled when terminal state; (3) NewTaskForm rejects blank title via disabled button; (4) ProjectFilters toggle is pure (no localStorage here — that's App.tsx)."

- [ ] **Step 10: Commit**

```bash
git add ui/src/components/TaskDetailModal.tsx ui/src/components/TaskDetailModal.test.tsx ui/src/components/NewTaskForm.tsx ui/src/components/NewTaskForm.test.tsx ui/src/components/ProjectFilters.tsx ui/src/components/ProjectFilters.test.tsx
git commit -m "$(cat <<'EOF'
feat(F4.i): TaskDetailModal + NewTaskForm + ProjectFilters

- Modal com title/desc edit (debounced 500ms), Move-to dropdown
  filtrado por transições válidas, dropdown de worktree, botão
  iniciar sessão disabled em estado terminal
- NewTaskForm com project picker; submit disabled com title em branco
- ProjectFilters: chips clicáveis multi-select; estado controlado
EOF
)"
```

---

## Task 10 — F4.j: ProjectsDrawer (encapsula UI atual + delete-409 toast)

**Objetivo:** mover o flow atual de Projects/Worktrees pra um drawer lateral acionado por botão "Projetos ▾". Adicionar toast quando DELETE retorna 409.

**Files:**
- Create: `ui/src/components/ProjectsDrawer.tsx`
- Create: `ui/src/components/ProjectsDrawer.test.tsx`

- [ ] **Step 1: Test drawer**

```tsx
// ui/src/components/ProjectsDrawer.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import { ProjectsDrawer } from './ProjectsDrawer';

vi.mock('../lib/api', () => ({
  api: {
    listProjects: vi.fn().mockResolvedValue([
      { id: 'p1', name: 'projA', path: '/p' },
    ]),
    listWorktrees: vi.fn().mockResolvedValue([]),
    deleteProject: vi.fn(),
  },
}));

function wrap(ui: React.ReactElement) {
  return render(<QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>);
}

describe('ProjectsDrawer', () => {
  it('renders projects when open', async () => {
    wrap(<ProjectsDrawer open={true} onClose={() => {}} />);
    expect(await screen.findByText('projA')).toBeInTheDocument();
  });

  it('does not render when closed', () => {
    wrap(<ProjectsDrawer open={false} onClose={() => {}} />);
    expect(screen.queryByText('projA')).toBeNull();
  });

  it('shows toast when delete-project returns 409', async () => {
    const { api } = await import('../lib/api');
    (api.deleteProject as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error('project has 2 task(s); discard them before deleting')
    );
    wrap(<ProjectsDrawer open={true} onClose={() => {}} />);
    fireEvent.click(await screen.findByLabelText(/delete-projA/i));
    await waitFor(() => {
      expect(screen.getByRole('alert').textContent).toMatch(/Descarte as tasks/i);
    });
  });
});
```

- [ ] **Step 2: Implementar ProjectsDrawer**

```tsx
// ui/src/components/ProjectsDrawer.tsx
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '../lib/api';
import { translateError } from '../lib/errorMessages';
import { queryKeys } from '../lib/query-keys';

type Props = { open: boolean; onClose: () => void };

export function ProjectsDrawer({ open, onClose }: Props) {
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const projects = useQuery({
    queryKey: queryKeys.projects,
    queryFn: api.listProjects,
    enabled: open,
  });
  const del = useMutation({
    mutationFn: (id: string) => api.deleteProject(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.projects }),
    onError: (err) => setError(translateError(String((err as Error).message ?? err))),
  });

  if (!open) return null;
  return (
    <aside role="dialog" aria-label="projects-drawer" className="drawer">
      <header>
        <h2>Projetos</h2>
        <button onClick={onClose} aria-label="close-drawer">✕</button>
      </header>
      {projects.data?.map((p) => (
        <div key={p.id} className="project-row">
          <strong>{p.name}</strong>
          <code>{p.path}</code>
          <button
            aria-label={`delete-${p.name}`}
            onClick={() => del.mutate(p.id)}
          >
            Excluir
          </button>
          <WorktreesInline projectId={p.id} />
        </div>
      ))}
      {error && <p role="alert">{error}</p>}
    </aside>
  );
}

function WorktreesInline({ projectId }: { projectId: string }) {
  const wts = useQuery({
    queryKey: queryKeys.worktrees(projectId),
    queryFn: () => api.listWorktrees(projectId),
  });
  return (
    <ul>
      {wts.data?.map((w) => (
        <li key={w.id}>
          <code>{w.branch ?? '(detached)'}</code>
          <button
            onClick={() => api.startSession(w.id)}
            aria-label={`quick-${w.branch ?? w.id}`}
          >
            ▶ Quick session
          </button>
        </li>
      ))}
    </ul>
  );
}
```

- [ ] **Step 3: GREEN drawer**

Run: `pnpm --dir ui exec vitest run src/components/ProjectsDrawer.test.tsx`
Expected: 3 passed.

- [ ] **Step 4: Code review**

Prompt: "Review staged: ProjectsDrawer.tsx + test. Verify: (1) projects/worktrees query is gated on `open` to avoid useless fetches; (2) deleteProject error path translates message via errorMessages; (3) Quick session button still works (delegates to api.startSession)."

- [ ] **Step 5: Commit**

```bash
git add ui/src/components/ProjectsDrawer.tsx ui/src/components/ProjectsDrawer.test.tsx
git commit -m "$(cat <<'EOF'
feat(F4.j): ProjectsDrawer encapsula UI atual + toast em delete-409

- Drawer lateral controlado por prop `open`
- Lista projects + worktrees inline; mantém Quick session button
- DELETE 409 vira toast pt-BR via translateError
EOF
)"
```

---

## Task 11 — F4.k: App.tsx layout reorg + useTasks hook + useSessionEvents extends

**Objetivo:** orquestrar todos os componentes novos no App; remover Projects/Worktrees do main flow (vão pro drawer); estender useSessionEvents pra invalidar tasks.

**Files:**
- Modify: `ui/src/App.tsx`
- Modify: `ui/src/hooks/useSessionEvents.ts`

- [ ] **Step 1: Estender useSessionEvents**

```ts
// ui/src/hooks/useSessionEvents.ts — modify dispatch handler
// Adicionar handlers pra task.created/task.updated +
// invalidar queryKeys.tasks também em session.status/session.stopped
```

(Se `useSessionEvents` usa `dispatch` direto: passar handlers pra ambos os tipos.)

- [ ] **Step 2: Reescrever App.tsx**

```tsx
// ui/src/App.tsx — full rewrite
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import { api } from './lib/api';
import { loadFilters, saveFilters } from './lib/kanbanFilters';
import { queryKeys } from './lib/query-keys';
import { useSessionEvents } from './hooks/useSessionEvents';

import { Kanban } from './components/Kanban';
import { NewTaskForm } from './components/NewTaskForm';
import { ProjectFilters } from './components/ProjectFilters';
import { ProjectsDrawer } from './components/ProjectsDrawer';
import { TaskDetailModal } from './components/TaskDetailModal';

export function App() {
  const queryClient = useQueryClient();
  useSessionEvents(queryClient);

  const projects = useQuery({
    queryKey: queryKeys.projects,
    queryFn: api.listProjects,
  });
  const known = new Set(projects.data?.map((p) => p.id) ?? []);

  const [filters, setFilters] = useState<string[]>(() => loadFilters(known));
  useEffect(() => {
    saveFilters(filters);
  }, [filters]);

  // Re-validate filters when projects change
  useEffect(() => {
    if (projects.data) {
      setFilters((prev) => prev.filter((id) => known.has(id)));
    }
  }, [projects.data?.length]);

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);

  return (
    <main>
      <header>
        <h1>J-arvis</h1>
        <button onClick={() => setDrawerOpen(true)}>Projetos ▾</button>
      </header>
      <ProjectFilters
        projects={projects.data ?? []}
        active={filters}
        onChange={setFilters}
      />
      <Kanban filters={filters} onCardClick={setSelectedTaskId} />
      <NewTaskForm projects={projects.data ?? []} />

      <ProjectsDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />
      {selectedTaskId && (
        <TaskDetailModal
          taskId={selectedTaskId}
          onClose={() => setSelectedTaskId(null)}
        />
      )}
    </main>
  );
}
```

- [ ] **Step 3: Re-rodar todos os Vitest tests**

```bash
pnpm --dir ui exec vitest run
```
Expected: tudo verde. Pode ser que App.test.ts pré-existente quebre — atualizar pra refletir novo layout.

- [ ] **Step 4: Smoke test em browser (manual)**

```bash
pnpm --dir ui run dev
# Abrir http://localhost:5173 (porta default Vite)
# Verificar:
# - "J-arvis" + botão Projetos ▾
# - 5 colunas vazias do Kanban
# - Form "Nova task" no rodapé
# - Botão Projetos ▾ abre drawer
```

- [ ] **Step 5: Coverage final UI**

```bash
pnpm --dir ui exec vitest run --coverage
```
Expected: 100% nos arquivos novos; App.tsx pode ser menor se houver branches difíceis (ex: error states de queries) — admissível com `// @vitest-ignore` ou test extra se for realmente cobrir.

- [ ] **Step 6: Code review**

Prompt: "Review staged: ui/src/App.tsx (full rewrite) + ui/src/hooks/useSessionEvents.ts (extends). Verify: (1) filters persist to localStorage on every change; (2) filters re-validate when projects.data changes (delete project removes from filters); (3) drawer/modal are conditionally rendered (no remount thrash); (4) useSessionEvents invalidates tasks on session.status."

- [ ] **Step 7: Commit**

```bash
git add ui/src/App.tsx ui/src/hooks/useSessionEvents.ts
git commit -m "$(cat <<'EOF'
feat(F4.k): App.tsx reorganizado em torno do Kanban + ProjectsDrawer

- Header com título + botão Projetos ▾ (abre drawer)
- ProjectFilters chips no topo, persiste em localStorage via kanbanFilters
- Kanban (5 colunas) ocupa main; NewTaskForm no rodapé da Backlog
- TaskDetailModal abre ao clicar num card
- useSessionEvents invalida tasks em session.status/stopped
EOF
)"
```

---

## Task 12 — F4.l: E2E flows + ARCHITECTURE update + ADR-0012/0013 + Demo

**Objetivo:** fechamento da fase. E2E Playwright cobrindo o fluxo completo, atualizar `ARCHITECTURE.md`, criar ADR-0012 e ADR-0013, atualizar `docs/adr/README.md`, executar demo manual.

**Files:**
- Create: `tests/e2e/test_kanban_e2e_flow.py`
- Modify: `ARCHITECTURE.md` (§3, §11, §13)
- Create: `docs/adr/0012-task-como-entidade-primaria.md`
- Create: `docs/adr/0013-kanban-unificado-cross-project.md`
- Modify: `docs/adr/README.md`

- [ ] **Step 1: E2E test (Playwright + Docker)**

```python
# tests/e2e/test_kanban_e2e_flow.py
"""E2E: criar task → drag → iniciar sessão (NullSessionRuntime)
→ drag pra Done."""
import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
def test_kanban_happy_path(page: Page, daemon_url: str, seed_project_and_worktree):
    page.goto(f"{daemon_url}/")

    # Criar task
    page.fill('[aria-label="título"]', "Adicionar dark mode")
    page.click('button:has-text("Criar")')

    # Aparece em Backlog
    backlog = page.locator('[data-testid="column-Backlog"]')
    expect(backlog).to_contain_text("Adicionar dark mode")

    # Drag idea → ready (intra-Backlog não muda; precisa via modal)
    # Em vez disso: clica → Move-to → ready
    page.click("text=Adicionar dark mode")
    page.select_option('select[aria-label="move to"]', "ready")

    # Iniciar sessão
    page.select_option('select[name="worktree"]', "main")
    page.click('button:has-text("Iniciar sessão")')

    # Card foi pra In Progress
    inprog = page.locator('[data-testid="column-In Progress"]')
    expect(inprog).to_contain_text("Adicionar dark mode")

    # Drag In Progress → Review
    page.drag_to(
        page.locator('[data-task-id]').first,
        page.locator('[data-testid="column-Review"]'),
    )
    review = page.locator('[data-testid="column-Review"]')
    expect(review).to_contain_text("Adicionar dark mode")

    # Drag Review → Done
    page.drag_to(
        review.locator('[data-task-id]').first,
        page.locator('[data-testid="column-Done"]'),
    )
    expect(page.locator('[data-testid="column-Done"]')).to_contain_text("Adicionar dark mode")
```

(Outros 5 flows de §7.4 do spec: quick session, transição inválida, filtro, duplo-iniciar, project-delete-409. Cada um similar em estrutura — pode ser implementado iterativamente.)

- [ ] **Step 2: Rodar E2E (do host, fora da jaula!)**

```bash
uv run pytest tests/e2e/test_kanban_e2e_flow.py -v
```
Expected: passa. ⚠️ **Esse passo só roda fora da jaula ai-jail** (gotcha #9).

- [ ] **Step 3: ADR-0012**

```markdown
# ADR-0012: Task como entidade primária; Session é filha obrigatória

- **Status:** Accepted
- **Data:** 2026-05-09
- **Decisores:** Marcos

## Contexto

Antes de F4 a `ClaudeSession` era órfã (vinculada só a Worktree). UX
pedia "qual sessão está rodando agora?" mas o usuário pensa em
"qual trabalho preciso fazer?". ARCHITECTURE.md §1.2 já estabelecia
o princípio task-first; F4 implementa.

## Decisão

`Task` é a entidade primária do domínio (kanban + roadmap).
`Session.task_id` é FK NOT NULL. Não há Session órfã. Quick session
(clique numa worktree) cria Task implícita "Quick session · <branch>"
em `in_progress`.

`Task` não conhece worktree — Session traz worktree. Tasks no
backlog não precisam alocar worktree.

## Alternativas

1. **`Session.task_id` opcional** (rejeitada): dilui task-first;
   duplica caminhos de criação.
2. **`Task.worktree_id` direto** (rejeitada): força alocar worktree
   pra ideias no backlog; estado a sincronizar.

## Consequências

- Task é o objeto que UI manipula via kanban.
- Sessions acumulam histórico por task.
- 1 session ativa por task (lock server-side).
- Quick session preserva UX de F1 sem trair task-first.

## Referências

- ARCHITECTURE.md §1.2 (princípios), §3 (modelo de dados)
- Spec F4 §1, §3
```

- [ ] **Step 4: ADR-0013**

```markdown
# ADR-0013: Kanban unificado cross-project com filtros

- **Status:** Accepted
- **Data:** 2026-05-09
- **Decisores:** Marcos

## Contexto

Layout original do brainstorming F4 era kanban POR projeto (project
picker no topo, swap entre kanbans). Ao discutir, ficou claro que
trabalhar em múltiplos projetos simultaneamente é o caso real;
context-switching entre kanbans desorganiza fluxo.

## Decisão

Kanban único cross-project. Cada card mostra **chip colorido** com
nome do projeto (cor por hash determinístico do `project_id` em
paleta fixa de 8). Filtros multi-select no header (chips clicáveis)
permitem incluir/excluir projetos. Estado de filtros persiste em
`localStorage["jarvis.kanban.filters"]`. IDs ausentes silenciosamente
filtrados ao ler.

Projetos e worktrees ficam num **drawer lateral** acionado por
botão "Projetos ▾" — mantém UX existente de F1 sem ocupar tela.

## Alternativas

1. Kanban por projeto (rejeitada): força swap, perde contexto.
2. Kanban híbrido (badge global + per-project): scope creep.

## Consequências

- Schema/API independente de projeto (Task carrega `project_id`).
- Cor do chip não persiste no DB (derivada do id).
- Drawer encapsula complexidade de project/worktree mgmt.

## Referências

- Spec F4 §6.1, decisões #3, #11, #15, #17
```

- [ ] **Step 5: Atualizar ARCHITECTURE.md §3, §11, §13**

§3: adicionar `Task` ao modelo de dados; mostrar `Session.task_id`.

§11: marcar F4 como completo + atualizar entrega:

```markdown
| **F4 — Backlog kanban** | Kanban unificado cross-project; criar/mover/discardar tasks; iniciar sessão de uma task; quick session cria task implícita | `Task`, kanban UI 5 colunas com dnd-kit, `Session.task_id` NOT NULL, drawer pra projects/worktrees |
```

§13: adicionar 3 rows (ADR-0012, 0013, 0014).

- [ ] **Step 6: docs/adr/README.md**

Adicionar 2 rows:
```markdown
| [0012](0012-task-como-entidade-primaria.md) | Task como entidade primária; Session é filha obrigatória | Accepted | 2026-05-09 |
| [0013](0013-kanban-unificado-cross-project.md) | Kanban unificado cross-project com filtros multi-select | Accepted | 2026-05-09 |
```

(ADR-0014 já adicionado em F4.f.)

- [ ] **Step 7: Demo manual (do host, fora da jaula)**

Roteiro:
1. `JARVIS_RUNTIME=aijail uv run uvicorn orchestrator.main:app --port 8765`
2. `pnpm --dir ui run build`
3. Abrir `http://localhost:8765`
4. Adicionar projeto via drawer (criar `~/projects/X` git init)
5. Criar worktree
6. Criar task "Adicionar dark mode" via Backlog
7. Drag pra Backlog (mantém em ready) — testar drag inválido tipo Done → Backlog: snap-back + toast
8. Clicar no card → modal → "▶ Iniciar sessão" com worktree main
9. Terminal nativo abre; card foi pra In Progress
10. Quick session via drawer numa worktree feature/foo → task implícita aparece em In Progress
11. Filtrar por projeto X → task da feature/foo some
12. Reload da página → filtro permanece
13. Drag In Progress → Review → Done
14. Tentar deletar projeto → toast "Descarte as tasks…"

- [ ] **Step 8: Coverage final do projeto**

```bash
uv run pytest tests/unit tests/integration --cov=orchestrator --cov-report=term-missing --cov-fail-under=100
pnpm --dir ui exec vitest run --coverage
```
Expected: 100% Python; UI 100% nos arquivos novos.

- [ ] **Step 9: Code review final (Agent superpowers:code-reviewer)**

Dispatch reviewer com prompt: "Review entire F4 branch from b8f9e7b..HEAD. Verify against spec `docs/superpowers/specs/2026-05-09-f4-backlog-kanban-design.md`: every closed decision (#1-20) implemented; every test in §7.1-§7.4 exists; ARCHITECTURE.md §3/§11/§13 reflects new state; ADR-0012/0013/0014 follow ADR-0009/0010 format; no leftover `awaiting_approval` references; no leftover `ApprovalRequest` references."

Aplicar fixes finais antes do commit de fechamento.

- [ ] **Step 10: Commit final**

```bash
git add tests/e2e/test_kanban_e2e_flow.py ARCHITECTURE.md docs/adr/0012-task-como-entidade-primaria.md docs/adr/0013-kanban-unificado-cross-project.md docs/adr/README.md
git commit -m "$(cat <<'EOF'
feat(F4.l): E2E flows + ARCHITECTURE update + ADR-0012/0013 + demo

- E2E happy path + 5 fluxos de §7.4 do spec
- ADR-0012 documenta task-first como entidade primária
- ADR-0013 documenta decisão de kanban unificado cross-project
- ARCHITECTURE.md §3 inclui Task; §11 atualiza linha F4; §13
  adiciona rows ADR-0012/0013/0014
- README.md indexado

F4 completa. Próximo: F5 (mapa de worktrees) ou F9 (master session).
EOF
)"
```

---

## Encerramento — checklist final F4

- [ ] Todos os tests F2 e F1 pré-existentes passam (regressão zero)
- [ ] `uv run pytest tests/unit -q`: 100% verde
- [ ] `uv run pytest tests/integration -q`: 100% verde
- [ ] `pnpm --dir ui exec vitest run`: 100% verde
- [ ] `uv run pytest tests/e2e -v`: passa (do host)
- [ ] `uv run pytest --cov=orchestrator --cov-fail-under=100`
- [ ] Demo manual roteiro inteiro funciona
- [ ] `git log --oneline | head -20` mostra 12-13 commits F4.X consecutivos
- [ ] `gotchas.md` revisado — adicionar entry se algum aprendizado novo (ex: dnd-kit + Playwright drag quirks)
- [ ] Push da branch (`git push origin claude/fresh-start-cleanup-XDaHV`) — depende de fora da jaula
