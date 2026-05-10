# F5 — Mapa de worktrees + multi-repo + auto-create (design spec)

- **Data:** 2026-05-09
- **Fase do roadmap:** F5 (`ARCHITECTURE.md` §11)
- **Pré-requisitos:** F1 + F2 + F4 concluídos. F4.m fechou gate de cobertura.
- **Decisões novas:** ADR-0015 (Project = lista de sub-repos com auto-detect),
  ADR-0016 (multi-repo: 1 sessão Claude com cwd no parent dir),
  ADR-0017 (Worktree é detalhe de implementação da Task — sem standalone create UI).
- **Escopo recusado / deferido:**
  - **Standalone "+ Nova worktree"**: criação de worktree só acontece
    como side-effect de "Iniciar sessão" numa task. Sem botão dedicado.
  - **Quick session**: removida. Tudo passa pelo kanban (`Iniciar
    sessão` na task). Reduz caminhos paralelos.
  - **Configuração de base branch**: HEAD de cada sub-repo, sem
    config. Pós-MVP pode ganhar override por projeto se a dor aparecer.
  - **Re-detect de sub-repos** após add-project: não auto-detecta
    novos sub-repos depois. Usuário remove + re-adiciona projeto. F5.5
    futura pode adicionar botão "Re-detect".
  - **Worktree de branch existente** (checkout de branch teammate):
    descartado. Auto-slug + override em `task.branch` cobrem 95%; o
    raro 5% pode ser feito via terminal e aparece como órfã.

## 1. Objetivo

Resolver "tô com 5 worktrees em 3 projetos e não sei quem é quem".
Mapa visual de tudo que existe no disco, com criação/destruição
implícitas via fluxo de tasks. **Worktree é detalhe de implementação
da task** — task-first até o fim. Suporta projetos multi-repo
(ex: `gcb-hub` com `backend/` + `frontend/` cada um com seu `.git`).

**Demo de aceitação** (em E2E + manual do host fora da jaula):

1. Adicionar projeto monorepo (mock: `~/tmp/proj-mono` com `git init`)
   → ver "monorepo · 0 tasks" no map.
2. Adicionar projeto multi-repo (mock: `~/tmp/proj-multi/{backend,frontend}`
   cada um com `git init`) → ver "2 sub-repos".
3. Criar task "Add OAuth" no projeto multi-repo (com Avançado.branch =
   `feature/add-oauth`).
4. Click ▶ Iniciar sessão (do kanban) → daemon cria 2 worktrees em
   `~/tmp/proj-multi--feature-add-oauth/{backend,frontend}` + spawn
   Claude com cwd = parent. Map mostra a task com 2 worktrees agrupadas.
5. Drag task → Done no kanban → toast + worktrees somem do map + dirs
   removidos.
6. Externamente: `git -C ~/tmp/proj-mono worktree add ../proj-mono--external -b external`
   → reload UI → ver órfã sob proj-mono → click `✕ Remover`.
7. Tentar mover task com session ativa pra Done → 422 "stop session first".

## 2. Não-objetivos

Já listados no preâmbulo. Reforçando o porquê de cada YAGNI:

- **Sem standalone create**: cada caminho extra de criação é code-path
  duplicado pra testar e manter. Single-path via task simplifica.
- **Sem quick session**: F4.e introduziu como back-compat de F1; com
  task-first maduro, é caminho paralelo redundante (criar task → Iniciar
  é 2 cliques, não vale o atalho).
- **Sem base-branch config**: zero usuários reportaram precisar disso.
  Adicionar = scope creep sem demanda.
