# F5 — Mapa de worktrees + multi-repo + auto-create — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar mapa visual de worktrees + suporte a projetos multi-repo (gcb-hub) + criação/destruição de worktrees implícita via fluxo de tasks (auto-create no Iniciar; auto-delete no state→done/discarded).

**Architecture:** Project ganha N rows em nova tabela `repositories` (auto-detect via `_detect_repos`); `Worktree` migra de `project_id` → `repository_id` + `task_id` (NULL = órfã); `ClaudeSession` migra de `worktree_id` → `cwd` (parent dir contendo as N sub-worktrees em multi-repo, ou o próprio worktree em monorepo). `start_session` refatorado é atômico em 3 camadas (filesystem + DB + WS); cleanup é tolerante a falhas (orfana row em vez de bloquear transição).

**Tech Stack:**
- Backend: Python 3.13 + FastAPI + SQLAlchemy 2 async + Alembic + pydantic v2
- Frontend: Vite 6 + React 19 + TanStack Query + Zustand + @dnd-kit
- Sandbox: ai-jail externo
- Tests: pytest + pytest-asyncio + httpx + testcontainers + Playwright + Vitest

**Spec source of truth:** `docs/superpowers/specs/2026-05-09-f5-mapa-worktrees-design.md`

---

## File Structure

### Backend (novos)

| Arquivo | Responsabilidade |
|---|---|
| `alembic/versions/0004_repositories_and_cwd.py` | Migration: tabela `repositories`; refactor de `worktrees` (drop project_id, add repository_id + task_id); refactor de `sessions` (drop worktree_id, add cwd); `tasks.branch` |
| `orchestrator/core/repositories.py` | `RepoSpec`, `detect_repos`, `list_project_repositories`, `NoGitReposError` |
| `orchestrator/core/slug.py` | `slugify_for_branch`, `InvalidBranchSlugError` |
| `tests/unit/test_detect_repos.py` | Unit |
| `tests/unit/test_slugify_for_branch.py` | Unit |
| `tests/unit/test_repositories_crud.py` | Unit |
| `tests/unit/test_session_start_atomic.py` | Unit (FakeGitOps) |
| `tests/unit/test_session_start_re_iniciar.py` | Unit |
| `tests/unit/test_session_start_no_worktree_id.py` | Unit (signature) |
| `tests/unit/test_session_start_branch_clash.py` | Unit |
| `tests/unit/test_worktrees_cleanup_soft_fail.py` | Unit |
| `tests/unit/test_task_state_done_active_session_guard.py` | Unit |
| `tests/unit/test_ws_envelope_worktrees.py` | Unit |
| `tests/unit/test_task_branch_validation.py` | Unit |
| `tests/integration/test_migration_0004_roundtrip.py` | Integration (Alembic real) |
| `tests/integration/test_projects_create_detects_repos.py` | Integration |
| `tests/integration/test_repositories_in_projects_response.py` | Integration |
| `tests/integration/test_task_session_monorepo_flow.py` | Integration (real git) |
| `tests/integration/test_task_session_multi_repo_flow.py` | Integration (real git) |
| `tests/integration/test_task_session_re_iniciar.py` | Integration |
| `tests/integration/test_task_session_branch_clash_422.py` | Integration |
| `tests/integration/test_task_state_done_triggers_cleanup.py` | Integration |
| `tests/integration/test_task_state_done_blocked_active_session.py` | Integration |
| `tests/integration/test_cleanup_soft_fail_orphans.py` | Integration |
| `tests/integration/test_delete_orphan_worktree.py` | Integration |
| `tests/integration/test_external_worktree_appears_as_orphan.py` | Integration |
| `tests/integration/test_branch_override_field.py` | Integration |
| `docs/adr/0015-project-multi-repo-com-auto-detect.md` | ADR |
| `docs/adr/0016-multi-repo-1-sessao-cwd-shared.md` | ADR |
| `docs/adr/0017-worktree-detalhe-da-task-sem-create-ui.md` | ADR |

### Backend (modificados)

| Arquivo | Mudanças |
|---|---|
| `orchestrator/store/models.py` | Add `Repository`; refactor `Worktree` (drop project_id, add repository_id, task_id); add `Task.branch`; refactor `ClaudeSession` (drop worktree_id, add cwd) |
| `orchestrator/core/git.py` | Add `GitWorktreeOps` Protocol; add `SubprocessGitWorktreeOps` impl com `add`/`remove` |
| `orchestrator/core/projects.py` | `create_project` chama `detect_repos` + INSERT em repositories na mesma transaction |
| `orchestrator/core/sessions.py` | Refactor `start_session`: signature (drop worktree_id, add git: GitWorktreeOps), atomic 3-layer flow, _derive_cwd, rollback parcial |
| `orchestrator/core/tasks.py` | `update_task` ganha guards: TaskHasActiveSessionError em terminal-state; BranchImmutableAfterFirstSessionError em branch change pós-1ª-sessão; aceita `branch` param |
| `orchestrator/core/worktrees.py` | `list_project_worktrees` itera repositories + insere externas como órfãs; novas: `cleanup_task_worktrees`, `list_worktrees_for_task`, `list_orphan_worktrees`, `delete_worktree` |
| `orchestrator/api/projects.py` | POST /projects detecta repos + inclui em response; GET /projects inclui repositories |
| `orchestrator/api/tasks.py` | POST /tasks aceita branch; PATCH /tasks aceita branch + dispara cleanup em done/discarded; POST /tasks/{id}/sessions sem worktree_id (extra=forbid) |
| `orchestrator/api/worktrees.py` | DELETE /worktrees/{id} para órfãs |
| `orchestrator/events/envelope.py` | Add factories `worktree_created`, `worktree_removed`, `worktree_orphaned` |
| `orchestrator/main.py` | Wire `app.state.git_ops = SubprocessGitWorktreeOps()`; inject em handlers via Depends |
| `orchestrator/api/_deps.py` | Add `resolve_git_ops` Depends helper |
| `orchestrator/sandbox/aijail.py` | (possivel ajuste após F5.0 spike pra cobrir cwd com N sub-`.git`s) |

### Frontend (novos)

| Arquivo | Responsabilidade |
|---|---|
| `ui/src/lib/slug.ts` | Mirror client-side de `slugify_for_branch` (preview no placeholder) |
| `ui/src/lib/slug.test.ts` | Vitest |
| `ui/src/lib/useLocalStorage.ts` | Helper genérico `useLocalStorage<T>` (typed) |
| `ui/src/lib/useLocalStorage.test.ts` | Vitest |
| `ui/src/components/ProjectNode.tsx` | Projeto expandível com tasks ativos + órfãs |
| `ui/src/components/ProjectNode.test.tsx` | Vitest |
| `ui/src/components/TaskWorktreeGroup.tsx` | Header de task + worktrees como filhos |
| `ui/src/components/TaskWorktreeGroup.test.tsx` | Vitest |
| `ui/src/components/WorktreeRow.tsx` | 1 linha de worktree (path tooltip + ações) |
| `ui/src/components/WorktreeRow.test.tsx` | Vitest |
| `ui/src/components/OrphansGroup.tsx` | Sub-tree colapsável de órfãs |
| `ui/src/components/OrphansGroup.test.tsx` | Vitest |

### Frontend (modificados)

| Arquivo | Mudanças |
|---|---|
| `ui/src/lib/api.ts` | Types: `Repository`; `Project.repositories`; `Worktree.repository_id/repository_name/task_id/is_orphan`; `Task.branch`. Endpoints: `createTask`/`patchTask` aceitam `branch`; `startTaskSession(taskId)` sem worktreeId; `deleteWorktree` |
| `ui/src/lib/api.test.ts` | EXTEND: deleteWorktree + types changes |
| `ui/src/hooks/useSessionEvents.ts` | EXTEND: handlers `worktree.created/removed/orphaned` invalidam `queryKeys.worktrees(projectId)`; orphaned dispara toast |
| `ui/src/hooks/useSessionEvents.test.ts` | EXTEND |
| `ui/src/components/ProjectsDrawer.tsx` | REWRITE: container que renderiza N `<ProjectNode>`; remove inline `WorktreesInline` |
| `ui/src/components/ProjectsDrawer.test.tsx` | REWRITE |
| `ui/src/components/NewTaskForm.tsx` | Add `<details>Avançado ▾</details>` com campo `branch` + slug preview no placeholder |
| `ui/src/components/NewTaskForm.test.tsx` | EXTEND |
| `ui/src/components/TaskDetailModal.tsx` | Remove worktree picker; `▶ Iniciar` único; mostra `branch` (read-only após 1ª sessão); lista worktrees |
| `ui/src/components/TaskDetailModal.test.tsx` | EXTEND |

### Documentos (modificados)

| Arquivo | Mudanças |
|---|---|
| `ARCHITECTURE.md` | §3 (modelo de dados): add Repository, refatora Worktree e ClaudeSession; §11 marca F5 ✅; §13 adiciona ADR-0015/0016/0017 |
| `docs/adr/README.md` | Index ADRs novos |
| `gotchas.md` | Possivelmente #12 sobre lições aprendidas durante F5.0 spike |

---

## Pre-flight corrections (READ BEFORE EXECUTING)

### PFC-1 — `tests/conftest.py` auto-marker já em vigor (F4.m)

`tests/conftest.py` aplica markers via path. **Não declarar `pytestmark = pytest.mark.X` em arquivos novos** — é redundante e pode confundir. Os arquivos novos sob `tests/unit/` automaticamente recebem `pytest.mark.unit`; sob `tests/integration/` recebem `pytest.mark.integration`.

### PFC-2 — Padrão de integration test (sem fixtures globais novas)

Os tests de integration seguem o padrão estabelecido em `tests/integration/test_sessions_api.py` e `test_task_session_route.py` (post-F4.m): cada test cria seu próprio `AsyncClient` + seed via helpers existentes em `conftest.py`:

```python
from tests.integration.conftest import (
    FakeSessionRuntime,
    _create_project_and_worktree,
    _make_repo,
    _git,
)
```

Helpers existentes:
- `_git(cwd, *args)` — roda git via subprocess
- `_make_repo(parent, name="repo")` — cria repo bare git init -b main + initial commit
- `_create_project_and_worktree(client, repo)` — POST /projects + GET /worktrees, retorna `(pid, wid)`

**Para multi-repo F5 testes**, criar helper `_make_multi_repo(parent, sub_repos: list[str])` em `conftest.py` (no PFC-3 abaixo).

### PFC-3 — Helpers novos em `tests/integration/conftest.py`

Adicionar ao final de `tests/integration/conftest.py`:

```python
def _make_multi_repo(parent: Path, sub_repos: list[str], name: str = "multi-repo") -> Path:
    """Create umbrella dir with N sub-repos, each with its own .git.

    Used for F5 multi-repo project tests (gcb-hub-like).
    """
    base = parent / name
    base.mkdir()
    # NB: NO .git in base — that's the multi-repo signature
    for sub in sub_repos:
        sub_path = base / sub
        sub_path.mkdir()
        _git(sub_path, "init", "-b", "main")
        (sub_path / "f").write_text("x", encoding="utf-8")
        _git(sub_path, "add", ".")
        _git(sub_path, "-c", "commit.gpgsign=false", "commit", "-m", "init")
    return base
```

Adicionar como sub-step explícito da Task F5.a Step 0 (antes de tudo).

### PFC-4 — Production wiring de `git_ops` em main.py

`main.py::create_app` precisa wire `app.state.git_ops = SubprocessGitWorktreeOps()` (similar a `token_registry`, `ws_broadcaster`, etc). E `api/_deps.py` precisa novo `resolve_git_ops` que lê `request.app.state.git_ops`. Adicionar em F5.c (junto com a criação do Protocol).

### PFC-5 — Coverage gate (auto-marker pós F4.m)

