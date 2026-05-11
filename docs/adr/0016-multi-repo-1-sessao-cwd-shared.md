# ADR-0016: Multi-repo — 1 sessão Claude com `cwd` compartilhado

- **Status:** Accepted
- **Data:** 2026-05-11
- **Decisores:** Marcos

## Contexto

ADR-0015 introduz N `Repository` por `Project`. Quando uma task em
projeto multi-repo (`gcb-hub`: backend + frontend) entra em
`in_progress`, o daemon precisa criar **uma worktree por sub-repo**
(N worktrees pra 1 task), e iniciar sessão Claude com acesso a
**todas**. Pergunta arquitetural: 1 sessão vê os 2 sub-worktrees,
ou 2 sessões paralelas (uma por sub-repo)?

ADR-0012 estabelece "1 session ativa por task". ADR-0008 spawna
sessão num terminal nativo com `cwd` fixo. Multiplicar sessões
fragmenta o contexto que o Claude tem da feature.

## Decisão

**Uma sessão por task, sempre.** Pra multi-repo:

1. Daemon cria `cwd = <dirname(project.path)>/<basename(project.path)>--<branch_slug>`
   (ex: `~/work/gcb-hub--add-oauth/`).
2. Cria 1 worktree por sub-repo dentro de `cwd`:
   - `cwd/backend/` ← `git worktree add` em `<project.path>/backend`
   - `cwd/frontend/` ← `git worktree add` em `<project.path>/frontend`
3. `ai-jail run` monta `cwd` como root da jaula.
4. Claude opera com `cd backend` / `cd ../frontend` — ambos visíveis
   no mesmo ambiente.

`ClaudeSession.cwd` substitui `ClaudeSession.worktree_id` da F1/F4
(migration 0004 dropa a FK). Cwd derivada **funcionalmente** das
worktrees vinculadas à task (não precisa coluna extra). Para monorepo:
a única worktree **é** o cwd.

## Alternativas

1. **N sessões paralelas (1 por sub-repo)** (rejeitada): Claude perde
   contexto cross-repo ("API endpoint X precisa de SPA hook Y").
   Quebra "1 session ativa por task". Multiplica processos.
2. **1 sessão com worktree.path como cwd** (rejeitada pré-F5): só
   funciona em monorepo; quebra em multi-repo (qual worktree é "o"
   cwd?).
3. **Symlinks sub-repo → diretório compartilhado** (rejeitada):
   `git worktree` não lida bem com symlinks; auditoria fica torta.
4. **Container Docker com bind mounts dos N sub-repos** (rejeitada):
   over-engineering. ai-jail + dir-pai resolve.

## Consequências

**Positivas**

- ADR-0012 ("1 session por task") sobrevive intacto — multi-repo
  não introduz novo conceito de sessão.
- Claude vê o produto inteiro (`backend/` + `frontend/`) — refactors
  cross-repo ficam triviais.
- `ai-jail` continua sendo o boundary natural — não muda nada no
  contrato de sandbox.
- Cleanup é simétrico: `task → done/discarded` remove **todas** as
  worktrees + cwd dir (se vazio); 1 chamada `cleanup_task_worktrees`.

**Negativas**

- `cwd` é diretório-pai **fora** de qualquer repo git — `git status`
  no root não funciona, só dentro dos sub-dirs. Aceitável: Claude
  sabe `cd <repo>` antes.
- Rollback atômico em 3 camadas (FS + DB + WS) ficou mais complexo:
  se `git worktree add frontend/` falha após `backend/` ter passado,
  precisa reverter `backend/` antes de raise. Detalhado em
  spec §6.3 (steps 4d/4e_rollback) e implementado em
  `core/sessions.py::_create_worktrees_atomic`.
- Branch slug é **único globalmente entre sub-repos** — se `add-oauth`
  existe em backend mas não em frontend, 422 preemptivo (spec §9.3).
  Trade-off aceito: namespace único = conceito único.

## Referências

- Spec F5 §3 (decisão #1), §6.3 (fluxo de session create), §6.4
  (cleanup), §9.3 (assimetrias multi-repo)
- ADR-0008 (sessão em terminal nativo)
- ADR-0012 (task como entidade primária)
- ADR-0015 (multi-repo com auto-detect)
- `core/sessions.py::start_session`, `_create_worktrees_atomic`
