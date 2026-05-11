# ADR-0018: RunInstance é detalhe da task; 1 run ativa por task

- **Status:** Accepted
- **Data:** 2026-05-11
- **Decisores:** Marcos

## Contexto

F6 (Run from Panel) sobe a stack dev (DB + serviços) pra uma task ativa.
A pergunta inicial: como `RunInstance` se vincula ao modelo task-first
estabelecido em F4/F5? Worktree foi promovida a "detalhe da task" em
ADR-0017; ClaudeSession ganhou `task_id` em ADR-0012. RunInstance segue
o mesmo padrão ou tem ciclo de vida próprio (e.g., compartilhada entre
tasks)?

## Decisão

**RunInstance carrega `task_id` (FK, NOT NULL, CASCADE)**. Paralelo a
ClaudeSession e Worktree pós-F5:

```python
class RunInstance(Base):
    id: str
    task_id: str   # FK tasks.id ON DELETE CASCADE
    cwd: str       # mesmo da ClaudeSession.cwd quando há session ativa
    manifest_path: str
    status: Literal[
        "pending", "building", "seeding", "ready",
        "failed", "stopping", "stopped"
    ]
    ports_json: str     # {<service>: <host_port>}
    containers_json: str  # {<service>: <container_id>}
    network_name: str   # jarvis-run-<short_id>
    started_at: datetime
    ended_at: datetime | None
    error_message: str | None
```

**Invariants:**

- **1 run ativa por task** — partial unique index
  `ix_run_instances_active_task` em `task_id WHERE ended_at IS NULL`.
  Runs finalizadas (`ended_at != NULL`) acumulam audit trail.
- **Run requer task em `in_progress` ou `review`** — `start_run` valida;
  outras states retornam 422.
- **Cleanup automático em terminal state** — task → `done`/`discarded`
  chama `stop_run(reason="task_terminal")` antes do worktree cleanup F5.
- **Cleanup automático em session stop** — F6.k hook em `stop_session`
  chama `stop_run(reason="session_stopped")` (lifecycle layer 2 do spec §3).
- **`cwd` deriva da session ativa** — se task tem session, usa
  `ClaudeSession.cwd`; senão deriva de `<project.path>/--<branch>` (mesmo
  cálculo F5).

## Alternativas

1. **`RunInstance.worktree_id`** (rejeitada): worktrees são ephemeras
   pós-F5 (cleanup em task terminal), FK quebraria.
2. **Run compartilhada entre tasks** (rejeitada): força named-run abstration,
   contradiz task-first. Caso de "olhar stack sem task ativa" não foi pedido.
3. **`task_id` só, sem `cwd`** (rejeitada): força re-deriving cwd a cada
   API call; duplica lógica entre core/runs.py e core/sessions.py.
4. **Run independente de Session** (mantida — ADR-0017 fala worktree, mas
   spec F6 §3 decisão #8 explicita que Run não requer Session ativa, só
   task em `in_progress`/`review`).

## Consequências

**Positivas**

- Modelo mental coerente: Task é unit-of-work; Worktree + Session + Run
  são detalhes derivados.
- Cleanup F5 reuso direto: terminal state limpa worktree E run sem código
  duplicado.
- API surface mínima: 4 endpoints (POST runs, GET run, POST stop, GET logs)
  sem precisar de "Run namespace".
- ports_json/containers_json em TEXT JSON (SQLite sem tipo nativo) — flexível
  pra cardinalidade variável de serviços do manifest.

**Negativas**

- 1 run ativa por task limita "olhar 2 versões da mesma task lado-a-lado"
  (e.g., comparar comportamento antes/depois da edição). Aceitável: clone
  da task pra ter run separada.
- `cwd` duplicado entre `ClaudeSession.cwd` e `RunInstance.cwd` — pode
  divergir se um for atualizado e o outro não. Mitigação: `derive_run_cwd`
  sempre olha worktrees primeiro; cwd na RunInstance é só snapshot.
- `containers_json` armazenado como string requer `json.loads` toda vez.
  Custo aceitável; alternativa seria tabela `run_services` mas YAGNI pra
  ≤10 serviços por run.

## Referências

- Spec F6 §3 (decisão #7), §4 (modelo de dados), §8 (state machine)
- ADR-0007 (task-first), ADR-0012 (Session.task_id NOT NULL), ADR-0017
  (Worktree detalhe da task)
- Migration `alembic/versions/0005_run_instances.py`
- `orchestrator/core/runs.py`, `orchestrator/store/models.py::RunInstance`