O auto-marker em `tests/conftest.py` (F4.m) garante que tests novos sob `tests/unit/` e `tests/integration/` rodam mesmo com `-m "unit or integration"`. Coverage gate em `make coverage` deve continuar 100% após cada sub-task.

### PFC-6 — Pre-commit code review subagent

Cada commit final de cada sub-task (F5.a, F5.b, ..., F5.l) deve passar por code-reviewer subagent (`feature-dev:code-reviewer` ou `superpowers:code-reviewer`) **antes** do commit. Replica disciplina F4. Pula-se só com aprovação explícita.

### PFC-7 — F5.0 spike é blocker

A spike F5.0 valida ai-jail config com cwd contendo N sub-`.git`s. **Se falhar, NÃO prosseguir** pra F5.a até `sandbox/aijail.py` ser ajustado. Risco enumerado em §12 do spec; PFC-7 é o gate operacional.

### PFC-8 — `Worktree.repository_id` requer carga eager em queries de WS broadcast

`WsEvent.worktree_created` payload precisa de `project_id`, que está em `repository.project_id`. Em handler de F5.d (`start_session`) ao broadcast, **carregar repository via `await session.get(Repository, wt.repository_id)`** ANTES de fechar a session, ou usar `joinedload(Worktree.repository)`. Mais simples: passar `repo` (já em escopo do loop) pro factory:

```python
WsEvent.worktree_created(
    worktree_id=wt.id,
    project_id=repo.project_id,  # passa direto, evita re-fetch
    repository_id=repo.id,
    task_id=task_id,
    path=wt.path,
    branch=wt.branch,
)
```

### PFC-9 — `cwd` re-iniciar derivado é o parent dos worktrees

Em F5.d step 4 ("Has existing worktrees pra essa task?"), `cwd` é derivado como `Path(existing_worktrees[0].path).parent` para multi-repo, ou `Path(existing_worktrees[0].path)` para monorepo. Como distinguir? Pelo número de worktrees:

```python
existing = await list_worktrees_for_task(session, task_id)
if existing:
    if len(existing) == 1:
        cwd = Path(existing[0].path)  # monorepo: cwd = worktree path
    else:
        cwd = Path(existing[0].path).parent  # multi-repo: cwd = parent
```

Adicionar como helper `_derive_cwd_from_existing(worktrees) -> Path` em `core/sessions.py`.

### PFC-10 — Migration 0004 backfill de `Repository.name` em monorepo usa `project.name`

Em `_detect_repos`, monorepo retorna `RepoSpec(name=base_path.name, sub_path=".")`. `base_path.name` é o último componente do path (ex: `gcb-financeiro`). Para a migration backfill: usa `project.name` (campo do Project, não do path) pra ser consistente com o nome configurado pelo usuário, NÃO o basename do path. Pequena divergência: a função pure usa `base_path.name`; o migration backfill usa `project.name`. Documentar em `_detect_repos` docstring que essa diferença existe.

### PFC-11 — `os.getenv` em test_session_start tem que respeitar tmpdir

Tests que tocam filesystem (cwd existing, etc) devem usar `tmp_path` fixture. `_derive_cwd` usa `Path(project_path).parent` — em tests, `project.path` deve estar em `tmp_path`, garantindo isolamento.

### PFC-12 — UI: `slugify` no client espelha `slugify_for_branch` Python 1:1

`ui/src/lib/slug.ts` deve produzir o MESMO output que `core/slug.py::slugify_for_branch` para qualquer input válido. Testar paridade no Vitest com inputs comuns + edge cases (unicode acentos, "...", "Refactor: HTTP/2"). Divergência = bug. Documentar isso no docstring de ambos.

### PFC-13 — `lib/api.test.ts` deve testar `extra=forbid` rejeição

Adicionar test que `startTaskSession(taskId)` rejeita silenciosamente se passar `worktree_id` (não compila por TypeScript), mas testar via raw fetch que servidor retorna 422 — em integration test (não vitest).

---

## Disciplina

- **Decomposição**: cada Task abaixo = uma sub-fase F5.X. Ordem **obrigatória** F5.0 → F5.l (dependências de migração + tipos + componentes). F5.0 é spike validatório.
- **Comprometimento**: cada sub-task termina com 1 commit dedicado (`feat(F5.X): ...`).
- **TDD**: red → green → refactor em cada sub-task. Sem código de produção sem teste falhando antes.
- **Cobertura**: `make coverage` 100% pós cada sub-task. Auto-marker da F4.m garante que arquivos novos rodam.
- **Pre-commit code review**: dispatch subagent antes de cada commit (PFC-6).
- **Coverage gate**: 100% mantido sub-task a sub-task.

---

## Task 0 — F5.0: Spike `git worktree add` em multi-repo + ai-jail config check

**Objetivo:** validar que ai-jail consegue spawnar Claude com cwd contendo N sub-`.git`s sem violar capabilities ou bloquear acesso. Spike fast-fail antes de qualquer schema mudar.

**Files:**
- Spike (não commitado): `/tmp/f5-spike-multi-repo/` — projeto multi-repo de teste

- [ ] **Step 0: Entender a invocação real de ai-jail**

Ler:
- `orchestrator/sandbox/aijail.py` — em particular linhas 102-117. A invocação de produção é `inner = ["ai-jail", "run", "--", "claude"]` rodada com `cwd=str(worktree)` (ai-jail lê config do `.ai-jail` no cwd, NÃO via CLI flags).
- `.ai-jail` no root do projeto J-arvs — é o exemplo de config: `command`, `rw_maps`, `ro_maps`, `hide_dotdirs`, `mask`, `allow_tcp_ports`.
- `https://github.com/akitaonrails/ai-jail` README pra confirmar formato do `.ai-jail` e behavior (quais paths são bind-mounted, semântica de isolamento de rede).

**Sem ler isto, o spike vai usar flags inventadas** (eg. `--rw host:container` Docker-style que não existe).

- [ ] **Step 1: Setup local de teste — multi-repo synthetic**

```bash
mkdir -p /tmp/f5-spike/multi-repo/{backend,frontend}
cd /tmp/f5-spike/multi-repo/backend && git init -b main && echo "x" > f && git add . && git -c commit.gpgsign=false commit -m init
cd /tmp/f5-spike/multi-repo/frontend && git init -b main && echo "y" > g && git add . && git -c commit.gpgsign=false commit -m init
```

- [ ] **Step 2: Manual `git worktree add` em ambos os sub-repos pro mesmo branch**

```bash
mkdir -p /tmp/f5-spike/multi-repo--feature-test
git -C /tmp/f5-spike/multi-repo/backend worktree add /tmp/f5-spike/multi-repo--feature-test/backend -b feature-test
git -C /tmp/f5-spike/multi-repo/frontend worktree add /tmp/f5-spike/multi-repo--feature-test/frontend -b feature-test
ls -la /tmp/f5-spike/multi-repo--feature-test/
# Expected: backend/  frontend/  cada um com `.git` (arquivo pointer, não dir)
cat /tmp/f5-spike/multi-repo--feature-test/backend/.git
# Expected: gitdir: /tmp/f5-spike/multi-repo/backend/.git/worktrees/backend
```

Esse `.git` arquivo aponta pra dir **fora** do cwd parent — é a parte crítica. Pra `git status` funcionar dentro da jaula, esse caminho precisa estar acessível.

- [ ] **Step 3: Criar `.ai-jail` config no cwd da spike e tentar git status sem mounts extras**

```bash
cat > /tmp/f5-spike/multi-repo--feature-test/.ai-jail <<'EOF'
command = ["bash", "-c", "echo === backend === && cd backend && git status && echo === frontend === && cd ../frontend && git status"]
rw_maps = []
ro_maps = []
hide_dotdirs = []
mask = []
allow_tcp_ports = []
EOF

cd /tmp/f5-spike/multi-repo--feature-test
ai-jail run --
```

Expected: PROVAVELMENTE FALHA com "fatal: not a git repository" porque o `.git` pointer aponta pra `/tmp/f5-spike/multi-repo/backend/.git/worktrees/backend` que não está montado.

- [ ] **Step 4: Adicionar rw_maps pros .git originais e re-tentar**

```bash
cat > /tmp/f5-spike/multi-repo--feature-test/.ai-jail <<'EOF'
command = ["bash", "-c", "echo === backend === && cd backend && git status && echo === frontend === && cd ../frontend && git status"]
rw_maps = [
    "/tmp/f5-spike/multi-repo/backend/.git",
    "/tmp/f5-spike/multi-repo/frontend/.git",
]
ro_maps = []
hide_dotdirs = []
mask = []
allow_tcp_ports = []
EOF

cd /tmp/f5-spike/multi-repo--feature-test
ai-jail run --
```

Expected (caso ideal): ambos `git status` rodam OK ("On branch feature-test...").

- [ ] **Step 5: Identificar mudanças necessárias em `sandbox/aijail.py`**

Conforme resultado:
- **Step 4 OK**: F5 precisa que `start_session` gere o `.ai-jail` config dinamicamente com `rw_maps` apontando pros `.git` paths originais de cada sub-repo. Adicionar como sub-step de F5.d.
- **Step 4 falha**: investigar mais — talvez precise mount do parent dir do .git, talvez precise hide_dotdirs config diferente. Documentar em gotcha + ajustar plano.
- **Step 3 já OK** (sem rw_maps extras): aijail tem alguma magic de auto-mount que cobriu; documentar como ele faz e proceder sem mudança.

- [ ] **Step 6: Cleanup spike**

```bash
git -C /tmp/f5-spike/multi-repo/backend worktree remove --force /tmp/f5-spike/multi-repo--feature-test/backend
git -C /tmp/f5-spike/multi-repo/frontend worktree remove --force /tmp/f5-spike/multi-repo--feature-test/frontend
rm -rf /tmp/f5-spike
```

- [ ] **Step 7: Decisão**

```
Se Step 3 OK (sem rw_maps): prosseguir pra F5.a SEM mudanças em aijail.py.
Se Step 4 OK (com rw_maps): F5.d ganha geração de `.ai-jail` dinâmico; documentar em gotcha #12.
Se Step 4 falha sem mitigação: pausar e revisar arquitetura — multi-repo pode exigir mudança maior em ai-jail config ou trocar pra mounts customizados.
```

**Sem commit** — spike é validação manual; resultado documentado em `gotchas.md` apenas se mitigação for necessária.

---

## Task 1 — F5.a: Migration 0004 + `Repository` model + roundtrip test

**Objetivo:** schema novo + migration determinística + roundtrip test que prova upgrade/downgrade.

**Files:**
- Create: `alembic/versions/0004_repositories_and_cwd.py`
- Modify: `orchestrator/store/models.py`
- Create: `tests/integration/test_migration_0004_roundtrip.py`
- Modify: `tests/integration/conftest.py` (add `_make_multi_repo` helper)

- [ ] **Step 1: Add `_make_multi_repo` helper em conftest.py**

Adicionar no final de `tests/integration/conftest.py` (após `_create_project_and_worktree`):

```python
def _make_multi_repo(parent: Path, sub_repos: list[str], name: str = "multi-repo") -> Path:
    """Create umbrella dir with N sub-repos, each with its own .git.
    Used for F5 multi-repo project tests (gcb-hub-like).
    NB: no .git in `parent/<name>` itself — that's the multi-repo signature.
    """
    base = parent / name
    base.mkdir()
    for sub in sub_repos:
        sub_path = base / sub
        sub_path.mkdir()
        _git(sub_path, "init", "-b", "main")
        (sub_path / "f").write_text("x", encoding="utf-8")
        _git(sub_path, "add", ".")
        _git(sub_path, "-c", "commit.gpgsign=false", "commit", "-m", "init")
    return base
```

- [ ] **Step 2: Write failing test_migration_0004_roundtrip.py**

