# scripts/

Scripts auxiliares pra release workflow do J-arvis.

## F8 (Sessão master Claude no sidebar web)

Execute na **ordem**:

### 1. `f8-push.sh` — push branch + abrir PR

```bash
./scripts/f8-push.sh
```

- Confere que você está no branch `feat/f8-master-session`
- Confere que não há mudanças não-commitadas
- `git push -u origin feat/f8-master-session`
- `gh pr create` com title + body completos (18 commits documentados)

**Pré-requisitos:** `git`, `gh` (GitHub CLI) autenticado, branch `main` existe no remote.

### 2. (Revisar PR no GitHub, esperar CI)

A esta altura, abra o PR no browser (`gh pr view --web`) e revise/aprove.

### 3. `f8-merge.sh` — merge + tag + release

```bash
./scripts/f8-merge.sh
```

- `gh pr merge --merge` (preserva os 18 commits no histórico)
- `git pull main` pós-merge
- Cria tag `v0.2.0-f8` no merge commit + push
- `gh release create --latest` com release notes
- Deleta branch local + remote

### 4. `f8-followups.sh` — criar 7 issues de follow-up

```bash
./scripts/f8-followups.sh
```

Cria as 7 issues identificadas pelo final code reviewer:
- PID-reuse race em `cleanup_orphan_master`
- Watchdog re-spawn ordering window
- `term.write` coverage gap (UI test)
- Window resize não propaga pra `xterm.fit()`
- Bundle splitting (xterm vendor chunk)
- `_MASTER_PORT` hardcoded → sourcing de Settings
- Janitorial: limpar 41 ruff baseline errors

Labels: `F8-followup` + (`bug`/`tests`/`enhancement`/`performance`/`chore` conforme tipo).

## Estratégia de merge

**`--merge`** (default) preserva os 18 commits granulares de F8 no histórico de `main` (igual fizemos com v0.1.0-mvp via PR #1).

Pra mudar pra `--squash`: edite `scripts/f8-merge.sh` linha do `gh pr merge`.

## Convenções

- Scripts em bash com `set -euo pipefail`
- CD pro repo root via `$REPO_ROOT` (chama-se de qualquer dir)
- Idempotentes onde possível (push novamente é no-op; tag duplicada falha graciosamente)
- Sem dependências além de `git` + `gh` (já requeridos pelo workflow)
