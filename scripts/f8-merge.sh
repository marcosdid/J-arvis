#!/usr/bin/env bash
# F8 — Merge PR + tag + cleanup branch
#
# Run AFTER the PR is approved and CI is green.
# Idempotent-ish: if already merged, gh skips; if tag exists, git fails.
#
# Strategy: --merge (preserves the 18 F8 commits in main history).
# Same convention as v0.1.0-mvp (PR #1) merge.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

BRANCH="feat/f8-master-session"
BASE="main"
TAG="v0.2.0-f8"

# Find PR number for this branch
PR_NUM="$(gh pr list --head "$BRANCH" --json number --jq '.[0].number // empty')"
if [[ -z "$PR_NUM" ]]; then
  echo "✗ No open PR found for branch '$BRANCH'. Did you run scripts/f8-push.sh?"
  exit 1
fi

echo "→ Merging PR #$PR_NUM ($BRANCH → $BASE) with --merge..."
gh pr merge "$PR_NUM" --merge --delete-branch=false

echo ""
echo "→ Pulling main..."
git checkout "$BASE"
git pull origin "$BASE"

echo ""
echo "→ Tagging $TAG on merge commit..."
git tag -a "$TAG" -m "F8 — Sessão master Claude no sidebar web

Primeira fase pós-MVP. Substitui original planner épico por sessão master
persistente renderizada num sidebar web (xterm.js + PTY) com tools MCP
que manipulam o banco do J-arvis. Persistência via claude --resume.

507 backend tests + 255 UI tests. ADR-0022. 18 commits."
git push origin "$TAG"

echo ""
echo "→ Creating GitHub Release..."
gh release create "$TAG" \
  --title "v0.2.0-f8 — Sessão master Claude no sidebar web" \
  --notes "$(cat <<'EOF'
F8 fecha a primeira fase pós-MVP. Sessão master Claude global, persistente,
renderizada num sidebar web do J-arvis, com tools MCP que mexem no banco.

Ver [ADR-0022](docs/adr/0022-sessao-master-claude-no-sidebar-web.md) pra
contexto e decisões. Ver [PR #2](../../pull/2) pro changelog completo.

**Highlights:**
- xterm.js + PTY backend (estilo VSCode terminal)
- MCP Streamable HTTP + JSON-RPC 2.0 com 7 tools (read + write)
- Persistência via `claude --resume <session-id>` (zero trabalho custom)
- Daemon sobe degradado se spawn falha (UI mostra system error)
- Watchdog 2s detecta `--resume` failure e re-spawna fresh

**Stats:**
- 507 backend tests + 255 UI tests, 100% coverage F8 modules
- 18 commits (spec + plan + 7 sub-tasks + 6 polish + closure)
- Linux/macOS only (Windows out of scope)
EOF
)" \
  --latest

echo ""
echo "→ Cleanup: deletar branch local + remote..."
git branch -D "$BRANCH" 2>/dev/null || echo "  (local branch já apagada)"
git push origin --delete "$BRANCH" 2>/dev/null || echo "  (remote branch já apagada)"

echo ""
echo "✓ F8 shipped. Release: $(gh release view "$TAG" --json url --jq '.url')"
echo ""
echo "Próximo passo: rodar ./scripts/f8-followups.sh pra criar as 7 issues de follow-up."