```python
"""Migration 0004: tabela repositories + worktrees.repository_id/task_id +
sessions.cwd + tasks.branch.

Seed F4 (1 monorepo + 1 multi-repo project sem worktrees ainda) →
upgrade → asserts; downgrade → asserts (best-effort).
"""
from pathlib import Path

import pytest
from alembic.command import upgrade, downgrade
from alembic.config import Config
from sqlalchemy import create_engine, text

from tests.integration.conftest import _make_repo, _make_multi_repo


def _alembic_cfg(db_url: str) -> Config:
    repo_root = Path(__file__).resolve().parents[2]
    cfg = Config(str(repo_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(repo_root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_upgrade_0003_to_0004_creates_repositories_and_migrates_worktrees(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "f4.db"
    db_url = f"sqlite:///{db_path}"
    cfg = _alembic_cfg(db_url)

    # Seed at F4 (revision 0003)
    upgrade(cfg, "0003")

    monorepo = _make_repo(tmp_path, "mono")
    multirepo_base = _make_multi_repo(tmp_path, ["backend", "frontend"], name="multi")

    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO projects (id, name, path, created_at) VALUES "
            "('p1','mono',:mp,'2026-01-01'),"
            "('p2','multi',:mr,'2026-01-01')"
        ), {"mp": str(monorepo), "mr": str(multirepo_base)})
        # F4 monorepo já tem worktree
        conn.execute(text(
            "INSERT INTO worktrees (id, project_id, path, branch) VALUES "
            "('w1','p1',:wp,'main')"
        ), {"wp": str(monorepo)})
        # Sessions com worktree_id
        conn.execute(text(
            "INSERT INTO tasks (id, project_id, title, description, state, created_at, updated_at) "
            "VALUES ('t1','p1','Mono task','','in_progress','2026-01-01','2026-01-01')"
        ))
        conn.execute(text(
            "INSERT INTO sessions (id, worktree_id, task_id, status, started_at) "
            "VALUES ('s1','w1','t1','executing','2026-01-01')"
        ))

    # Upgrade
    upgrade(cfg, "0004")

    with engine.begin() as conn:
        # repositories created
        repos = conn.execute(text("SELECT project_id, name, sub_path FROM repositories ORDER BY name")).all()
        assert len(repos) == 3  # mono(1) + multi(2)
        # mono → 1 row sub_path="."
        mono_repos = [r for r in repos if r.project_id == "p1"]
        assert len(mono_repos) == 1
        assert mono_repos[0].sub_path == "."
        # multi → 2 rows backend + frontend
        multi_repos = sorted(r.sub_path for r in repos if r.project_id == "p2")
        assert multi_repos == ["backend", "frontend"]

        # worktrees.repository_id populado
        wt_repo = conn.execute(text("SELECT repository_id FROM worktrees WHERE id='w1'")).scalar_one()
        assert wt_repo == mono_repos[0].id if isinstance(mono_repos[0], tuple) else None  # adjust to row obj
        # worktree task_id is NULL (orphan no F4)
        wt_task = conn.execute(text("SELECT task_id FROM worktrees WHERE id='w1'")).scalar_one()
        assert wt_task is None
        # worktree.project_id NÃO existe mais
        cols = conn.execute(text("PRAGMA table_info(worktrees)")).all()
        names = {c.name for c in cols}
        assert "project_id" not in names
        assert "repository_id" in names
        assert "task_id" in names

        # sessions.cwd backfilled
        cwd = conn.execute(text("SELECT cwd FROM sessions WHERE id='s1'")).scalar_one()
        assert cwd == str(monorepo)
        # sessions.worktree_id NÃO existe mais
        cols_s = conn.execute(text("PRAGMA table_info(sessions)")).all()
        names_s = {c.name for c in cols_s}
        assert "worktree_id" not in names_s
        assert "cwd" in names_s

        # tasks.branch existe (NULL pra row legacy)
        cols_t = conn.execute(text("PRAGMA table_info(tasks)")).all()
        assert "branch" in {c.name for c in cols_t}


def test_downgrade_0004_to_0003_best_effort(tmp_path: Path) -> None:
    """Downgrade is lossy by design (multi-repo cwd doesn't map back).
    Roundtrip just needs to not crash and restore F4 schema shape."""
    db_path = tmp_path / "round.db"
    db_url = f"sqlite:///{db_path}"
    cfg = _alembic_cfg(db_url)

    upgrade(cfg, "0003")
    monorepo = _make_repo(tmp_path, "mono")
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO projects (id, name, path, created_at) VALUES "
            "('p1','mono',:mp,'2026-01-01')"
        ), {"mp": str(monorepo)})

    upgrade(cfg, "0004")
    downgrade(cfg, "0003")

    with engine.begin() as conn:
        # Schema F4 shape restored
        cols_w = conn.execute(text("PRAGMA table_info(worktrees)")).all()
        names_w = {c.name for c in cols_w}
        assert "project_id" in names_w
        assert "repository_id" not in names_w
        cols_s = conn.execute(text("PRAGMA table_info(sessions)")).all()
        names_s = {c.name for c in cols_s}
        assert "worktree_id" in names_s
        assert "cwd" not in names_s
```

- [ ] **Step 3: Run test, verify FAIL**

```bash
unset VIRTUAL_ENV && uv run python -m pytest tests/integration/test_migration_0004_roundtrip.py -v
```
Expected: FAIL — `alembic.script.ScriptDirectory.get_revision` levanta porque revisão 0004 não existe.

- [ ] **Step 4: Add `Repository` model em `store/models.py`**

```python
class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sub_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("project_id", "sub_path", name="uq_repo_project_subpath"),
    )
```

Imports adicionais:
```python
from sqlalchemy import UniqueConstraint
```

- [ ] **Step 5: Modify `Worktree` em `store/models.py`**

```python
class Worktree(Base):
    __tablename__ = "worktrees"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    repository_id: Mapped[str] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[str | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
    path: Mapped[str] = mapped_column(String(1024), unique=True)
    branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
```

Remove `project_id` line.

- [ ] **Step 6: Modify `Task` em `store/models.py`**

Adicionar campo `branch`:
```python
class Task(Base):
    # ... existing fields ...
    branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
```

- [ ] **Step 7: Modify `ClaudeSession` em `store/models.py`**

```python
class ClaudeSession(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("tasks.id", ondelete="RESTRICT"), nullable=False
    )
    cwd: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[str] = mapped_column(String(32))
    pid: Mapped[int | None] = mapped_column(nullable=True)
    jail_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    transcript_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    started_at: Mapped[datetime] = mapped_column(default=_now)
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)
    hook_token: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True)
    last_hook_at: Mapped[datetime | None] = mapped_column(nullable=True)
```

Remove `worktree_id` line.

- [ ] **Step 8: Write migration `alembic/versions/0004_repositories_and_cwd.py`**

```python
"""repositories + worktrees.repository_id/task_id + sessions.cwd + tasks.branch

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-09
"""
from datetime import datetime, UTC
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa
from alembic import op


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _detect_repos_inline(base_path: str) -> list[tuple[str, str]]:
    """Inline copy of core/repositories.detect_repos for migration use.
    Returns list of (name, sub_path)."""
    base = Path(base_path)
    if not base.is_dir():
        return []
    if (base / ".git").is_dir():
        return [(base.name, ".")]
    sub = sorted(
        c.name for c in base.iterdir()
        if c.is_dir() and (c / ".git").is_dir()
    )
    return [(s, s) for s in sub]


def upgrade() -> None:
    # 1. Create repositories table
    op.create_table(
        "repositories",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.String(32),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("sub_path", sa.String(1024), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("project_id", "sub_path", name="uq_repo_project_subpath"),
    )

    # 2. Backfill: pra cada Project, detectar repos + insert
    bind = op.get_bind()
    projects = bind.execute(sa.text("SELECT id, name, path FROM projects")).all()
    now = datetime.now(UTC)
    project_to_repo_id: dict[str, str] = {}
    import logging
    _mig_log = logging.getLogger("alembic.runtime.migration")
    for proj in projects:
        repos = _detect_repos_inline(proj.path)
        if not repos:
            # Sem .git no path — projeto pode ter sido renomeado/deletado entre
            # F4 e F5. Criar 1 row "." pra não quebrar o backfill (worktrees
            # existentes precisam de algum repository_id pro NOT NULL passar).
            # Loggar WARNING pra que o usuário veja na saída do alembic upgrade.
            _mig_log.warning(
                "project '%s' (id=%s) at path '%s' has no .git — fallback to "
                "1 dummy repository row (sub_path='.'). User should reconcile "
                "after migration.",
                proj.name, proj.id, proj.path,
            )
            repos = [(proj.name, ".")]
        for name, sub_path in repos:
            rid = uuid4().hex
            bind.execute(sa.text(
                "INSERT INTO repositories (id, project_id, name, sub_path, created_at) "
                "VALUES (:id, :pid, :name, :sub, :ts)"
            ), {"id": rid, "pid": proj.id, "name": name, "sub": sub_path, "ts": now})
            # Pra monorepo (1 row), guardar pra usar no backfill de worktrees
            if sub_path == ".":
                project_to_repo_id[proj.id] = rid

    # 3. ALTER worktrees: add repository_id + task_id (nullable inicialmente)
    with op.batch_alter_table("worktrees") as batch:
        batch.add_column(sa.Column("repository_id", sa.String(32), nullable=True))
        batch.add_column(sa.Column("task_id", sa.String(32), nullable=True))

    # 4. Backfill worktrees.repository_id (F4 schema só tem monorepo)
    bind.execute(sa.text(
        "UPDATE worktrees SET repository_id = ("
        "  SELECT r.id FROM repositories r "
        "  WHERE r.project_id = worktrees.project_id LIMIT 1"
        ")"
    ))

    # 5. ALTER worktrees: NOT NULL + FKs + drop project_id
    with op.batch_alter_table("worktrees") as batch:
        batch.alter_column("repository_id", existing_type=sa.String(32), nullable=False)
        batch.create_foreign_key(
            "fk_wt_repository", "repositories", ["repository_id"], ["id"],
            ondelete="CASCADE",
        )
        batch.create_foreign_key(
            "fk_wt_task", "tasks", ["task_id"], ["id"], ondelete="SET NULL",
        )
        batch.drop_column("project_id")

    # 6. ALTER tasks: add branch
    with op.batch_alter_table("tasks") as batch:
        batch.add_column(sa.Column("branch", sa.String(255), nullable=True))

    # 7. ALTER sessions: add cwd (nullable)
    with op.batch_alter_table("sessions") as batch:
        batch.add_column(sa.Column("cwd", sa.String(1024), nullable=True))

    # 8. Backfill sessions.cwd
    bind.execute(sa.text(
        "UPDATE sessions SET cwd = ("
        "  SELECT path FROM worktrees WHERE worktrees.id = sessions.worktree_id"
        ")"
    ))

    # 9. ALTER sessions: NOT NULL + drop worktree_id
    with op.batch_alter_table("sessions") as batch:
        batch.alter_column("cwd", existing_type=sa.String(1024), nullable=False)
        batch.drop_column("worktree_id")


def downgrade() -> None:
    """Best-effort downgrade. Multi-repo data is lossy:
    sessions of multi-repo tasks (cwd is parent of N worktrees) cannot
    be perfectly mapped to a single worktree_id. Picks any worktree
    of the same task as fallback. Columns added in upgrade are dropped.
    """
    bind = op.get_bind()

    # Add worktree_id back to sessions
    with op.batch_alter_table("sessions") as batch:
        batch.add_column(sa.Column("worktree_id", sa.String(32), nullable=True))

    # Backfill: pick any worktree of the session's task
    bind.execute(sa.text(
        "UPDATE sessions SET worktree_id = ("
        "  SELECT id FROM worktrees WHERE task_id = sessions.task_id LIMIT 1"
        ")"
    ))

    with op.batch_alter_table("sessions") as batch:
        batch.create_foreign_key(
            "fk_sess_wt", "worktrees", ["worktree_id"], ["id"], ondelete="RESTRICT",
        )
        batch.alter_column("worktree_id", nullable=False)
        batch.drop_column("cwd")

    # Drop tasks.branch
    with op.batch_alter_table("tasks") as batch:
        batch.drop_column("branch")

    # Restore worktrees.project_id
    with op.batch_alter_table("worktrees") as batch:
        batch.add_column(sa.Column("project_id", sa.String(32), nullable=True))

    bind.execute(sa.text(
        "UPDATE worktrees SET project_id = ("
        "  SELECT project_id FROM repositories WHERE repositories.id = worktrees.repository_id"
        ")"
    ))

    with op.batch_alter_table("worktrees") as batch:
        batch.alter_column("project_id", nullable=False)
        batch.drop_constraint("fk_wt_repository", type_="foreignkey")
        batch.drop_constraint("fk_wt_task", type_="foreignkey")
        batch.create_foreign_key(
            "fk_wt_project", "projects", ["project_id"], ["id"], ondelete="RESTRICT",
        )
        batch.drop_column("repository_id")
        batch.drop_column("task_id")

    # Drop repositories
    op.drop_table("repositories")
```

