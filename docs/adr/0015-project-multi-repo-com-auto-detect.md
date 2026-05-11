# ADR-0015: Project multi-repo com auto-detect de sub-repos

- **Status:** Accepted
- **Data:** 2026-05-11
- **Decisores:** Marcos

## Contexto

Até F4 o modelo era 1-projeto = 1-repo: `Project(path)` era assumido
como um único working tree git, e cada `Worktree` apontava direto pra
`project_id`. Casos reais quebram essa hipótese — `gcb-hub` tem
`backend/` (API) e `frontend/` (SPA) lado-a-lado, cada um com seu
`.git`, mas conceitualmente é **um produto**. Forçar o usuário a
cadastrar dois projetos quebra o agrupamento natural ("Add OAuth" é
1 task que toca os dois).

## Decisão

Introduzir entidade intermediária **`Repository`** entre `Project` e
`Worktree`. `Project.path` aponta pra base; `Project` tem **N
repositories** descobertos automaticamente em `POST /api/projects`:

1. Se `<base_path>/.git/` é diretório → monorepo: 1 `Repository` com
   `sub_path="."`, `name=basename(base_path)`.
2. Senão, scan filhos imediatos: pra cada `child/` onde `child/.git/`
   é dir → `Repository(name=child.name, sub_path=child.name)`.
3. Se nada detectado → 422 `NoGitReposError` (recusa add-project).

Implementado em `core/repositories.py::detect_repos` (pure function).
`Worktree.repository_id` (não `project_id`) — JOIN dá o projeto.

## Alternativas

1. **Continuar 1-projeto = 1-repo** (rejeitada): força usuário a
   cadastrar `gcb-hub-backend` + `gcb-hub-frontend` separados; tasks
   cross-repo precisam ser duplicadas; perde agrupamento UX.
2. **Sub-repo declarado manualmente no add-project** (rejeitada):
   friction. Layout do disco já é a fonte da verdade — `.git` dir
   é sinal honesto.
3. **Auto-detect recursivo (depth ≥ 2)** (rejeitada): `services/api/.git`
   complica heurística sem caso real ainda. Suporte se aparecer demanda.
4. **`Worktree.project_id` denormalizado** (rejeitada): risco de
   divergir de `worktree.repository.project_id`. SQLite single-user
   local — JOIN é sub-ms; consistência > micro-otimização.

## Consequências

**Positivas**

- Modelo natural pra mono **e** multi-repo (gcb-financeiro monorepo
  + gcb-hub multi-repo coexistem sem caso especial na UI).
- Auto-detect é zero-friction: usuário só dá o path.
- Branch namespace **único por projeto** — `add-oauth` em backend e
  frontend é o **mesmo conceito**, refletido no slug compartilhado.
- UI suprime `Repository.name` quando task tem 1 worktree (monorepo
  ou multi-repo com cleanup parcial); mostra `<repo>/<branch>` quando
  >1. Schema não muda; só rendering.

**Negativas**

- Sub-módulos (`.git` é arquivo) e bare repos (sem `.git/`) ficam
  fora. Aceitável: ambos são edge no MVP.
- Sub-repo adicionado **depois** do add-project não auto-aparece —
  usuário precisa remover + re-adicionar. Documentado em §9.3 do spec.
- Migration 0004 backfill assume cenário F4 (monorepo) — cria
  `Repository(sub_path=".")` com `LIMIT 1` na worktree existente.
  Downgrade é lossy.

## Referências

- Spec F5 §3 (decisão #2), §5.3 (`detect_repos`), §5.4 (normalização),
  §5.5 (`Repository.name` em monorepo)
- ADR-0007 (task-first)
- Migration `alembic/versions/0004_repositories_and_cwd.py`
