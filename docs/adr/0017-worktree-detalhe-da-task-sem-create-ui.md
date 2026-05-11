# ADR-0017: Worktree é detalhe da task — sem UI de create/destroy avulsa

- **Status:** Accepted
- **Data:** 2026-05-11
- **Decisores:** Marcos

## Contexto

F1 expunha worktrees como entidade de primeira classe na UI: listar,
criar via formulário "Nova worktree", iniciar sessão clicando numa
worktree. F4 introduziu Task como entidade primária (ADR-0012), mas
manteve o caminho legado: `POST /api/sessions {worktree_id}` (quick
session cria task implícita).

Ao especificar F5 (mapa de worktrees), surgiu a pergunta: a UI deve
ganhar botão "+ Nova worktree" no drawer? Resposta do usuário (citação
direta): *"chat, não preciso criar worktree pelo painel, quem cria
as worktrees é o painel quando eu vou iniciar um novo desenvolvimento.
eu não preciso conseguir criar fora esse caso."*

## Decisão

**Worktree é detalhe de implementação da task.** Ciclo de vida
completamente derivado de Task:

| Evento da Task | Efeito em Worktree |
|---|---|
| `task.state` entra em `in_progress`/`review` (1ª sessão) | Daemon cria N worktrees (1 por `Repository`) |
| `task.state` → `done`/`discarded` | Daemon remove **todas** as worktrees da task + cwd dir |
| Stop session sem mudar state | Worktrees **mantidas** (re-start usa o mesmo `cwd`) |

**API:**
- ❌ `POST /api/projects/{id}/worktrees` — **removida**. Sem criação avulsa.
- ❌ `POST /api/sessions {worktree_id}` — **removida**. Sem quick session.
- ✅ `POST /api/tasks/{id}/sessions {}` — único caminho pra iniciar sessão.
  Pydantic `extra="forbid"` rejeita `worktree_id` legado com 422.
- ✅ `DELETE /api/worktrees/{id}` — **só** pra órfãs (worktrees criadas
  externamente via terminal). UI mostra botão `✕` somente em órfãs.

**UI:**
- ❌ `TaskDetailModal` — picker de worktree removido.
- ❌ Botão "+ Nova worktree" — não existe.
- ✅ `NewTaskForm.Avançado.branch` — campo opcional de **branch name**
  (não worktree). Vazio → auto-slug do título.
- ✅ Drawer "Projetos & Worktrees" é **read-only** exceto pelo `✕`
  em órfãs e `Excluir projeto`.

## Alternativas

1. **Manter `POST /api/sessions {worktree_id}` como atalho power-user**
   (rejeitada): caminho duplicado fragiliza invariants ("quem criou
   essa worktree e por quê?"). Usuário rejeitou explicitamente.
2. **Manter UI de "Nova worktree" pra exploração ad-hoc** (rejeitada):
   o caso de uso ("criar worktree pra experimentar") já é coberto
   pelo usuário criando manualmente via terminal — daemon sincroniza
   e mostra como **órfã** (spec §9.5).
3. **Cleanup só em `discarded`, manter em `done`** (rejeitada): "done"
   é estado terminal — worktree não-removida vira lixo no disco e
   confunde o mapa. Coerente com "task-first": worktree é meio, não fim.

## Consequências

**Positivas**

- Modelo mental coeso: usuário pensa em tasks; worktrees aparecem
  por consequência. Drawer é mapa, não painel de controle.
- 1 caminho de criação (`POST /api/tasks/{id}/sessions`) elimina
  estados desincronizados (task sem worktree, worktree sem task).
- Cleanup automático = zero lixo no disco em fluxo feliz. Órfãs
  ficam visíveis e removíveis com 1 clique.
- API surface menor: 1 endpoint a menos pra testar, documentar,
  versionar.

**Negativas**

- Worktree externa criada via terminal **vira órfã** — leva 1 click
  pra "adotar"? Não: F5 só permite **remover** órfã. Adotar (vincular
  manualmente a uma task) é YAGNI; reabrir se aparecer demanda.
- `task.branch` é **imutável após 1ª sessão** (spec §3 decisão #10,
  422 em `BranchImmutableAfterFirstSessionError`). Mudar branch
  exige task nova — coerente com "branch faz parte da identidade da
  worktree".
- Cleanup pode falhar parcialmente (1 dos N sub-repos dirty). Soft-fail:
  worktrees não-removidas viram órfãs (`task_id=NULL`) + toast +
  task transiciona mesmo assim. Detalhado em spec §9.4.

## Referências

- Spec F5 §3 (decisões #5, #7, #10), §6.1 (endpoints removidos),
  §6.6 (hard-break legacy), §9.4 (cleanup parcial), §9.5 (worktrees
  externas)
- ADR-0007 (task-first)
- ADR-0012 (task como entidade primária)
- ADR-0015, ADR-0016
- `api/sessions.py`, `api/worktrees.py`, `api/tasks.py`