- [ ] **Step 9: Run test, verify PASS**

```bash
unset VIRTUAL_ENV && uv run python -m pytest tests/integration/test_migration_0004_roundtrip.py -v
```
Expected: PASS (2 testes).

- [ ] **Step 10: Run full Python coverage gate**

```bash
unset VIRTUAL_ENV && uv run python -m pytest tests/unit tests/integration -m "unit or integration" --cov=orchestrator --cov-fail-under=100
```
Expected: 100%. Se falha, ver missing lines.

**Nota:** os testes de integração de F4 que tocam `models.Worktree.project_id` ou `Session.worktree_id` agora **vão quebrar** — esses são consertados na F5.d/F5.f. Por enquanto, F5.a deve ser commitada com tests F4 quebrando? **NÃO.** F5.a só commita migration + models; tests F4 ainda passam contra revision 0003 (Alembic é controlado em-test). Os testes que quebram são os que FAZEM `Worktree(project_id=...)` direto no SQLAlchemy — esses precisam acompanhar a refactoração já em F5.a.

- [ ] **Step 10b: Atualizar testes F4 que usam `Worktree(project_id=...)` ou `ClaudeSession(worktree_id=...)`**

Search:
```bash
grep -rln "Worktree(project_id\|worktree_id=\|\.worktree_id" tests/ orchestrator/
```

Cada hit precisa adaptar para construir via `Repository` row primeiro. Para os testes F4 que usam `_create_project_and_worktree`, o helper continua funcionando porque vai pela API (que será atualizada em F5.g). Os tests que usam SQLAlchemy direto precisam ajustar.

**Lista completa de hits esperados** (`grep` confirmado em F4.m):

Tests:
- `tests/unit/test_session_token_lifecycle.py`
- `tests/unit/test_session_per_task_lock.py`
- `tests/unit/test_session_update_status.py`
- `tests/unit/test_quick_session_creates_task.py`
- `tests/unit/test_task_auto_transition.py`
- `tests/integration/test_db_roundtrip.py`
- `tests/integration/test_hooks_routes.py`
- `tests/integration/test_ws_endpoint.py`

Production code (refatorado na F5.d/F5.f, NÃO neste step):
- `orchestrator/api/sessions.py` (se ainda existir)
- `orchestrator/api/tasks.py`
- `orchestrator/core/sessions.py`
- `orchestrator/core/worktrees.py`

Pra cada test: substituir `Worktree(project_id=p.id, path=...)` por:
```python
repo = Repository(project_id=p.id, name=p.name, sub_path=".")
session.add(repo)
await session.flush()
wt = Worktree(repository_id=repo.id, task_id=None, path=..., branch=...)
session.add(wt)
```

E onde usa `ClaudeSession(worktree_id=wt.id, task_id=...)`: substituir por `cwd=str(wt_path)`.

- [ ] **Step 11: Re-run coverage gate**

```bash
unset VIRTUAL_ENV && uv run python -m pytest tests/unit tests/integration -m "unit or integration" --cov=orchestrator --cov-fail-under=100
```
Expected: 100% verde.

- [ ] **Step 12: Code review subagent**

Dispatch `feature-dev:code-reviewer` com o diff pra revisar:
- Migration logic determinístico (passo 4 do upgrade)
- Downgrade lossy documentado
- Models alinhados com spec

- [ ] **Step 13: Commit**

```bash
git add alembic/versions/0004_repositories_and_cwd.py orchestrator/store/models.py tests/integration/conftest.py tests/integration/test_migration_0004_roundtrip.py tests/unit/test_*.py
git commit -m "$(cat <<'EOF'
feat(F5.a): migration 0004 + Repository model + worktrees/sessions refactor

- Nova tabela repositories (project_id FK CASCADE; UNIQUE proj+sub_path)
- Worktree: drop project_id, add repository_id (CASCADE) + task_id (SET NULL, nullable=órfã)
- ClaudeSession: drop worktree_id, add cwd (parent dir em multi-repo)
- Task.branch: novo (override do auto-slug)
- Migration 0004 faz backfill determinístico (F4 só monorepo, 1 project = 1 repo row)
- Downgrade best-effort com docstring sobre data loss
- Helper _make_multi_repo em conftest.py

Tests F4 que tocavam Worktree.project_id ou ClaudeSession.worktree_id
ajustados para o novo schema.

Refs: spec §5
EOF
)"
```

---

## Task 2 — F5.b: `core/repositories.py` + `detect_repos`

**Objetivo:** pure function `detect_repos` + queries básicas pra `Repository`.

**Files:**
- Create: `orchestrator/core/repositories.py`
- Create: `tests/unit/test_detect_repos.py`
- Create: `tests/unit/test_repositories_crud.py`

- [ ] **Step 1: Write failing test_detect_repos.py**

```python
from pathlib import Path

import pytest

from orchestrator.core.repositories import (
    NoGitReposError,
    RepoSpec,
    detect_repos,
)


def _git_init(d: Path) -> None:
    import subprocess
    subprocess.run(["git", "-C", str(d), "init", "-b", "main"], check=True, capture_output=True)


def test_monorepo_returns_single_dot(tmp_path: Path) -> None:
    _git_init(tmp_path)
    result = detect_repos(tmp_path)
    assert result == [RepoSpec(name=tmp_path.name, sub_path=".")]


def test_multi_repo_lists_subdirs_alphabetically(tmp_path: Path) -> None:
    base = tmp_path / "multi"
    base.mkdir()
    for sub in ["frontend", "backend", "docs"]:
        d = base / sub
        d.mkdir()
        _git_init(d)
    result = detect_repos(base)
    assert result == [
        RepoSpec(name="backend", sub_path="backend"),
        RepoSpec(name="docs", sub_path="docs"),
        RepoSpec(name="frontend", sub_path="frontend"),
    ]


def test_no_repos_raises(tmp_path: Path) -> None:
    base = tmp_path / "empty"
    base.mkdir()
    with pytest.raises(NoGitReposError):
        detect_repos(base)


def test_path_does_not_exist_raises(tmp_path: Path) -> None:
    with pytest.raises(NoGitReposError):
        detect_repos(tmp_path / "nope")


def test_submodule_dot_git_as_file_is_ignored(tmp_path: Path) -> None:
    base = tmp_path / "with_submod"
    base.mkdir()
    sub = base / "submod"
    sub.mkdir()
    # .git as file (submodule pattern)
    (sub / ".git").write_text("gitdir: ../.git/modules/submod", encoding="utf-8")
    with pytest.raises(NoGitReposError):
        detect_repos(base)


def test_dot_git_at_root_takes_precedence_over_subdirs(tmp_path: Path) -> None:
    """If both base/.git/ AND base/sub/.git/ exist, base wins (monorepo)."""
    _git_init(tmp_path)
    sub = tmp_path / "embedded"
    sub.mkdir()
    _git_init(sub)
    result = detect_repos(tmp_path)
    assert result == [RepoSpec(name=tmp_path.name, sub_path=".")]
```

- [ ] **Step 2: Run, verify FAIL**

```bash
unset VIRTUAL_ENV && uv run python -m pytest tests/unit/test_detect_repos.py -v
```
Expected: FAIL — `ImportError: cannot import 'detect_repos' from 'orchestrator.core.repositories'`.

- [ ] **Step 3: Implement `core/repositories.py`**

```python
"""Repository discovery and queries.

A Project may map to N git repositories:
- Monorepo: 1 Repository row with sub_path="."
- Multi-repo (umbrella): N Repository rows, each pointing to a subdir

`detect_repos` is the auto-detection entry: it scans `base_path` and
returns the list of repos found. Used at add-project time and in
migration 0004 backfill.

NB on naming: for monorepo, RepoSpec.name = base_path.name (the last
path component). For migration backfill, callers may prefer to use
project.name (the user-configured name) instead — the Repository row
in DB stores whatever the caller chose.
"""
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.store.models import Repository


class NoGitReposError(Exception):
    """Raised when detect_repos finds no .git directory at root or 1 level deep."""


@dataclass(frozen=True)
class RepoSpec:
    name: str
    sub_path: str


def detect_repos(base_path: Path) -> list[RepoSpec]:
    """Detect git repositories within ``base_path``.

    Algorithm:
    1. If ``base_path/.git/`` exists (directory, not file): monorepo.
       Return ``[RepoSpec(name=base_path.name, sub_path=".")]``.
    2. Else, scan immediate children. Each child with ``child/.git/``
       (directory) becomes a sub-repo. Returned alphabetically by name.
    3. Empty: raise ``NoGitReposError``.

    Submodules (where ``.git`` is a *file* pointing elsewhere) are
    skipped because they are not independent repositories.
    """
    if not base_path.is_dir():
        raise NoGitReposError(f"path is not a directory: {base_path}")
    if (base_path / ".git").is_dir():
        return [RepoSpec(name=base_path.name, sub_path=".")]
    sub_repos = [
        RepoSpec(name=child.name, sub_path=child.name)
        for child in sorted(base_path.iterdir())
        if child.is_dir() and (child / ".git").is_dir()
    ]
    if not sub_repos:
        raise NoGitReposError(
            f"no .git dir found in {base_path} or 1 level below"
        )
    return sub_repos


async def list_project_repositories(
    session: AsyncSession, project_id: str
) -> Sequence[Repository]:
    """Returns repositories of a project ordered by sub_path ASC."""
    result = await session.execute(
        select(Repository)
        .where(Repository.project_id == project_id)
        .order_by(Repository.sub_path)
    )
    return result.scalars().all()
```

- [ ] **Step 4: Run test_detect_repos.py, verify PASS**

```bash
unset VIRTUAL_ENV && uv run python -m pytest tests/unit/test_detect_repos.py -v
```
Expected: 6 PASS.

- [ ] **Step 5: Write test_repositories_crud.py**

```python
from pathlib import Path

import pytest

from orchestrator.core.repositories import list_project_repositories
from orchestrator.store.database import Database
from orchestrator.store.models import Project, Repository


@pytest.mark.asyncio
async def test_list_project_repositories_orders_by_sub_path(tmp_path: Path) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/r.db")
    await db.bootstrap()
    async with db.session() as s:
        p = Project(name="x", path=str(tmp_path))
        s.add(p)
        await s.flush()
        s.add(Repository(project_id=p.id, name="frontend", sub_path="frontend"))
        s.add(Repository(project_id=p.id, name="backend", sub_path="backend"))
        await s.commit()

        repos = await list_project_repositories(s, p.id)
        assert [r.sub_path for r in repos] == ["backend", "frontend"]
```