- **Sem per-worktree status icon em multi-repo**: 1 task = 1 sessão
  Claude (decisão #16) → status é per-task, não per-worktree.

## 3. Decisões fechadas

| # | Decisão | Escolha | Por quê |
|---|---|---|---|
| 1 | Modelo de execução em multi-repo | 1 sessão Claude com `cwd` = diretório-pai contendo os sub-worktrees | Mantém lock "1 sessão ativa por task" sem mudança; Claude vê tudo via `cd backend; cd ../frontend` |
| 2 | Discovery de sub-repos | Auto-detect no add-project: `.git` no root → monorepo; senão scan 1 nível | Cobre 100% dos cenários do usuário sem friction extra |
| 3 | Branch naming | Auto-slug do título; campo opcional em `NewTaskForm.Avançado.branch` | Friction-free no caso comum; override pra quem usa convenção fixa (`JIRA-123/...`) |
| 4 | Base branch | HEAD de cada sub-repo (sem config) | 99% dos casos; override é YAGNI |
| 5 | Quick session | DROP | Caminho duplicado; kanban cobre |
| 6 | Worktrees externas (criadas via terminal) | Mostrar sob sub-tree "órfãs" com chip cinza | F1 já sincroniza via `git worktree list`; F5 só renderiza diferente quando `task_id IS NULL` |
| 7 | Cleanup | Auto-remove worktrees + parent dir quando task → `done`/`discarded` | Coerente com "task-first": worktree é detalhe da task |
| 8 | Layout UI | Tree expandível **task-grouped** dentro de cada projeto | Multi-repo precisa agrupar 2 worktrees da mesma task; group-by-task é natural |
| 9 | Guard terminal-state com session ativa | 422 "stop session first" | Evita git worktree remove falhar em worktree usada |
| 10 | `task.branch` editável após 1ª sessão | NÃO (422) | Mudança não retroage; refuse evita confusão |

## 4. Visualização

Drawer único "Projetos & Worktrees". Cada projeto é um nó expandível
(▼/▶) com:

- Header: nome, metadata (`monorepo · N tasks` ou `K sub-repos · N tasks`),
  botão `Excluir` (reusa F4 que faz 409 com tasks ativas).
- Sub-tree de tasks ativas (estado ∈ {`in_progress`, `review`}): cada
  task agrupando suas worktrees como leaves.
- Sub-tree "órfãs": worktrees com `task_id IS NULL` (criadas externamente
  ou cleanup que falhou).

```
┌─ Projetos & Worktrees ─────────────────────────────────┐
│                                                        │
│ ▼ gcb-financeiro             monorepo · 2 tasks ativas │
│    ▼ "Refactor login"          ● in-progress           │
│       └─ refactor-login                                │
│    ▼ "Add dark mode"           · review                │
│       └─ add-dark-mode                                 │
│    ▼ órfãs (1)                                         │
│       └─ experiment                              [✕]   │
│                                                        │
│ ▼ gcb-hub                     2 sub-repos · 1 task     │
│    ▼ "Add OAuth"               ● in-progress           │
│       ├─ backend  / add-oauth                          │
│       └─ frontend / add-oauth                          │
│                                                        │
│ ▶ projeto-3                   monorepo · 0 tasks       │
│                                                        │
│ [+ Adicionar projeto]                                  │
└────────────────────────────────────────────────────────┘
```

**Regras de renderização:**

- Tasks `idea`/`ready`/`done`/`discarded` **não aparecem**: o map é "o
  que tá no disco agora". Backlog/done ficam no kanban.
- Status icon (`●`/`·`) reflete `task.state` (não session status).
- Para multi-repo (>1 worktrees na mesma task): cada linha mostra
  `<repository.name> / <branch>`. Para monorepo (1 worktree): só
  `<branch>` (suprime `repository.name` redundante).
- Hover na linha mostra `worktree.path` completo via `title=` HTML.
- Click no nome da task abre `TaskDetailModal`.
- Botão `✕` aparece **só** em órfãs.
- Collapse-state per-projeto persistido em `localStorage` (chave
  `jarvis.proj.<id>.collapsed`).

## 5. Modelo de dados — migration 0004

### 5.1 Schema novo / modificado

**Nova tabela `repositories`:**

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

- gcb-financeiro (monorepo): 1 row com `name="gcb-financeiro"`, `sub_path="."`.
- gcb-hub (multi-repo): 2 rows com `name="backend"`/`sub_path="backend"`
  e `name="frontend"`/`sub_path="frontend"`.

**`worktrees` modificada:**

| Campo | Antes | Depois |
|---|---|---|
| `project_id` | FK NOT NULL | **REMOVIDO** (resolvido via `repository.project_id`) |
| `repository_id` | — | FK → `repositories.id` ON DELETE CASCADE, NOT NULL |
| `task_id` | — | FK → `tasks.id` ON DELETE SET NULL, **NULLable** (NULL = órfã) |
| `path` | UNIQUE | unchanged |
| `branch` | nullable | unchanged |

**`tasks` modificada:**

```python
class Task(Base):
    # ... campos existentes ...
    branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
```

Lido na 1ª `start_session` apenas. Edits após 1ª sessão recebem 422
(§6 — Edge cases).

**`sessions` (ClaudeSession) modificada:**

| Campo | Antes | Depois |
|---|---|---|
| `worktree_id` | FK NOT NULL | **REMOVIDO** |
| `cwd` | — | String(1024), NOT NULL |

`cwd` é o path absoluto onde Claude roda (e onde ai-jail spawna).
Monorepo: `cwd` = path da única worktree. Multi-repo: `cwd` = parent
dir contendo as N worktrees como subdirs.

### 5.2 Migration 0004 — passos

```
1. CREATE TABLE repositories (com UNIQUE)
2. Backfill: pra cada Project, executar _detect_repos(project.path) →
   INSERT N rows em repositories
3. ALTER worktrees:
   3a. ADD repository_id (nullable inicialmente)
   3b. ADD task_id (nullable)
4. Backfill worktrees.repository_id:
   F4 schema só permite monorepo (1 project = 1 git repo na raiz).
   Por isso, cada project terá exatamente 1 row em repositories após
   o passo 2. Match determinístico:
     UPDATE worktrees SET repository_id = (
       SELECT r.id FROM repositories r
       WHERE r.project_id = worktrees.project_id LIMIT 1
     )
   Multi-repo só começa a existir DEPOIS desta migration; nenhum
   worktree pré-existente é multi-repo. Path-prefix matching seria
   incorreto aqui porque F1 cria worktrees como siblings do
   project.path (ex: `~/projetos/proj--feature`, não dentro de
   `~/projetos/proj/`).
5. ALTER worktrees:
   5a. SET repository_id NOT NULL
   5b. CREATE FK fk_wt_repo CASCADE
   5c. CREATE FK fk_wt_task SET NULL
   5d. DROP COLUMN project_id
6. ALTER tasks: ADD branch (nullable; sem backfill — fica NULL pras
   tasks existentes)
7. ALTER sessions: ADD cwd (nullable)
8. Backfill sessions.cwd ← (SELECT worktrees.path WHERE id = sessions.worktree_id)
9. ALTER sessions: SET cwd NOT NULL + DROP worktree_id
```

Tudo dentro de `op.batch_alter_table()` pra contornar limitações do
SQLite (drop column, alter constraints).

**Roundtrip test (`test_migration_0004_roundtrip.py`):** seed F4 com
1 monorepo + 1 multi-repo + 1 worktree órfã + 1 session ativa →
upgrade → asserts (repositories criados; worktrees com repository_id
correto; sessions com cwd preenchido) → downgrade → asserts (estrutura
volta ao F4; data loss documentada).

### 5.3 Detecção de sub-repos: `_detect_repos`

Compartilhada entre migration backfill (passo 2) e fluxo
`POST /api/projects` (§6.1). Pure function, sem I/O assíncrono.

```python
@dataclass(frozen=True)
class RepoSpec:
    name: str
    sub_path: str  # relativa ao base_path

class NoGitReposError(Exception): pass

def detect_repos(base_path: Path) -> list[RepoSpec]:
    """
    1. Se base_path/.git/ existe (dir, não arquivo) → monorepo:
       return [RepoSpec(name=base_path.name, sub_path=".")]
    2. Senão, scan filhos imediatos. Pra cada child onde child/.git/ é dir:
       result.append(RepoSpec(name=child.name, sub_path=child.name))
       Ordena alfabeticamente.
    3. Se result vazio: raise NoGitReposError(base_path).
    """
```

**Edge cases cobertos:**

- Submódulos têm `.git` como **arquivo**, não dir → ignorados (correto:
  submódulo não é repo independente).
- Bare repos (sem `.git/` mas com `HEAD`+`refs/`) → não detectados; F5
  não suporta inicialmente.
- Sub-repo em depth ≥ 2 (ex: `services/backend/.git`) → não detectado;
  exige layout raso.

### 5.4 Por que normalizar (sem `Worktree.project_id`)?

- **Pros denorm**: query "worktrees do projeto X" sem JOIN. Irrelevante
  pra SQLite single-user local (sub-ms).
- **Pros normalize**: zero risco de `worktree.project_id` divergir de
  `worktree.repository.project_id`. Single source of truth.

**Escolha:** normalizar. Performance não é fator; consistência é.

### 5.5 `Repository.name` em monorepo

Para `gcb-financeiro` (monorepo), `Repository.name = "gcb-financeiro"`
(igual ao projeto). UI **suprime** exibição quando `len(worktrees_da_task) == 1`
(decisão de rendering, não de schema).

## 6. API surface

### 6.1 Endpoints — modificados / novos

| Método | Path | Mudança |
|---|---|---|
| GET | `/api/projects` | Resposta inclui `repositories: [...]` |
| POST | `/api/projects` | Detecta sub-repos via `_detect_repos`; cria N rows em `repositories` na mesma transaction; resposta inclui-as. 422 se `detect_repos` retorna vazio |
| GET | `/api/projects/{id}/worktrees` | Inclui `repository_id`, `repository_name`, `task_id`, `is_orphan` no payload |
| POST | `/api/tasks` | Aceita `branch?: str` opcional (validado: `^[a-z0-9][a-z0-9._/-]*$`, len ≤ 200) |
| PATCH | `/api/tasks/{id}` | Aceita `branch?: str`; **422** se task já tem worktrees criadas |
| POST | `/api/tasks/{id}/sessions` | **Não aceita `worktree_id`**; daemon cria worktrees + cwd + spawn. 422 se cliente legado mandar |
| PATCH | `/api/tasks/{id}` (state→done/discarded) | Cleanup automático de worktrees após state change. 422 se há session ativa |
| DELETE | `/api/worktrees/{id}` | Remove worktree órfã (git + DB). 422 se `task_id IS NOT NULL` |

### 6.2 Schemas Pydantic

```python
class RepositoryRead(BaseModel):
    id: str
    name: str
    sub_path: str
    model_config = {"from_attributes": True}

class ProjectRead(BaseModel):
    id: str
    name: str
    path: str
    created_at: datetime
    repositories: list[RepositoryRead]   # NEW

class TaskCreatePayload(BaseModel):
    project_id: str
    title: str
    description: str = ""
    branch: str | None = None             # NEW; regex validated

class TaskPatchPayload(BaseModel):
    title: str | None = None
    description: str | None = None
    state: str | None = None
    branch: str | None = None             # NEW

class TaskRead(BaseModel):
    # ... existing fields ...
    branch: str | None                    # NEW

class WorktreeRead(BaseModel):
    id: str
    repository_id: str                    # NEW
    repository_name: str                  # NEW (denormalized for UI)
    task_id: str | None                   # NEW
    path: str
    branch: str | None
    is_orphan: bool                       # NEW (computed: task_id is None)
    model_config = {"from_attributes": True}

class SessionCreatePayload(BaseModel):
    """Empty payload — F5 daemon decides cwd. `extra=forbid` faz Pydantic
    rejeitar campos não declarados (ex: `worktree_id` legado de F4)
    com 422 automático, sem precisar de check manual no handler.
    """
    model_config = {"extra": "forbid"}
```

### 6.3 Fluxo de `POST /api/tasks/{id}/sessions` (refatorado)

```
1. Get task; check state ∈ {idea, ready, review, in_progress};
   sem session ativa
2. Get task.project + repositories
3. branch_slug = task.branch OR slugify_for_branch(task.title)
4. Has existing worktrees pra essa task?
   SIM (re-iniciar) → cwd derivada do parent das worktrees existentes;
        skip steps 4a-4f. Vai direto pro step 5.
   NÃO (1ª sessão) → executa steps 4a-4f abaixo:
     a. cwd = <dirname(project.path)>/<basename(project.path)>--<branch_slug>
     b. Refuse 422 se cwd existe OU branch_slug existe em qualquer
        sub-repo (validação preemptiva, ANTES de qualquer side-effect).
        OBS: 4b SÓ ocorre na 1ª sessão (branch NÃO acima).
     c. Multi-repo (len(repos) > 1): mkdir cwd
        Monorepo: skip (git worktree add cria o dir)
     d. created: list[Path] = []
        Para cada repository (em ordem):
          - Multi-repo: target = cwd/<repo.name>
          - Monorepo:   target = cwd
          - try:
              await git.add(<project.path>/<repo.sub_path>, target, branch_slug)
              created.append(target)
              wt = Worktree(repository_id=repo.id, task_id=task_id,
                            path=str(target), branch=branch_slug)
              session.add(wt)
              await session.flush()  # mint wt.id sem commitar ainda
              new_worktree_rows.append(wt)
            except (GitWorktreeError, OSError):
              ROLLBACK (4e_rollback abaixo)
              raise

     e. await session.commit()
        # Worktree rows persistem; cwd + dirs no disco existem.

     f. Para cada wt in new_worktree_rows:
          await broadcaster.publish(WsEvent.worktree_created(wt))
        # Broadcasts SÓ depois do commit. Garante que clientes nunca
        # vejam worktree "fantasma" que foi rollback'ed.

     4e_rollback (se step 4d falha em qualquer iteração):
       for target in reverse(created):
         try: await git.remove(<project.path>/<repo.sub_path>, target, force=True)
         except: log warning (best-effort em rollback)
       if multi-repo and cwd.exists() and cwd is empty:
         try: cwd.rmdir()
         except OSError: pass
       await session.rollback()
       # Estado pós-rollback: nada no disco, nada no DB, ZERO broadcasts
       # disparados — clientes nunca souberam que tentamos.

5. Auto-transition task.state idea/ready/review → in_progress
   (set task.state, await session.commit(),
    broadcast task.updated se mudou)
6. Spawn Claude via runtime.spawn(cwd, ...)
   IF runtime.spawn falha após worktrees terem sido criadas (caso 1ª
   sessão), executar 4e_rollback completo + reverter task.state
   (`row.state = previous_state`; await commit; broadcast
   task.updated com new_state=previous_state pra UI refletir reversão)
   (raise — usuário tenta de novo após corrigir runtime).
7. INSERT ClaudeSession(task_id, cwd=str(cwd), status=executing, ...)
8. await session.commit()
9. Return SessionRead
```

**Rollback atômico em 3 camadas:**
- **Filesystem:** worktrees criadas via `git worktree remove --force`;
  cwd dir removido se ficar vazio.
- **DB:** rollback de transaction; rows nunca commitadas.
- **WS:** broadcasts só disparados após commit (step 4f). Em caso
  de rollback, ZERO `worktree.created` foi emitido — clientes nunca
  souberam.

**Re-iniciar (session N+1):** se task já tem worktrees, daemon **não**
recria — apenas re-spawna Claude no mesmo cwd. Permite "stop +
re-start" sem nuke do trabalho. Steps 4a-4f não são executados; vai
direto pra step 5 → 6 → 7 → 8 → 9.

### 6.4 Cleanup em PATCH state → done/discarded

#### 6.4.1 Call site & ordering (em `api/tasks.py::patch_task`)

```python
@router.patch("/{task_id}", response_model=TaskRead)
async def patch_task(task_id, payload, request, db, ...):
    # ... validação payload ...
    try:
        row, previous_state = await update_task(
            db, task_id,
            title=payload.title,
            description=payload.description,
            state=payload.state,
            branch=payload.branch,
        )
        # update_task internamente:
        #   1. Valida transição via state machine
        #   2. Se state ∈ {done, discarded}: checa _count_active_sessions
        #      → raise TaskHasActiveSessionError se > 0
        #   3. Se branch e _count_worktrees > 0: raise BranchImmutable...
        #   4. Mutate row (inclui state)
        #   5. await db.commit()
    except TaskNotFoundError as exc:
        raise HTTPException(404, ...) from exc
    except (TaskHasActiveSessionError, BranchImmutableAfterFirstSessionError,
            InvalidTaskTitleError, InvalidTransitionError, InvalidBranchOverrideError) as exc:
        raise HTTPException(422, ...) from exc

    # NESSE PONTO: state transition já está committed no DB.
    # Cleanup roda em transaction separada; soft-fail é OK.
    if payload.state in ("done", "discarded"):
        await cleanup_task_worktrees(db, git, broadcaster, task_id)
        # Internamente: per-worktree git remove + DELETE row OU mark
        # orphan; await db.commit().

    # Broadcast task.updated DEPOIS de cleanup (estado final correto).
    if broadcaster is not None and previous_state is not None:
        await broadcaster.publish(WsEvent.task_updated(...))

    return await _build_task_read(db, task_id)
```

**Ordem invariável:**
1. `update_task` (state mutation + commit) — guarda de active session
   roda DENTRO desta chamada, ANTES de mutar nada.
2. `cleanup_task_worktrees` (worktrees + commit) — só roda se state
   foi pra `done`/`discarded`.
3. `broadcast task.updated` — depois de ambos, refletindo estado final
   incluindo orphans gerados por cleanup soft-fail.

Essa ordem garante:
- Active-session guard previne cleanup com Claude rodando.
- State mutation é durable mesmo se cleanup falha em cascata.
- Cleanup soft-fail orfana rows na **mesma transaction da remoção**;
  durabilidade preservada.
- WS final reflete a verdade pós-cleanup.

#### 6.4.2 `cleanup_task_worktrees` (em `core/worktrees.py`)

```python
async def cleanup_task_worktrees(
    session: AsyncSession,
    git: GitWorktreeOps,
    broadcaster: WsBroadcaster | None,
    task_id: str,
) -> None:
    """Remove worktrees fisicamente + DB rows.
    Tolerante a falhas: git worktree remove falhar deixa row como órfã
    (task_id=NULL) em vez de bloquear a transição de estado da task.
    Faz seu próprio commit ao final."""
    wts = await list_worktrees_for_task(session, task_id)
    if not wts:
        return

    cwds: set[Path] = set()
    pending_broadcasts: list[WsEvent] = []
    for wt in wts:
        repo = await session.get(Repository, wt.repository_id)
        project = await session.get(Project, repo.project_id)
        repo_full = Path(project.path) / repo.sub_path
        wt_path = Path(wt.path)
        cwds.add(wt_path.parent)
        try:
            await git.remove(repo_full, wt_path, force=True)
            project_id = repo.project_id
            wt_id = wt.id
            await session.delete(wt)
            pending_broadcasts.append(WsEvent.worktree_removed(
                worktree_id=wt_id, project_id=project_id, task_id=task_id,
            ))
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            _log.warning(f"cleanup of {wt_path} failed: {exc}; orphaning")
            wt.task_id = None
            pending_broadcasts.append(WsEvent.worktree_orphaned(
                worktree_id=wt.id, project_id=repo.project_id, path=wt.path,
            ))

    await session.commit()
    # rmdir cwds vazios (wrapper de multi-repo)
    for cwd in cwds:
        if cwd.exists() and not list(cwd.iterdir()):
            try: cwd.rmdir()
            except OSError: pass
    # Broadcasts só após commit (mesma garantia do start_session)
    if broadcaster:
        for event in pending_broadcasts:
            await broadcaster.publish(event)
```

Mesmo padrão de atomicidade do `start_session`: mutate → commit →
broadcast. Falha mid-loop não emite broadcasts (objects continuam
no DB com state pré-falha; próxima tentativa de cleanup retoma).

### 6.5 WS events novos

| Type | Quando | Payload |
|---|---|---|
| `worktree.created` | após `git worktree add` OK + INSERT | `{worktree_id, project_id, repository_id, task_id, path, branch}` |
| `worktree.removed` | após `git worktree remove` + DELETE | `{worktree_id, project_id, task_id}` |
| `worktree.orphaned` | quando cleanup falha → task_id=NULL | `{worktree_id, project_id, path}` |

`useSessionEvents` (F4.k) ganha extensão pra invalidar
`queryKeys.worktrees(projectId)` nesses tipos. `worktree.orphaned` dispara
toast informativo.

### 6.6 Hard-break em `POST /api/tasks/{id}/sessions`

Cliente legado mandando `{ worktree_id: "..." }` recebe **422**.

A mensagem default do Pydantic (`"Extra inputs are not permitted"`)
é suficiente; se quiser detail mais explicativo, implementar com
`@field_validator` no `SessionCreatePayload` levantando
`ValueError("F5: worktree_id removido; daemon decide o cwd")`.

Sem silently degrade — F5 é major, força front a se atualizar.

## 7. Core layer

### 7.1 Mapa de mudanças por módulo

| Módulo | Mudança |
|---|---|
| `core/git.py` | + Protocol `GitWorktreeOps` + impl `SubprocessGitWorktreeOps` + `add`/`remove` ops |
| `core/repositories.py` | **NOVO** — `detect_repos`, `list_project_repositories` |
| `core/projects.py` | `create_project` chama `detect_repos`, INSERT em `repositories` na mesma transaction |
| `core/worktrees.py` | `list_project_worktrees` itera sobre repositories; novas funções |
| `core/sessions.py` | `start_session` refatorado (signature, cwd derivado, atomic spawn) |
| `core/tasks.py` | + branch field handling + terminal-state guard + cleanup hook |
| `core/slug.py` | **NOVO** — `slugify_for_branch` |

### 7.2 `GitWorktreeOps` Protocol

```python
class GitWorktreeError(Exception): pass

class GitWorktreeOps(Protocol):
    async def list(self, repo: Path) -> list[WorktreeInfo]: ...
    async def add(self, repo: Path, target: Path, branch: str) -> None: ...
    async def remove(self, repo: Path, target: Path, *, force: bool = False) -> None: ...

class SubprocessGitWorktreeOps:
    async def add(self, repo: Path, target: Path, branch: str) -> None:
        # asyncio.to_thread(subprocess.run, [
        #     "git", "-C", str(repo),
        #     "worktree", "add", str(target), "-b", branch
        # ], check=True, capture_output=True)
        # raise GitWorktreeError on CalledProcessError
        ...
```

**Test seams:**
- Unit: `FakeGitWorktreeOps` registra `(repo, target, branch)` calls,
  emula state local.
- Integration: real subprocess + tmpdir + git real (via `_make_repo`
  helper de F4 conftest).

### 7.3 `slugify_for_branch`

```python
class InvalidBranchSlugError(Exception): pass

def slugify_for_branch(text: str) -> str:
    """Auto-slug pra default de Task.branch.
    Regras: lowercase, espaços/punct → hyphen, collapse hyphens,
    strip leading/trailing, truncate 60.
    """
    s = text.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    if not s:
        raise InvalidBranchSlugError(f"cannot slugify '{text}' to a valid branch name")
    return s[:60].rstrip("-")
```

**Override do usuário** (`task.branch`) tem regex mais permissivo
(`^[a-z0-9][a-z0-9._/-]*$`, max 200) — permite prefixos como
`feature/JIRA-123-fix`.

### 7.4 `start_session` — assinatura nova

```python
async def start_session(
    session: AsyncSession,
    runtime: SessionRuntime,
    git: GitWorktreeOps,           # NOVO seam
    *,
    task_id: str,                  # mantém
    # worktree_id: str,            REMOVIDO
    token_registry: TokenRegistry | None = None,
    base_url: str | None = None,
) -> ClaudeSession:
    ...
```

`_derive_cwd(project_path, branch_slug)`:

```python
def _derive_cwd(project_path: str, branch_slug: str) -> Path:
    p = Path(project_path)
    return p.parent / f"{p.name}--{branch_slug}"
```

Mesma fórmula em monorepo e multi-repo. O que muda é o conteúdo do dir
(worktree direta vs N sub-worktrees).

### 7.5 `cleanup_task_worktrees` (em `core/worktrees.py`)

Já mostrada em §6.4. Soft-fail: cada worktree falha individualmente
sem bloquear as outras nem a transição de estado da task.

### 7.6 Funções de query novas

```python
# core/repositories.py
async def list_project_repositories(session, project_id) -> list[Repository]:
    """Returns repositories em ordem determinística (sub_path ASC)."""

# core/worktrees.py
async def list_worktrees_for_task(session, task_id) -> list[Worktree]: ...
async def list_orphan_worktrees(session, project_id) -> list[Worktree]: ...
async def delete_worktree(session, git, worktree_id) -> None:
    """Pra DELETE /api/worktrees/{id} de órfãs.
    Refuse com WorktreeNotOrphanError se task_id IS NOT NULL."""
```

### 7.7 `list_project_worktrees` refatorado

F1 chamava `git -C <project.path> worktree list`. Pra multi-repo,
quebra. F5:

```python
async def list_project_worktrees(
    session: AsyncSession,
    git: GitWorktreeOps,
    project_id: str,
) -> Sequence[Worktree]:
    project = await session.get(Project, project_id)
    repos = await list_project_repositories(session, project_id)

    discovered: dict[str, tuple[Repository, WorktreeInfo]] = {}
    for repo in repos:
        try:
            infos = await git.list(Path(project.path) / repo.sub_path)
        except GitWorktreeError as exc:
            _log.warning(f"git list failed in {repo.sub_path}: {exc}")
            continue
        for info in infos:
            discovered[info.path] = (repo, info)

    by_path = await _load_worktrees_by_path(session, project_id)
    for path, (repo, info) in discovered.items():
        existing = by_path.get(path)
        if existing is None:
            session.add(Worktree(
                repository_id=repo.id,
                task_id=None,             # órfã (criada externamente)
                path=path,
                branch=info.branch,
            ))
        elif existing.branch != info.branch:
            existing.branch = info.branch

    await session.commit()
    return await _list_all_worktrees_of_project(session, project_id)
```

Insere worktrees criadas externamente como **órfãs** (`task_id=None`).
Sub-repo path quebrado: log + skip aquele sub-repo (não derruba o sync
inteiro).

### 7.8 `core/tasks.py` — guard novo

```python
class TaskHasActiveSessionError(Exception): pass

async def update_task(session, task_id, *, state=None, branch=None, ...):
    ...
    if state in ("done", "discarded"):
        active_count = await _count_active_sessions(session, task_id)
        if active_count > 0:
            raise TaskHasActiveSessionError(
                "task has active session; stop it before completing/discarding"
            )

    if branch is not None:
        wts_count = await _count_worktrees_for_task(session, task_id)
        if wts_count > 0:
            raise BranchImmutableAfterFirstSessionError(
                "branch cannot be changed after worktrees were created; "
                "discard task and recreate"
            )
        # validar regex permissiva
        if not _BRANCH_OVERRIDE_RE.match(branch):
            raise InvalidBranchOverrideError(
                f"branch must match ^[a-z0-9][a-z0-9._/-]*$"
            )
        row.branch = branch
    ...
```

API mapeia ambos `TaskHasActiveSessionError` e
`BranchImmutableAfterFirstSessionError` para 422.

## 8. Frontend

### 8.1 Mapa de componentes

| Componente | Mudança |
|---|---|
| `ProjectsDrawer.tsx` | **Reescrito** — drop quick session inline, vira container |
| `ProjectNode.tsx` | **NOVO** — projeto expansível com tasks ativos + órfãs |
| `TaskWorktreeGroup.tsx` | **NOVO** — header de task + worktrees como filhos |
| `OrphansGroup.tsx` | **NOVO** — sub-tree colapsável de órfãs |
| `WorktreeRow.tsx` | **NOVO** — 1 linha de worktree |
| `NewTaskForm.tsx` | + `<details>` "Avançado ▾" com campo `branch` |
| `TaskDetailModal.tsx` | **Remove worktree picker**; mostra branch (read-only após 1ª sessão); `▶ Iniciar` vira único botão |
| `useSessionEvents.ts` | + handlers `worktree.created/removed/orphaned` |
| `lib/api.ts` | + `deleteWorktree`; tipos atualizados |
| `lib/slug.ts` | **NOVO** (espelho client-side de `slugify_for_branch` pra placeholder/preview) |

### 8.2 ProjectsDrawer (estrutura)

```tsx
<aside role="dialog" aria-label="projects-drawer">
  <header>
    <h2>Projetos & Worktrees</h2>
    <button onClick={onClose} aria-label="close-drawer">✕</button>
  </header>
  <CreateProjectForm />
  {projects.data?.map(p => <ProjectNode key={p.id} project={p} />)}
  {toast && <Toast message={toast} />}
</aside>
```

`<ProjectNode>` faz fetch via `queryKeys.worktrees(project.id)` +
`queryKeys.tasksForProject(project.id)`, separa em buckets
(`active` por `state ∈ {in_progress, review}` + has worktrees;
`orphans` por `task_id IS NULL`), renderiza tree.

### 8.3 NewTaskForm — campo Avançado.branch

```tsx
<details>
  <summary>Avançado ▾</summary>
  <input
    aria-label="task-branch"
    placeholder={slugifyForBranch(title) || "auto-slug do título"}
    pattern="^[a-z0-9][a-z0-9._/-]*$"
    maxLength={200}
  />
  <p className="hint">Vazio: usa slug do título. Aceita prefixos como
    "feature/JIRA-123".</p>
</details>
```

Slug preview no `placeholder` recomputado via `slugifyForBranch(title)`
(client-side mirror) toda vez que `title` muda.

### 8.4 TaskDetailModal — diff

**Remove:**
```tsx
<select name="worktree">{worktrees.map(...)}</select>
<button onClick={() => startSession(taskId, selectedWorktreeId)}>
  ▶ Iniciar sessão
</button>
```

**Substitui por:**
```tsx
{task.branch && <p>Branch: <code>{task.branch}</code></p>}
{!hasWorktrees && (
  <BranchEditField
    value={task.branch}
    onChange={(v) => patchTask({ branch: v })}
  />
)}
<button onClick={() => startTaskSession(taskId)}>▶ Iniciar sessão</button>
{hasWorktrees && (
  <details>
    <summary>Worktrees ({task.worktrees.length})</summary>
    <ul>{task.worktrees.map(w => (
      <li key={w.id}>{w.repository_name}: <code>{w.path}</code></li>
    ))}</ul>
  </details>
)}
```

`startTaskSession(taskId)` — sem `worktree_id`. Em sucesso, invalida
`queryKeys.worktrees(project_id)` + `queryKeys.tasks` + `queryKeys.sessions`.

### 8.5 useSessionEvents — extensão

```tsx
const HANDLERS: Record<string, Handler> = {
  // ... existing F4 handlers ...
  'worktree.created': (qc, e) =>
    qc.invalidateQueries({ queryKey: queryKeys.worktrees(e.payload.project_id) }),
  'worktree.removed': (qc, e) =>
    qc.invalidateQueries({ queryKey: queryKeys.worktrees(e.payload.project_id) }),
  'worktree.orphaned': (qc, e) => {
    qc.invalidateQueries({ queryKey: queryKeys.worktrees(e.payload.project_id) });
    showToast(`Worktree não pôde ser removida: ${e.payload.path}`);
  },
};
```

### 8.6 LocalStorage

| Chave | Valor | Uso |
|---|---|---|
| `jarvis.proj.<id>.collapsed` | boolean | Collapse-state por projeto na drawer |
| `jarvis.kanban.filters` | `string[]` | já existente (F4.l) |

## 9. Edge cases & error handling

### 9.1 Catálogo de erros

| Cenário | HTTP | Detail | Recuperação |
|---|---|---|---|
| Add project: path inexistente | 422 | `path doesn't exist` | Usuário corrige |
| Add project: nem `.git` no root, nem em subdirs | 422 | `no git repos found in <path> or 1 level below` | Usuário aponta pra repo válido |
| Add project: path duplicado | 409 | `path already used by project X` | F4 |
| Iniciar (1ª vez): branch slug existe em qualquer sub-repo | 422 | `branch '<slug>' already exists in <repo>; set task.branch to override` | Edita `task.branch` |
| Iniciar (1ª vez): cwd path já existe | 422 | `cwd path '<cwd>' already exists` | Renomeia/limpa. Não dispara em re-iniciar (cwd existe por design) |
| Iniciar (1ª vez): title slugifica vazio | 422 | `cannot derive branch slug from title; set task.branch manually` | Define branch |
| Iniciar: `git worktree add` falha em sub-repo | 500 | `git worktree add failed: <stderr>` | Daemon faz rollback parcial |
| Iniciar: `runtime.spawn` falha após worktrees criadas | 500 | `spawn failed: <reason>` | Daemon remove worktrees |
| Iniciar: task em `done`/`discarded` | 409 | F4 |  |
| Iniciar: task com session ativa | 409 | F4 |  |
| PATCH state→done/discarded com session ativa | 422 | `task has active session; stop it first` | **NOVO em F5** |
| PATCH branch=... com worktrees criadas | 422 | `branch cannot be changed after worktrees were created` | UI desabilita campo |
| DELETE worktree: não-órfã | 422 | `worktree belongs to active task` | Cleanup só via state→done |
| DELETE worktree: `git worktree remove` falha | 500 | `<stderr>` | Manual no terminal |
| Cleanup: 1 de N worktrees falha | — (não falha API) | — | Vira órfã + WS event + toast |

### 9.2 Race conditions

| Race | Mitigação |
|---|---|
| Duas tabs disparam Iniciar sessão na mesma task | F4.c per-task `asyncio.Lock` + check active count → 2ª 409 |
| Iniciar simultâneo em 2 tasks com mesmo branch slug | `git worktree add` falha na 2ª (branch exists) → rollback + 422 |
| User PATCH state→done enquanto outra tab inicia | 1ª transação ganha; 2ª vê estado terminal e falha 409 |
| User deleta projeto enquanto sessão ativa | F4 RESTRICT bloqueia |
| User cria worktree externamente entre 2 syncs | Sync seguinte insere como órfã |
| Cleanup paralelo de mesma task (state→done duas vezes) | 2ª chamada vê `list_worktrees_for_task = []` → no-op |

### 9.3 Multi-repo: assimetrias

| Cenário | Comportamento |
|---|---|
| Branch slug existe em backend mas não em frontend | Refuse 422 — nome único globalmente entre sub-repos |
| HEAD de backend e frontend divergem | OK — cada `git worktree add` deriva do seu HEAD |
| Sub-repo adicionado depois do add-project | Não auto-detectado; usuário remove + re-adiciona projeto |
| Sub-repo removido fisicamente | `list_project_worktrees` skipa esse sub-repo (try/except) |
| 1 sub-repo é submódulo (`.git` é arquivo) | `_detect_repos` ignora |

### 9.4 Cleanup parcial

```
Cenário B (1 sub-repo dirty):
  ✓ git remove backend/add-oauth → DELETE row + WS worktree.removed
  ✗ git remove frontend/add-oauth (changes não commited)
  → frontend.task_id = NULL → WS worktree.orphaned + toast
  → cwd não vazio (frontend/ ainda lá) → rmdir skip
  → task.state = done. ✓
  → Map: backend sumiu, frontend aparece em "órfãs"
```

### 9.5 Worktrees externas

| Cenário | Comportamento |
|---|---|
| User cria via terminal | Próximo sync insere como órfã |
| Path colide com convenção do daemon (`<project>--<slug>`) | UNIQUE em `worktrees.path` faz INSERT falhar; sync loga warning. Edge raro |
| User remove worktree manualmente (rm -rf) | Sync seguinte: row stale; UI mostra normal mas `git worktree remove` provavelmente falha. **MVP: leave-as-is** |
| Re-init de repo (.git apagado e recriado) | Worktrees do .git antigo somem do `git worktree list`; rows DB ficam stale. **MVP: leave-as-is** |

### 9.6 Migration 0004 — downgrade lossy

Upgrade é determinístico. **Downgrade perde:**

- `tasks.branch` → drop column
- `worktrees.task_id` → drop column
- `repositories` table → drop
- `sessions.cwd` → tentar recriar `sessions.worktree_id` escolhendo
  qualquer worktree da task. **Pra multi-repo perde a noção de
  parent-cwd.** F4 schema não suporta o conceito.

**Decisão:** downgrade implementado em best-effort com docstring
documentando perdas. Para single-user local dev, `rm jarvis.db` é a
saída sã se rollback for necessário após uso real do F5.

### 9.7 Logging

| Evento | Nível | Onde |
|---|---|---|
| `git worktree add` succeeded | DEBUG | `core.git` |
| `git worktree add` failed | ERROR | `core.git` (com stderr completo) |
| Rollback de spawn (criação parcial revertida) | WARNING | `core.sessions` |
| Cleanup soft-fail (worktree → órfã) | WARNING | `core.worktrees` |
| `_detect_repos` produces 0 repos | WARNING | `core.repositories` |
| Migration 0004 backfill row count | INFO | `alembic/env.py` |

## 10. Testing strategy

### 10.1 Por camada

| Camada | Alvo | Adições no F5 |
|---|---|---|
| Unit Python | 100% | ~9 arquivos novos + 4 extensões |
| Integration | 100% das rotas | ~13 arquivos (incl. migration roundtrip) |
| Frontend Vitest | 100% em `lib/`, `hooks/`, `stores/` | 5 novos files; 3 extensões |
| E2E | 100% dos fluxos novos | 3 fluxos |

### 10.2 Unit Python

```
tests/unit/
├── test_detect_repos.py                  monorepo / multi-repo / no-repos / submodule (.git as file) / depth-2 reject
├── test_slugify_for_branch.py            edges: empty, "...", unicode, length truncate, collapse hyphens
├── test_repositories_crud.py             list_project_repositories ordering + lookup
├── test_session_start_atomic.py          FakeGitOps: 2nd add fails → 1st removed, cwd rmdir
├── test_session_start_re_iniciar.py      task com worktrees existentes → reuse cwd, no novo git add
├── test_session_start_no_worktree_id.py  signature exige task_id only
├── test_session_start_branch_clash.py    branch já existente → BranchSlugClashError
├── test_worktrees_cleanup_soft_fail.py   FakeGitOps: 1 falha → orphan + outro removido
├── test_task_state_done_active_session_guard.py  novo guard em update_task
├── test_ws_envelope_worktrees.py         factories worktree.created/removed/orphaned
└── test_task_branch_validation.py        regex de override + auto-slug rules
```

### 10.3 Integration (rotas + git real)

```
tests/integration/
├── test_migration_0004_roundtrip.py            seed F4 (1 monorepo + 1 multi-repo + 1 órfã + 1 session ativa) → upgrade → asserts; downgrade → asserts (best-effort)
├── test_projects_create_detects_repos.py       POST /projects (monorepo path) → 1 repo; (multi-repo) → 2 repos
├── test_repositories_in_projects_response.py   GET /projects retorna `repositories: [...]`
├── test_task_session_monorepo_flow.py          POST task → POST session → 1 worktree + cwd derivado
├── test_task_session_multi_repo_flow.py        POST task → POST session → 2 worktrees + cwd parent + claude spawn em cwd parent
├── test_task_session_re_iniciar.py             stop → start novamente → mesmo cwd, sem git add novo
├── test_task_session_branch_clash_422.py       branch existe em sub-repo → 422 + nada criado
├── test_task_state_done_triggers_cleanup.py    PATCH done → worktrees removidas + cwd rmdir + WS events
├── test_task_state_done_blocked_active_session.py  active session → 422
├── test_cleanup_soft_fail_orphans.py           sub-repo dirty → 1 worktree vira órfã + WS worktree.orphaned
├── test_delete_orphan_worktree.py              DELETE /worktrees/{id} de órfã → 204; de não-órfã → 422
├── test_external_worktree_appears_as_orphan.py git worktree add manual → sync insere como órfã
└── test_branch_override_field.py               POST /tasks com branch="feature/foo" → respeitado em start_session
```

### 10.4 Frontend Vitest

```
ui/src/
├── components/
│   ├── ProjectNode.test.tsx              tree expansion; activeTasks filter; orphans count
│   ├── TaskWorktreeGroup.test.tsx        showRepoName lógica (1 vs N); status badge
│   ├── WorktreeRow.test.tsx              render + remove button + tooltip path
│   ├── OrphansGroup.test.tsx             list + delete trigger + confirmação
│   ├── NewTaskForm.test.tsx              EXTEND: campo Avançado.branch + slug preview
│   └── TaskDetailModal.test.tsx          EXTEND: sem worktree picker; branch display
├── hooks/
│   └── useSessionEvents.test.ts          EXTEND: worktree.* WS handling
└── lib/
    ├── api.test.ts                       EXTEND: deleteWorktree
    └── slug.test.ts                      NOVO: client mirror de slugify_for_branch
```

### 10.5 E2E (do host, fora da jaula)

```
tests/e2e/
├── test_f5_monorepo_flow.py              add proj monorepo → criar task → iniciar → ver no map → stop → done → map vazio
├── test_f5_multi_repo_flow.py            add proj multi-repo → criar task → iniciar → ver 2 worktrees agrupadas → done → cleanup
└── test_f5_orphan_visible.py             add projeto + externamente criar worktree → reload UI → órfã visível → remover via UI
```

## 11. Rollout — sub-tasks F5.0 → F5.l

| # | Sub-task | Entregável | Dependências |
|---|---|---|---|
| F5.0 | Spike: `git worktree add/remove` em multi-repo + ai-jail config check | Confirmar que ai-jail rw_maps cobre cwd com N sub-`.git`s | — |
| F5.a | Migration 0004 + Repository model + roundtrip test | Schema verde | F5.0 |
| F5.b | `core/repositories.py` + `detect_repos` | Pure function + unit tests | F5.a |
| F5.c | `core/git.py` extension: Protocol + `SubprocessGitWorktreeOps` | Inject seam ready | F5.a |
| F5.d | `core/sessions.py` refactor: signature, atomic spawn, rollback | Unit + integration | F5.b, F5.c |
| F5.e | `core/tasks.py`: branch field + terminal-state guard + cleanup hook | Tasks core ready | F5.a |
| F5.f | `core/worktrees.py`: cleanup_task_worktrees + list_worktrees_for_task + delete_worktree | Sync refactor | F5.c, F5.e |
| F5.g | API routes: detects on POST /projects; GET /projects.repositories; POST /tasks/{id}/sessions sem worktree_id; PATCH branch; DELETE /worktrees/{id} | API surface ready | F5.d, F5.f |
| F5.h | WS envelope: worktree.* factories + broadcasts em pontos certos | UI pode escutar | F5.g |
| F5.i | UI lib: api.ts types + `slugifyForBranch` espelho client + `useLocalStorage` helper | Frontend infra | — |
| F5.j | UI components: ProjectsDrawer rewrite + ProjectNode + TaskWorktreeGroup + WorktreeRow + OrphansGroup | Map renderizado | F5.h, F5.i |
| F5.k | UI: NewTaskForm.Avançado + TaskDetailModal sem picker + useSessionEvents WS extension | Forms/handlers ready | F5.j |
| F5.l | E2E flows + ARCHITECTURE update + ADR-0015/0016/0017 + Demo manual | Fechamento | F5.k |

Cada sub-task termina com:
- TDD verde (unit + integration onde aplicável)
- Coverage gate 100% (auto-marker em `tests/conftest.py` da F4.m mantém disciplina)
- Pre-commit code review subagent
- Commit dedicado (padrão `feat(F5.X): ...`)

## 12. Riscos antecipados

| Risco | Mitigação |
|---|---|
| **ai-jail rw/ro maps** com cwd contendo N sub-`.git`s pode quebrar | F5.0 spike valida primeiro; se quebrar, ajustar `sandbox/aijail.py` antes de F5.a |
| Migration 0004 backfill com path-matching pode falhar em edge cases (worktrees em paths atípicos) | Roundtrip test com seed realista; se falhar, log warning + skip row em vez de crashar |
| Rollback parcial em `start_session` multi-repo é caminho não-trivial | Unit test com FakeGitOps simulando falha em cada índice possível |
| Cleanup soft-fail pode acumular órfãs silenciosas | Toast + WS event garantem visibilidade; UI distingue órfãs visualmente |
| Downgrade de 0004 é lossy | Documentado em docstring; usuário sabe que rollback após uso multi-repo perde dados |
| `tasks.branch` editável só pré-1ª-sessão é regra implícita | Server hard-rejects 422; UI desabilita campo após `task.worktrees.length > 0` |

## 13. ADRs novas

A escrever em F5.l:

- **ADR-0015** — Project = lista de sub-repos com auto-detect.
  Justifica saída do model "1 project = 1 git repo" pra suportar
  multi-repo (gcb-hub).
- **ADR-0016** — Multi-repo: 1 sessão Claude com cwd no parent dir.
  Documenta alternativas descartadas (2 sessões simultâneas; 1 sessão
  por vez) e razão de manter "1 sessão por task" simples.
- **ADR-0017** — Worktree é detalhe de implementação da Task.
  Justifica ausência de standalone create UI e remoção da Quick session.

## 14. Demo manual (F5.l, do host)

1. Subir daemon + UI (`make dev`)
2. Adicionar projeto monorepo (mock: `git init` em `~/tmp/proj-mono`)
   → ver "monorepo" + 1 repo
3. Adicionar projeto multi-repo (`~/tmp/proj-multi/{backend,frontend}`
   cada um com `git init`) → ver "2 sub-repos"
4. Criar task "Add OAuth" no projeto multi-repo (com Avançado.branch =
   `feature/add-oauth`)
5. Click ▶ Iniciar sessão (do kanban) → ver 2 worktrees criadas no map
6. `ls ~/tmp/proj-multi--feature-add-oauth/` → ver `backend/` e `frontend/`
7. Terminal nativo abre com cwd = parent
8. Drag task → Done no kanban → toast + worktrees somem do map + dirs
   removidos
9. Externamente: `git -C ~/tmp/proj-mono worktree add ../proj-mono--external -b external`
   → reload UI → órfã sob proj-mono
10. Click `✕ Remover` na órfã → confirmação → some + dir removido
11. Tentar mover task com session ativa pra Done → 422 "stop session first"
12. Stop → drag pra Done → cleanup OK
13. Criar 2 tasks com mesmo título "Fix bug" → 1ª inicia OK → 2ª inicia
    → 422 com hint "edite task.branch"
14. Editar 2ª task → branch = `fix-bug-2` → iniciar → OK

## 15. Referências

- `ARCHITECTURE.md` §1.2 (task-first), §3 (modelo de dados), §11 (roadmap)
- ADR-0007 (task-first)
- ADR-0012 (Task como entidade primária)
- ADR-0008 (sessão em terminal nativo)
- ADR-0009 (hooks via settings.json no jail)
- ADR-0010 (envelope WS canal único)
- F4 spec: `docs/superpowers/specs/2026-05-09-f4-backlog-kanban-design.md`
- F4 plan: `docs/superpowers/plans/2026-05-09-f4-backlog-kanban.md`
- `gotchas.md` #9 (E2E fora da jaula), #11 (auto-marker tests)
