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
- 1 session ativa por task (lock server-side via per-task asyncio.Lock + count check).
- Quick session preserva UX de F1 sem trair task-first.
- Migration 0003 backfill defensivo cria task implícita por session
  pré-existente.

## Referências

- ARCHITECTURE.md §1.2 (princípios), §3 (modelo de dados)
- Spec F4 §1, §3
- Migration `alembic/versions/0003_tasks_and_session_task_link.py`