- [ ] **Step 6: Run test_repositories_crud.py, verify PASS**

```bash
unset VIRTUAL_ENV && uv run python -m pytest tests/unit/test_repositories_crud.py -v
```
Expected: PASS.

- [ ] **Step 7: Coverage gate**

```bash
unset VIRTUAL_ENV && uv run python -m pytest tests/unit tests/integration -m "unit or integration" --cov=orchestrator --cov-fail-under=100
```

- [ ] **Step 8: Code review subagent + Commit**

```bash
git add orchestrator/core/repositories.py tests/unit/test_detect_repos.py tests/unit/test_repositories_crud.py
git commit -m "feat(F5.b): core/repositories with detect_repos + list_project_repositories"
```

---

## Task 3 — F5.c: `core/git.py` extension — `GitWorktreeOps` Protocol + impl

**Objetivo:** seam de teste pra git ops; impl real via subprocess; helpers pra add/remove/list.

**Files:**
- Modify: `orchestrator/core/git.py`
- Create: `tests/unit/test_git_worktree_ops.py`
- Modify: `orchestrator/main.py` (wire `app.state.git_ops`)
- Modify: `orchestrator/api/_deps.py` (add `resolve_git_ops`)

- [ ] **Step 1: Write failing test_git_worktree_ops.py**

```python
import asyncio
import subprocess
from pathlib import Path

import pytest

from orchestrator.core.git import (
    GitWorktreeError,
    SubprocessGitWorktreeOps,
)


def _make_repo(tmp_path: Path, name: str = "repo") -> Path:
    repo = tmp_path / name
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-b", "main"],
                   check=True, capture_output=True)
    (repo / "f").write_text("x")
    subprocess.run(["git", "-C", str(repo), "add", "."],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "-c", "commit.gpgsign=false",
                    "commit", "-m", "init"],
                   check=True, capture_output=True,
                   env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e",
                        "PATH": __import__("os").environ["PATH"]})
    return repo


@pytest.mark.asyncio
async def test_add_creates_worktree_with_new_branch(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    ops = SubprocessGitWorktreeOps()
    target = tmp_path / "wt"
    await ops.add(repo, target, "feature/x")
    assert target.is_dir()
    assert (target / ".git").exists()  # file pointer in worktree


@pytest.mark.asyncio
async def test_add_failing_branch_existing_raises(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    ops = SubprocessGitWorktreeOps()
    target = tmp_path / "wt"
    await ops.add(repo, target, "feature/x")
    target2 = tmp_path / "wt2"
    with pytest.raises(GitWorktreeError):
        await ops.add(repo, target2, "feature/x")  # branch already exists


@pytest.mark.asyncio
async def test_remove_force_removes_worktree(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    ops = SubprocessGitWorktreeOps()
    target = tmp_path / "wt"
    await ops.add(repo, target, "feature/x")
    await ops.remove(repo, target, force=True)
    assert not target.exists()


@pytest.mark.asyncio
async def test_list_returns_worktree_infos(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    ops = SubprocessGitWorktreeOps()
    target = tmp_path / "wt"
    await ops.add(repo, target, "feature/x")
    infos = await ops.list(repo)
    paths = {i.path for i in infos}
    assert str(target) in paths
```

- [ ] **Step 2: Run, verify FAIL** (`ImportError: cannot import 'SubprocessGitWorktreeOps'`)

- [ ] **Step 3: Extend `core/git.py`**

Adicionar ao `core/git.py`:

```python
import asyncio
from typing import Protocol


class GitWorktreeError(Exception):
    """Raised on any failed git worktree operation."""


class GitWorktreeOps(Protocol):
    async def list(self, repo: Path) -> list["WorktreeInfo"]: ...
    async def add(self, repo: Path, target: Path, branch: str) -> None: ...
    async def remove(self, repo: Path, target: Path, *, force: bool = False) -> None: ...


class SubprocessGitWorktreeOps:
    """Production impl: invokes git via subprocess on a thread pool."""

    async def list(self, repo: Path) -> list[WorktreeInfo]:
        try:
            output = await asyncio.to_thread(run_git_worktree_list, repo)
        except subprocess.CalledProcessError as exc:
            raise GitWorktreeError(
                f"git worktree list failed in {repo}: {exc.stderr.decode() if exc.stderr else exc}"
            ) from exc
        return parse_worktree_list(output)

    async def add(self, repo: Path, target: Path, branch: str) -> None:
        def _run() -> None:
            subprocess.run(
                ["git", "-C", str(repo), "worktree", "add", str(target),
                 "-b", branch],
                check=True, capture_output=True, timeout=30.0,
            )
        try:
            await asyncio.to_thread(_run)
        except subprocess.CalledProcessError as exc:
            raise GitWorktreeError(
                f"git worktree add failed in {repo} -> {target} ({branch}): "
                f"{exc.stderr.decode() if exc.stderr else exc}"
            ) from exc

    async def remove(self, repo: Path, target: Path, *, force: bool = False) -> None:
        def _run() -> None:
            cmd = ["git", "-C", str(repo), "worktree", "remove", str(target)]
            if force:
                cmd.append("--force")
            subprocess.run(cmd, check=True, capture_output=True, timeout=30.0)
        try:
            await asyncio.to_thread(_run)
        except subprocess.CalledProcessError as exc:
            raise GitWorktreeError(
                f"git worktree remove failed in {repo} -> {target}: "
                f"{exc.stderr.decode() if exc.stderr else exc}"
            ) from exc
```

- [ ] **Step 4: Run test_git_worktree_ops.py, verify PASS**

- [ ] **Step 5: Wire em main.py**

Modify `orchestrator/main.py::_build_production_app`:

```python
from orchestrator.core.git import SubprocessGitWorktreeOps

# ... dentro da função:
git_ops = SubprocessGitWorktreeOps()
# ... após create_app:
app.state.git_ops = git_ops
```

E em `create_app`:
```python
app.state.git_ops = getattr(app.state, "git_ops", None)
```

- [ ] **Step 6: Add `resolve_git_ops` em `api/_deps.py`**

```python
from fastapi import Depends, Request

from orchestrator.core.git import GitWorktreeOps


async def resolve_git_ops(request: Request) -> GitWorktreeOps:
    git = request.app.state.git_ops
    if git is None:
        raise RuntimeError("git_ops not configured in app.state")
    return git
```

- [ ] **Step 7: Coverage gate + Code review + Commit**

```bash
git add orchestrator/core/git.py orchestrator/main.py orchestrator/api/_deps.py tests/unit/test_git_worktree_ops.py
git commit -m "feat(F5.c): GitWorktreeOps Protocol + SubprocessGitWorktreeOps + wiring"
```

---

## Task 4 — F5.d: `core/sessions.py` refactor — atomic spawn + cwd

**Objetivo:** `start_session` refatorado pra criar worktrees, derivar cwd, spawn Claude, com atomicidade em 3 camadas (FS + DB + WS).

**Files:**
- Create: `orchestrator/core/slug.py`
- Create: `tests/unit/test_slugify_for_branch.py`
- Modify: `orchestrator/core/sessions.py`
- Create: `tests/unit/test_session_start_atomic.py`
- Create: `tests/unit/test_session_start_re_iniciar.py`
- Create: `tests/unit/test_session_start_no_worktree_id.py`
- Create: `tests/unit/test_session_start_branch_clash.py`

- [ ] **Step 1: Write test_slugify_for_branch.py**

```python
import pytest

from orchestrator.core.slug import (
    InvalidBranchSlugError,
    slugify_for_branch,
)


def test_simple() -> None:
    assert slugify_for_branch("Add dark mode") == "add-dark-mode"


def test_collapses_repeated_separators() -> None:
    assert slugify_for_branch("Refactor:::HTTP/2 layer") == "refactor-http-2-layer"


def test_strips_leading_trailing() -> None:
    assert slugify_for_branch("  --  Fix bug  --  ") == "fix-bug"


def test_truncates_at_60() -> None:
    long = "a" * 100
    assert len(slugify_for_branch(long)) == 60


def test_unicode_collapses_to_hyphens() -> None:
    # accents are non-[a-z0-9] → become hyphens, then collapsed
    assert slugify_for_branch("Café à la mode") == "caf-la-mode"


def test_empty_raises() -> None:
    with pytest.raises(InvalidBranchSlugError):
        slugify_for_branch("...")


def test_only_whitespace_raises() -> None:
    with pytest.raises(InvalidBranchSlugError):
        slugify_for_branch("   ")
```

- [ ] **Step 2: Run, FAIL → Implement `core/slug.py`**

```python
"""Branch slug derivation from task titles.

`slugify_for_branch` is used as the default branch name when a task
starts its first session. The output is conservative: lowercase ASCII,
hyphens only, max 60 chars. For more permissive overrides (e.g.
`feature/JIRA-123/foo`), use the user-set `task.branch` field, which
is validated by a different regex at the API layer.

NB: this function MUST stay in 1:1 sync with ui/src/lib/slug.ts. Any
divergence will cause server-side validation to disagree with the
slug preview shown in NewTaskForm placeholder.
"""
import re


_SLUG_INVALID_RE = re.compile(r"[^a-z0-9]+")
_SLUG_COLLAPSE_RE = re.compile(r"-+")


class InvalidBranchSlugError(Exception):
    """Raised when slugify yields an empty result (e.g. all-punctuation title)."""


def slugify_for_branch(text: str) -> str:
    """Derive a kebab-case slug suitable as a git branch name.

    Rules: lowercase, replace non-[a-z0-9] runs with single hyphen,
    strip leading/trailing hyphens, truncate at 60 chars.
    Raises InvalidBranchSlugError if the result is empty.
    """
    s = text.lower().strip()
    s = _SLUG_INVALID_RE.sub("-", s)
    s = _SLUG_COLLAPSE_RE.sub("-", s).strip("-")
    if not s:
        raise InvalidBranchSlugError(f"cannot slugify '{text}' to a valid branch name")
    return s[:60].rstrip("-")
```

- [ ] **Step 3: Run test, PASS**

- [ ] **Step 4: Write test_session_start_atomic.py (FakeGitOps + CollectingBroadcaster)**

```python
"""F5.d: start_session atomic in 3 layers (FS, DB, WS).

Uses FakeGitWorktreeOps to inject controlled failures and asserts
rollback semantics. Uses CollectingBroadcaster (NOT
InMemoryWsBroadcaster.subscribers) to actually verify zero broadcasts
on rollback — subscribers tracks `subscribe()` calls and is independent
of `publish()`. The honest test is: collect every event published.
"""
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from orchestrator.core.git import GitWorktreeError
from orchestrator.core.sessions import start_session
from orchestrator.events.envelope import WsEvent
from orchestrator.sandbox.runtime import JailHandle
from orchestrator.store.database import Database
from orchestrator.store.models import (
    ClaudeSession, Project, Repository, Task, Worktree,
)


class FakeGitOps:
    def __init__(self, fail_at: int | None = None) -> None:
        self.added: list[tuple[Path, Path, str]] = []
        self.removed: list[tuple[Path, Path]] = []
        self._fail_at = fail_at

    async def add(self, repo: Path, target: Path, branch: str) -> None:
        if self._fail_at is not None and len(self.added) == self._fail_at:
            raise GitWorktreeError(f"simulated failure on add #{self._fail_at}")
        self.added.append((repo, target, branch))
        target.mkdir(parents=True, exist_ok=True)
        (target / ".git").write_text("ref")

    async def remove(self, repo: Path, target: Path, *, force: bool = False) -> None:
        self.removed.append((repo, target))
        if target.exists():
            import shutil
            shutil.rmtree(target)

    async def list(self, repo: Path):
        return []


class CollectingBroadcaster:
    """Captures every WsEvent published. Use this — NOT
    InMemoryWsBroadcaster — when the test needs to assert WHAT was
    broadcast, not just track subscribers."""

    def __init__(self) -> None:
        self.received: list[WsEvent] = []

    async def publish(self, event: WsEvent) -> None:
        self.received.append(event)


class FakeRuntime:
    async def spawn(self, cwd: Path, *, token=None, base_url=None) -> JailHandle:
        return JailHandle(id="fake", pid=42, started_at=datetime.now(UTC))

    async def kill(self, handle, *, worktree=None) -> None:
        pass


async def _seed_multi_repo_project(
    session, tmp_path: Path, sub_repos: Iterable[str]
) -> tuple[Project, list[Repository], Task]:
    proj_path = tmp_path / "p"
    proj_path.mkdir()
    project = Project(name="p", path=str(proj_path))
    session.add(project)
    await session.flush()
    repos = []
    for sub in sub_repos:
        r = Repository(project_id=project.id, name=sub, sub_path=sub)
        session.add(r)
        repos.append(r)
    task = Task(project_id=project.id, title="Add OAuth", description="")
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return project, repos, task


@pytest.mark.asyncio
async def test_atomic_spawn_multi_repo_happy_path(tmp_path: Path) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/a.db")
    await db.bootstrap()
    git = FakeGitOps()
    runtime = FakeRuntime()
    bc = CollectingBroadcaster()

    async with db.session() as s:
        project, repos, task = await _seed_multi_repo_project(s, tmp_path, ["backend", "frontend"])

        row = await start_session(
            s, runtime, git,
            task_id=task.id, broadcaster=bc,
        )

        # 2 worktrees criadas no FS via Fake
        assert len(git.added) == 2
        # cwd parent contém os 2
        cwd = Path(row.cwd)
        assert cwd.exists()
        assert (cwd / "backend").is_dir()
        assert (cwd / "frontend").is_dir()
        # DB rows committed
        from sqlalchemy import select
        wts = (await s.execute(select(Worktree).where(Worktree.task_id == task.id))).scalars().all()
        assert len(wts) == 2
        # WS broadcasted 2 worktree.created events (após commit, não antes)
        worktree_events = [e for e in bc.received if e.type == "worktree.created"]
        assert len(worktree_events) == 2


@pytest.mark.asyncio
async def test_atomic_spawn_rollback_on_second_add_fail(tmp_path: Path) -> None:
    """Critical: rollback on partial failure must leave NO traces:
    no FS, no DB rows committed, NO worktree.created broadcasts emitted.
    """
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/r.db")
    await db.bootstrap()
    git = FakeGitOps(fail_at=1)  # 2nd add falha
    runtime = FakeRuntime()
    bc = CollectingBroadcaster()

    async with db.session() as s:
        project, repos, task = await _seed_multi_repo_project(s, tmp_path, ["backend", "frontend"])

        with pytest.raises(GitWorktreeError):
            await start_session(s, runtime, git, task_id=task.id, broadcaster=bc)

        # 1st add foi feito; rollback chamou remove
        assert len(git.added) == 1
        assert len(git.removed) == 1
        # Nada committed
        from sqlalchemy import select
        wts = (await s.execute(select(Worktree).where(Worktree.task_id == task.id))).scalars().all()
        assert len(wts) == 0
        # ZERO broadcasts de worktree.created (deferred até pós-commit; rollback bloqueou)
        worktree_events = [e for e in bc.received if e.type == "worktree.created"]
        assert worktree_events == [], (
            f"expected no worktree.created broadcasts on rollback; got {worktree_events}"
        )
```

- [ ] **Step 5: Run, FAIL — refactor `core/sessions.py::start_session`**

Refactor full function. Steps detalhados em §6.3 do spec. Sketch:

```python
async def start_session(
    session: AsyncSession,
    runtime: SessionRuntime,
    git: GitWorktreeOps,
    *,
    task_id: str,
    token_registry: TokenRegistry | None = None,
    base_url: str | None = None,
    broadcaster: WsBroadcaster | None = None,
) -> ClaudeSession:
    task = await get_task(session, task_id)
    await session.refresh(task)

    if task.state in ("done", "discarded"):
        raise TaskInTerminalStateError(...)

    active = await _count_active_sessions(session, task_id)
    if active > 0:
        raise TaskAlreadyHasActiveSessionError(...)

    project = await session.get(Project, task.project_id)
    repos = await list_project_repositories(session, project.id)

    branch = task.branch or slugify_for_branch(task.title)
    cwd_default = _derive_cwd(project.path, branch)

    # Has existing worktrees? (re-iniciar)
    existing = await list_worktrees_for_task(session, task_id)
    if existing:
        cwd = _derive_cwd_from_existing(existing)
        new_worktree_pairs = []  # nada a criar
    else:
        cwd = cwd_default
        # NB: broadcaster is NOT passed — broadcasts are deferred until
        # AFTER session.commit() in start_session itself (see "Broadcasts:
        # worktree.created (deferred até depois do commit final)" below).
        new_worktree_pairs = await _create_worktrees_atomic(
            session, git, project, repos, task_id, branch, cwd
        )

    # Auto-transition state
    prev_state = task.state
    if task.state in ("idea", "ready", "review"):
        task.state = "in_progress"
        task.updated_at = datetime.now(UTC)

    # Spawn Claude
    token = generate_token() if token_registry is not None else None
    try:
        handle = await runtime.spawn(cwd, token=token, base_url=base_url)
    except Exception:
        # Rollback worktrees criadas + reverter state
        if new_worktree_pairs:
            await _rollback_worktrees(git, project, new_worktree_pairs)
        if prev_state != task.state:
            task.state = prev_state
            await session.commit()
        raise

    row = ClaudeSession(
        task_id=task_id, cwd=str(cwd), status=SessionStatus.EXECUTING,
        pid=handle.pid, jail_id=handle.id, started_at=handle.started_at,
        hook_token=token,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)

    if token_registry is not None and token is not None:
        token_registry.register(token, row.id)

    # Broadcasts: worktree.created (deferred até depois do commit final)
    if broadcaster is not None:
        for wt, repo in new_worktree_pairs:
            await broadcaster.publish(WsEvent.worktree_created(
                worktree_id=wt.id, project_id=repo.project_id,
                repository_id=repo.id, task_id=task_id,
                path=wt.path, branch=wt.branch,
            ))

    return row


def _derive_cwd(project_path: str, branch_slug: str) -> Path:
    p = Path(project_path)
    return p.parent / f"{p.name}--{branch_slug}"


def _derive_cwd_from_existing(worktrees: list[Worktree]) -> Path:
    if len(worktrees) == 1:
        return Path(worktrees[0].path)  # monorepo
    return Path(worktrees[0].path).parent  # multi-repo


async def _create_worktrees_atomic(
    session: AsyncSession,
    git: GitWorktreeOps,
    project: Project,
    repos: Sequence[Repository],
    task_id: str,
    branch: str,
    cwd: Path,
) -> list[tuple[Worktree, Repository]]:
    """Create N worktrees atomically. Returns [(wt_row, repo)] on success
    (DB committed). On any failure: rollback git ops + session, raise.

    Single source of truth: `created_pairs` is the list — each entry is
    (Worktree row, Repository). Built incrementally; consumed in reverse
    on rollback.
    """
    if cwd.exists():
        raise CwdAlreadyExistsError(f"cwd path '{cwd}' already exists")

    is_multi = len(repos) > 1
    if is_multi:
        cwd.mkdir(parents=False, exist_ok=False)

    created_pairs: list[tuple[Worktree, Repository]] = []
    try:
        for repo in repos:
            repo_full = Path(project.path) / repo.sub_path
            target = cwd / repo.name if is_multi else cwd
            await git.add(repo_full, target, branch)
            wt = Worktree(
                repository_id=repo.id, task_id=task_id,
                path=str(target), branch=branch,
            )
            session.add(wt)
            await session.flush()
            created_pairs.append((wt, repo))
        await session.commit()
    except Exception:
        await _rollback_worktrees(git, project, created_pairs)
        if is_multi and cwd.exists():
            try: cwd.rmdir()
            except OSError: pass
        await session.rollback()
        raise
    return created_pairs


async def _rollback_worktrees(
    git: GitWorktreeOps,
    project: Project,
    created_pairs: list[tuple[Worktree, Repository]],
) -> None:
    """Best-effort rollback. Iterates in reverse to undo last-first."""
    for wt, repo in reversed(created_pairs):
        repo_full = Path(project.path) / repo.sub_path
        try:
            await git.remove(repo_full, Path(wt.path), force=True)
        except GitWorktreeError as exc:
            _log.warning(f"rollback failed for {wt.path}: {exc}")


# NB: `_log` é o logger do módulo. Se ainda não existir em `core/sessions.py`,
# adicionar no topo do arquivo:
#
#     import logging
#     _log = logging.getLogger(__name__)
#
# (mesmo padrão de `notifications/notify_send.py` da F2).
```

- [ ] **Step 6: Run tests, iterate até PASS**

- [ ] **Step 7: Write + run test_session_start_re_iniciar.py** (verifica que 2ª chamada não chama git.add)

- [ ] **Step 8: Write + run test_session_start_no_worktree_id.py** (verifica que assinatura nova rejeita worktree_id por TypeError)

- [ ] **Step 9: Write + run test_session_start_branch_clash.py** (FakeGitOps levanta GitWorktreeError → rollback + raise)

- [ ] **Step 10: Coverage gate + code review + commit**

```bash
git add orchestrator/core/slug.py orchestrator/core/sessions.py tests/unit/test_slugify_for_branch.py tests/unit/test_session_start_*.py
git commit -m "feat(F5.d): start_session atomic spawn (3-layer rollback) + cwd derivation"
```

---

## Task 5 — F5.e: `core/tasks.py` — branch field + active-session guard + cleanup hook

**Objetivo:** add `branch` no `update_task`; raise `TaskHasActiveSessionError` em terminal-state transitions com session ativa; raise `BranchImmutableAfterFirstSessionError` em mudança de branch pós-1ª-sessão.

**Files:**
- Modify: `orchestrator/core/tasks.py`
- Create: `tests/unit/test_task_state_done_active_session_guard.py`
- Create: `tests/unit/test_task_branch_validation.py`

- [ ] **Step 1: Write test_task_state_done_active_session_guard.py**

```python
import pytest

from orchestrator.core.sessions import SessionStatus
from orchestrator.core.tasks import (
    TaskHasActiveSessionError,
    update_task,
)
from orchestrator.store.models import ClaudeSession, Project, Repository, Task


@pytest.mark.asyncio
async def test_state_done_with_active_session_raises(tmp_path) -> None:
    from orchestrator.store.database import Database
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/g.db")
    await db.bootstrap()
    async with db.session() as s:
        p = Project(name="p", path=str(tmp_path))
        s.add(p); await s.flush()
        r = Repository(project_id=p.id, name="p", sub_path=".")
        s.add(r); await s.flush()
        t = Task(project_id=p.id, title="T", description="", state="in_progress")
        s.add(t); await s.flush()
        cs = ClaudeSession(task_id=t.id, cwd=str(tmp_path), status=SessionStatus.EXECUTING)
        s.add(cs); await s.commit()

        with pytest.raises(TaskHasActiveSessionError):
            await update_task(s, t.id, state="done")


@pytest.mark.asyncio
async def test_state_done_without_active_session_ok(tmp_path) -> None:
    # ... setup similar mas sem session ativa, ou com session em DONE
    # update_task ok, retorna row
```

- [ ] **Step 2: Run, FAIL → Modify `core/tasks.py`**

Add new exception:
```python
class TaskHasActiveSessionError(Exception): pass
class BranchImmutableAfterFirstSessionError(Exception): pass
class InvalidBranchOverrideError(Exception): pass
```

In `update_task`:
```python
import re
_BRANCH_OVERRIDE_RE = re.compile(r"^[a-z0-9][a-z0-9._/-]*$")

async def update_task(
    session: AsyncSession,
    task_id: str,
    *,
    title: str | None = None,
    description: str | None = None,
    state: str | None = None,
    branch: str | None = None,
) -> tuple[Task, str | None]:
    row = await get_task(session, task_id)
    await session.refresh(row)
    previous_state = row.state if state is not None else None

    if title is not None:
        if not title.strip():
            raise InvalidTaskTitleError("title cannot be empty")
        row.title = title
    if description is not None:
        row.description = description
    if branch is not None:
        if not _BRANCH_OVERRIDE_RE.match(branch) or len(branch) > 200:
            raise InvalidBranchOverrideError(
                f"branch must match ^[a-z0-9][a-z0-9._/-]*$ and be ≤200 chars"
            )
        wts_count = await _count_worktrees_for_task(session, task_id)
        if wts_count > 0:
            raise BranchImmutableAfterFirstSessionError(
                "branch cannot be changed after worktrees were created; "
                "discard task and recreate"
            )
        row.branch = branch
    if state is not None:
        if not is_valid_transition(row.state, state):
            raise InvalidTransitionError(...)
        if state in ("done", "discarded"):
            from orchestrator.core.sessions import _count_active_sessions
            active = await _count_active_sessions(session, task_id)
            if active > 0:
                raise TaskHasActiveSessionError(
                    "task has active session; stop it before completing/discarding"
                )
        row.state = state
        row.updated_at = datetime.now(UTC)

    await session.commit()
    return row, previous_state


async def _count_worktrees_for_task(session, task_id) -> int:
    from sqlalchemy import select, func
    from orchestrator.store.models import Worktree
    return (await session.execute(
        select(func.count()).select_from(Worktree).where(Worktree.task_id == task_id)
    )).scalar_one()
```

- [ ] **Step 3: Run, PASS**

- [ ] **Step 4: Write + run test_task_branch_validation.py** — testa regex, len, override pós-worktree.

- [ ] **Step 5: Coverage gate + code review + commit**

```bash
git add orchestrator/core/tasks.py tests/unit/test_task_state_done_active_session_guard.py tests/unit/test_task_branch_validation.py
git commit -m "feat(F5.e): tasks branch field + active-session guard + cleanup-trigger hooks"
```

---

## Task 6 — F5.f: `core/worktrees.py` — refactor + cleanup_task_worktrees + delete_worktree

**Objetivo:** refactor `list_project_worktrees` pra iterar repositories; add `cleanup_task_worktrees`, `list_worktrees_for_task`, `list_orphan_worktrees`, `delete_worktree`.

**Files:**
- Modify: `orchestrator/core/worktrees.py`
- Create: `tests/unit/test_worktrees_cleanup_soft_fail.py`

- [ ] **Step 1: Write test_worktrees_cleanup_soft_fail.py**

```python
"""Cleanup tolerates per-worktree git remove failures by orphaning rows."""
import pytest

from orchestrator.core.worktrees import cleanup_task_worktrees
# ... seed multi-repo task with 2 worktrees ...
# FakeGitOps configured to fail on 2nd remove
# After: 1st worktree DELETED, 2nd has task_id=NULL, both broadcast events
```

- [ ] **Step 2: FAIL → Implement `cleanup_task_worktrees`**

(Spec §6.4.2 — code completo.)

- [ ] **Step 3: Add `list_worktrees_for_task`, `list_orphan_worktrees`, `delete_worktree`**

```python
async def list_worktrees_for_task(session, task_id) -> Sequence[Worktree]:
    result = await session.execute(
        select(Worktree).where(Worktree.task_id == task_id)
    )
    return result.scalars().all()


async def list_orphan_worktrees(session, project_id) -> Sequence[Worktree]:
    result = await session.execute(
        select(Worktree)
        .join(Repository, Repository.id == Worktree.repository_id)
        .where(Repository.project_id == project_id, Worktree.task_id.is_(None))
    )
    return result.scalars().all()


class WorktreeNotOrphanError(Exception): pass


async def delete_worktree(
    session, git: GitWorktreeOps, worktree_id: str
) -> None:
    wt = await session.get(Worktree, worktree_id)
    if wt is None:
        raise WorktreeNotFoundError(...)
    if wt.task_id is not None:
        raise WorktreeNotOrphanError(
            f"worktree {worktree_id} belongs to active task {wt.task_id}"
        )
    repo = await session.get(Repository, wt.repository_id)
    project = await session.get(Project, repo.project_id)
    repo_full = Path(project.path) / repo.sub_path
    await git.remove(repo_full, Path(wt.path), force=True)
    await session.delete(wt)
    await session.commit()
```

- [ ] **Step 4: Refactor `list_project_worktrees`** (spec §7.7).

- [ ] **Step 5: Coverage gate + code review + commit**

```bash
git commit -m "feat(F5.f): worktree sync iterates repositories; cleanup soft-fail; delete_worktree for orphans"
```

---

## Task 7 — F5.g: API routes update

**Objetivo:** atualizar `api/projects.py`, `api/tasks.py`, `api/worktrees.py` para o novo modelo.

**Files:**
- Modify: `orchestrator/api/projects.py`
- Modify: `orchestrator/api/tasks.py`
- Modify: `orchestrator/api/worktrees.py`
- Create: `tests/integration/test_projects_create_detects_repos.py`
- Create: `tests/integration/test_repositories_in_projects_response.py`
- Create: `tests/integration/test_task_session_monorepo_flow.py`
- Create: `tests/integration/test_task_session_multi_repo_flow.py`
- Create: `tests/integration/test_task_session_re_iniciar.py`
- Create: `tests/integration/test_task_session_branch_clash_422.py`
- Create: `tests/integration/test_task_state_done_triggers_cleanup.py`
- Create: `tests/integration/test_task_state_done_blocked_active_session.py`
- Create: `tests/integration/test_cleanup_soft_fail_orphans.py`
- Create: `tests/integration/test_delete_orphan_worktree.py`
- Create: `tests/integration/test_external_worktree_appears_as_orphan.py`
- Create: `tests/integration/test_branch_override_field.py`

- [ ] **Step 1: Write integration tests in TDD style** — um por arquivo, RED → GREEN para cada cenário. Estrutura conforme §6 e §10 do spec. Para os testes não-óbvios, scaffolds abaixo:

#### `test_projects_create_detects_repos.py` (mirror estrutural de `test_projects_api.py`)

```python
"""POST /projects detecta sub-repos automaticamente via _detect_repos."""
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.main import create_app
from orchestrator.store.database import Database
from tests.integration.conftest import _make_repo, _make_multi_repo


async def test_post_project_monorepo_creates_one_repository(
    db: Database, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path, "mono")
    app = create_app(database=db, runtime=None, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/projects", json={"name": "mono", "path": str(repo)})
    assert r.status_code == 201
    body = r.json()
    assert len(body["repositories"]) == 1
    assert body["repositories"][0]["sub_path"] == "."


async def test_post_project_multi_repo_creates_n_repositories(
    db: Database, tmp_path: Path,
) -> None:
    base = _make_multi_repo(tmp_path, ["backend", "frontend"], name="hub")
    app = create_app(database=db, runtime=None, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/projects", json={"name": "hub", "path": str(base)})
    assert r.status_code == 201
    sub_paths = sorted(r["sub_path"] for r in r.json()["repositories"])
    assert sub_paths == ["backend", "frontend"]


async def test_post_project_no_repos_returns_422(
    db: Database, tmp_path: Path,
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    app = create_app(database=db, runtime=None, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/projects", json={"name": "empty", "path": str(empty)})
    assert r.status_code == 422
    assert "no .git" in r.json()["detail"]
```

#### `test_task_session_multi_repo_flow.py` (mirror de `test_task_session_route.py`)

```python
"""End-to-end: POST /tasks/{id}/sessions em projeto multi-repo cria 2
worktrees; cwd = parent dir; FakeRuntime spawn registra cwd correto."""
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.main import create_app
from orchestrator.store.database import Database
from tests.integration.conftest import FakeSessionRuntime, _make_multi_repo


async def test_post_task_session_multi_repo_creates_2_worktrees(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    base = _make_multi_repo(tmp_path, ["backend", "frontend"], name="hub")
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        proj = (await c.post("/api/projects", json={"name": "hub", "path": str(base)})).json()
        task = (await c.post("/api/tasks", json={"project_id": proj["id"], "title": "Add OAuth"})).json()
        r = await c.post(f"/api/tasks/{task['id']}/sessions", json={})
    assert r.status_code == 201
    body = r.json()
    cwd = Path(body["cwd"])
    assert cwd.exists()
    assert (cwd / "backend" / ".git").exists()
    assert (cwd / "frontend" / ".git").exists()
    # FakeSessionRuntime registrou spawn no parent (cwd), não em cada subdir
    assert len(runtime.spawned) == 1
```

#### `test_cleanup_soft_fail_orphans.py` (test override de git_ops)

```python
"""Cleanup tolera falhas: se git remove falha em uma worktree, ela vira
órfã (task_id=NULL) sem bloquear a transição de estado da task."""
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.core.git import GitWorktreeError
from orchestrator.main import create_app
from orchestrator.store.database import Database
from tests.integration.conftest import FakeSessionRuntime, _make_multi_repo


class FlakyGitOps:
    """Real adds, but fail on remove of a specific path."""
    def __init__(self, real_ops, fail_path: str) -> None:
        self._real = real_ops
        self._fail_path = fail_path
        self.removed: list[str] = []

    async def add(self, repo, target, branch): await self._real.add(repo, target, branch)
    async def list(self, repo): return await self._real.list(repo)
    async def remove(self, repo, target, *, force=False):
        self.removed.append(str(target))
        if str(target) == self._fail_path:
            raise GitWorktreeError("simulated dirty worktree")
        await self._real.remove(repo, target, force=force)


async def test_cleanup_soft_fail_orphans_failed_worktree(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    base = _make_multi_repo(tmp_path, ["backend", "frontend"], name="hub")
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    # Override git_ops para forçar falha no frontend.
    from orchestrator.core.git import SubprocessGitWorktreeOps
    real_ops = SubprocessGitWorktreeOps()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        proj = (await c.post("/api/projects", json={"name": "hub", "path": str(base)})).json()
        task = (await c.post("/api/tasks", json={"project_id": proj["id"], "title": "T"})).json()
        sess = (await c.post(f"/api/tasks/{task['id']}/sessions", json={})).json()
        cwd = Path(sess["cwd"])
        # Inject flaky ops AFTER worktrees criadas; falha no remove do frontend
        app.state.git_ops = FlakyGitOps(real_ops, str(cwd / "frontend"))
        # Move task pra done — dispara cleanup
        r = await c.patch(f"/api/tasks/{task['id']}", json={"state": "done"})
        wts = (await c.get(f"/api/projects/{proj['id']}/worktrees")).json()
    assert r.status_code == 200
    # backend foi removido; frontend ficou órfã (task_id=None)
    orphans = [w for w in wts if w["is_orphan"]]
    paths = [w["path"] for w in orphans]
    assert any("frontend" in p for p in paths)
    assert not any("backend" in p for p in paths)
```

#### `test_external_worktree_appears_as_orphan.py`

```python
"""Worktree criada externamente (via terminal) aparece como órfã na
próxima sync via GET /projects/{id}/worktrees."""
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.main import create_app
from orchestrator.store.database import Database
from tests.integration.conftest import _make_repo, _git


async def test_external_git_worktree_appears_as_orphan(
    db: Database, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path, "mono")
    # Criar worktree externamente via subprocess
    target = tmp_path / "mono--external"
    _git(repo, "worktree", "add", str(target), "-b", "external")

    app = create_app(database=db, runtime=None, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        proj = (await c.post("/api/projects", json={"name": "mono", "path": str(repo)})).json()
        wts = (await c.get(f"/api/projects/{proj['id']}/worktrees")).json()

    paths = [w["path"] for w in wts]
    assert str(target) in paths
    external_row = next(w for w in wts if w["path"] == str(target))
    assert external_row["is_orphan"] is True
    assert external_row["task_id"] is None
```

Os outros (`test_repositories_in_projects_response.py`, `test_task_session_monorepo_flow.py`, `test_task_session_re_iniciar.py`, `test_task_session_branch_clash_422.py`, `test_task_state_done_triggers_cleanup.py`, `test_task_state_done_blocked_active_session.py`, `test_delete_orphan_worktree.py`, `test_branch_override_field.py`) seguem o mesmo pattern dos exemplos acima — cada um é 30-50 linhas, estrutura idêntica a `test_task_session_route.py` da F4.

- [ ] **Step 2: Modify `api/projects.py`**

```python
from orchestrator.core.repositories import detect_repos, NoGitReposError

@router.post("", status_code=201, response_model=ProjectRead)
async def post_project(payload, ...):
    # ... existing validation ...
    try:
        repos_specs = detect_repos(Path(payload.path))
    except NoGitReposError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    # Create Project + N Repository rows in same transaction
    project = Project(name=payload.name, path=payload.path)
    session.add(project)
    await session.flush()
    for spec in repos_specs:
        session.add(Repository(
            project_id=project.id,
            name=spec.name if spec.sub_path != "." else project.name,
            sub_path=spec.sub_path,
        ))
    await session.commit()
    # ... return ProjectRead with repositories list ...
```

- [ ] **Step 3: Modify `api/tasks.py`** — remove worktree_id; add SessionCreatePayload com `extra=forbid`; add cleanup trigger no PATCH; aceita branch.

- [ ] **Step 4: Modify `api/worktrees.py`** — DELETE endpoint para órfãs.

- [ ] **Step 5: Run all integration tests + coverage gate**

- [ ] **Step 6: Code review + commit**

```bash
git commit -m "feat(F5.g): API routes atualizadas (auto-detect projects + tasks com branch + DELETE worktree)"
```

---

## Task 8 — F5.h: WS envelope + broadcasts

**Objetivo:** `worktree_created`, `worktree_removed`, `worktree_orphaned` factories; broadcast pontos certos.

**Files:**
- Modify: `orchestrator/events/envelope.py`
- Create: `tests/unit/test_ws_envelope_worktrees.py`

- [ ] **Step 1: Write tests for 3 factories**

- [ ] **Step 2: Add factories**

```python
@classmethod
def worktree_created(
    cls, *, worktree_id: str, project_id: str, repository_id: str,
    task_id: str | None, path: str, branch: str | None,
) -> "WsEvent":
    return cls(
        type="worktree.created",
        session_id="",
        task_id=task_id,
        payload={"worktree_id": worktree_id, "project_id": project_id,
                 "repository_id": repository_id, "path": path, "branch": branch},
    )

@classmethod
def worktree_removed(...): ...

@classmethod
def worktree_orphaned(...): ...
```

- [ ] **Step 3: Wire broadcasts em start_session, cleanup_task_worktrees, delete_worktree**

- [ ] **Step 4: Coverage gate + commit**

```bash
git commit -m "feat(F5.h): WS envelope worktree.* factories + broadcasts"
```

---

## Task 9 — F5.i: UI lib (api.ts + slug.ts + useLocalStorage)

**Objetivo:** types e endpoints atualizados; mirror client de slugify; helper localStorage.

**Files:**
- Modify: `ui/src/lib/api.ts`
- Modify: `ui/src/lib/api.test.ts`
- Create: `ui/src/lib/slug.ts`
- Create: `ui/src/lib/slug.test.ts`
- Create: `ui/src/lib/useLocalStorage.ts`
- Create: `ui/src/lib/useLocalStorage.test.ts`

- [ ] **Step 1: Write slug.test.ts (paridade com Python)**

```ts
import { describe, expect, it } from 'vitest';
import { slugifyForBranch, InvalidBranchSlugError } from './slug';

describe('slugifyForBranch', () => {
  it('simple', () => expect(slugifyForBranch('Add dark mode')).toBe('add-dark-mode'));
  it('collapses', () => expect(slugifyForBranch('Refactor:::HTTP/2 layer')).toBe('refactor-http-2-layer'));
  it('strips', () => expect(slugifyForBranch('  --  Fix bug  --  ')).toBe('fix-bug'));
  it('truncates 60', () => expect(slugifyForBranch('a'.repeat(100)).length).toBe(60));
  it('unicode', () => expect(slugifyForBranch('Café à la mode')).toBe('caf-la-mode'));
  it('empty throws', () => expect(() => slugifyForBranch('...')).toThrow(InvalidBranchSlugError));
});
```

- [ ] **Step 2: Implement slug.ts** (mirror exato de Python)

```ts
export class InvalidBranchSlugError extends Error {}

export function slugifyForBranch(text: string): string {
  let s = text.toLowerCase().trim();
  s = s.replace(/[^a-z0-9]+/g, '-');
  s = s.replace(/-+/g, '-').replace(/^-+|-+$/g, '');
  if (!s) throw new InvalidBranchSlugError(`cannot slugify '${text}'`);
  return s.slice(0, 60).replace(/-+$/g, '');
}
```

- [ ] **Step 3: Write + implement useLocalStorage**

```ts
import { useState, useEffect, useCallback } from 'react';

export function useLocalStorage<T>(key: string, initial: T): [T, (v: T) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = window.localStorage.getItem(key);
      return raw === null ? initial : (JSON.parse(raw) as T);
    } catch {
      return initial;
    }
  });
  const set = useCallback((v: T) => {
    setValue(v);
    try { window.localStorage.setItem(key, JSON.stringify(v)); } catch {}
  }, [key]);
  return [value, set];
}
```

- [ ] **Step 4: Update api.ts types e endpoints (spec §5.6)**

- [ ] **Step 5: Update api.test.ts tests**

- [ ] **Step 6: UI Coverage gate**

```bash
cd ui && CI=true pnpm coverage
```

- [ ] **Step 7: Commit**

```bash
git commit -m "feat(F5.i): UI lib slug.ts + useLocalStorage + api.ts types/endpoints F5"
```

---

## Task 10 — F5.j: UI components — ProjectsDrawer rewrite + sub-components

**Objetivo:** rewrite `ProjectsDrawer` como container; novos `ProjectNode`, `TaskWorktreeGroup`, `WorktreeRow`, `OrphansGroup`.

**Files:**
- Modify: `ui/src/components/ProjectsDrawer.tsx` + `.test.tsx`
- Create: `ui/src/components/ProjectNode.tsx` + `.test.tsx`
- Create: `ui/src/components/TaskWorktreeGroup.tsx` + `.test.tsx`
- Create: `ui/src/components/WorktreeRow.tsx` + `.test.tsx`
- Create: `ui/src/components/OrphansGroup.tsx` + `.test.tsx`

- [ ] **Steps por componente: TDD red → green** (ver spec §8.2 pra estrutura JSX).

- [ ] **Final: UI coverage gate + commit**

```bash
git commit -m "feat(F5.j): Kanban map de worktrees (ProjectsDrawer rewrite + 4 sub-components)"
```

---

## Task 11 — F5.k: UI — NewTaskForm + TaskDetailModal + useSessionEvents

**Objetivo:** NewTaskForm.Avançado.branch; TaskDetailModal sem worktree picker; useSessionEvents handlers worktree.*.

**Files:**
- Modify: `ui/src/components/NewTaskForm.tsx` + `.test.tsx`
- Modify: `ui/src/components/TaskDetailModal.tsx` + `.test.tsx`
- Modify: `ui/src/hooks/useSessionEvents.ts` + `.test.ts`

- [ ] **TDD por componente** (spec §8.3, §8.4, §8.5).

- [ ] **Coverage gate + commit**

```bash
git commit -m "feat(F5.k): NewTaskForm.Avançado.branch + TaskDetailModal sem picker + useSessionEvents handlers worktree.*"
```

---

## Task 12 — F5.l: E2E + ARCHITECTURE + ADRs + Demo

**Objetivo:** fechamento da fase. E2E Playwright cobrindo fluxos novos, ARCHITECTURE.md atualizada, 3 ADRs, demo manual.

**Files:**
- Create: `tests/e2e/test_f5_monorepo_flow.py`
- Create: `tests/e2e/test_f5_multi_repo_flow.py`
- Create: `tests/e2e/test_f5_orphan_visible.py`
- Modify: `ARCHITECTURE.md`
- Create: `docs/adr/0015-project-multi-repo-com-auto-detect.md`
- Create: `docs/adr/0016-multi-repo-1-sessao-cwd-shared.md`
- Create: `docs/adr/0017-worktree-detalhe-da-task-sem-create-ui.md`
- Modify: `docs/adr/README.md`

- [ ] **Step 1: E2E tests Playwright** (3 arquivos, similar a F4.l Step 1)

- [ ] **Step 2: Run E2E (do host, fora da jaula!)**

```bash
uv run pytest tests/e2e -v
```

- [ ] **Step 3: ADR-0015** — Project multi-repo com auto-detect.

- [ ] **Step 4: ADR-0016** — Multi-repo 1 sessão cwd shared.

- [ ] **Step 5: ADR-0017** — Worktree é detalhe da task; sem create UI.

- [ ] **Step 6: Update ARCHITECTURE.md §3, §11, §13**

§3: add Repository ao modelo de dados; refatora Worktree e ClaudeSession.
§11: marca F5 ✅.
§13: 3 rows novas (ADR-0015, 0016, 0017).

- [ ] **Step 7: Update docs/adr/README.md**

- [ ] **Step 8: Coverage final do projeto**

```bash
unset VIRTUAL_ENV && uv run python -m pytest tests/unit tests/integration --cov=orchestrator --cov-fail-under=100
cd ui && CI=true pnpm coverage
```
Expected: 100% Python; UI 100% nos arquivos novos.

- [ ] **Step 9: Code review final** (Agent superpowers:code-reviewer)

Dispatch reviewer com prompt: "Review entire F5 branch from F4.m..HEAD. Verify against spec `docs/superpowers/specs/2026-05-09-f5-mapa-worktrees-design.md`: every closed decision (#1-10) implemented; every test in §10 exists; ARCHITECTURE.md §3/§11/§13 reflects new state; ADR-0015/0016/0017 follow ADR-0009/0010 format; no leftover `worktree_id` references in api/sessions endpoint or `Worktree.project_id` references."

- [ ] **Step 10: Demo manual (do host, fora da jaula)**

Ver §14 do spec — 14 passos.

- [ ] **Step 11: Commit final**

```bash
git add tests/e2e/test_f5_*.py ARCHITECTURE.md docs/adr/0015-*.md docs/adr/0016-*.md docs/adr/0017-*.md docs/adr/README.md
git commit -m "feat(F5.l): E2E flows + ARCHITECTURE + ADR-0015/0016/0017 + demo"
```

---

## Encerramento — checklist final F5

- [ ] Todos os tests F1/F2/F4 pré-existentes passam (regressão zero)
- [ ] `uv run pytest tests/unit -q`: 100% verde
- [ ] `uv run pytest tests/integration -q`: 100% verde
- [ ] `pnpm --dir ui exec vitest run`: 100% verde
- [ ] `uv run pytest tests/e2e -v`: passa (do host)
- [ ] `uv run pytest --cov=orchestrator --cov-fail-under=100`
- [ ] Demo manual roteiro inteiro funciona
- [ ] `git log --oneline | head -25` mostra 12-13 commits F5.X consecutivos
- [ ] `gotchas.md` revisado — adicionar entry se algum aprendizado novo
- [ ] Push da branch — depende de fora da jaula
