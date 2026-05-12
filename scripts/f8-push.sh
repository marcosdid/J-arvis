#!/usr/bin/env bash
# F8 — Push branch + create PR
#
# Run from repo root (or anywhere — script CDs into repo via $REPO_ROOT).
# Requires: git, gh (GitHub CLI), authenticated to marcosdid/J-arvis.
#
# Idempotent: pushing again is a no-op; gh pr create fails gracefully if PR exists.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

BRANCH="feat/f8-master-session"
BASE="main"

# Safety: confirm we're on the right branch
current_branch="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$current_branch" != "$BRANCH" ]]; then
  echo "✗ Current branch is '$current_branch', expected '$BRANCH'."
  echo "  Run: git checkout $BRANCH"
  exit 1
fi

# Safety: confirm no uncommitted changes
if ! git diff-index --quiet HEAD --; then
  echo "✗ Uncommitted changes detected. Commit or stash first."
  git status --short
  exit 1
fi

echo "→ Pushing $BRANCH to origin..."
git push -u origin "$BRANCH"

echo ""
echo "→ Creating PR ($BRANCH → $BASE)..."

# PR body via HEREDOC. Edit if you want to change before opening.
gh pr create \
  --base "$BASE" \
  --head "$BRANCH" \
  --title "feat: F8 — Sessão master Claude no sidebar web" \
  --body "$(cat <<'EOF'
## Resumo

F8 substitui o original "Planner meta-agente" (épico efêmero) por uma **sessão master Claude global, persistente, renderizada num sidebar web** (xterm.js + PTY backend) que gerencia o app inteiro via tools MCP que mexem no banco do J-arvis.

Decompor épico continua coberto — agora como uma das interações via chat (`Claude usa create_task N vezes`), não UI dedicada.

## End-to-end flow

```
Browser (React + xterm.js) ←─ WebSocket ─→ Daemon (FastAPI)
                                             │
                                             ▼
                                       PtyMultiplexer
                                             │
                                             ▼ os.openpty()
                                       PTY pair
                                             │
                                             ▼
                                       ai-jail + claude --resume <id>
                                                     --dangerously-skip-permissions
                                             │
                                             ▼ MCP tools (via settings.json)
                                       POST /api/mcp
                                       (Bearer auth + JSON-RPC 2.0)
                                             │
                                             ▼
                                       core.tasks.* / core.projects.*
                                       + WsEvent broadcast pra Kanban
```

## 11 decisões arquiteturais (ADR-0022)

1. **F8 substitui o original** (épico vira tool no chat genérico)
2. **UI: sidebar web** com xterm.js + PTY backend
3. **Tech: mesma de F1+** — ai-jail + Claude CLI em PTY pair (não terminal nativo)
4-5. **Tool surface ampla** (list/get/create/update/discard tasks + projects). Fora de scope: start_session, start_run, manage worktrees
6. **Persistência via `claude --resume <session-id>`**
7. **Uma sessão global** (não per-project, não multi-conversa)
8. **MCP via Streamable HTTP + JSON-RPC 2.0** com SDK oficial \`mcp>=1.27\`
9. **Hooks F2 NÃO participam** no master
10. **PtyMultiplexer drop slow subscriber** (queue full → unsubscribe, não mata reader)
11. **WS protocol**: 4 message types (input/output/resize/system)

## Test plan

| Camada | Tests | Status |
|---|---|---|
| Unit | 27 novos (PtyOps, runtime, writers, multiplexer, MCP dispatch, get_project) | ✅ |
| Integration | 14 novos (PTY smoke, MCP read/write, WS race, lifespan, cleanup_orphan, spawn failure) | ✅ |
| UI | 3 novos (MasterSidebar header + WS + system banner) + smoke gate | ✅ |
| E2E | 1 skeleton (host-only via Playwright) | 📋 |
| **Total backend** | **507 tests** | ✅ green |
| **Total UI** | **255 tests** | ✅ green |
| Coverage backend | 100% em F8 modules (`# pragma: no cover` em SubprocessPtyOps + watchdog re-spawn) | ✅ |
| Mypy F8 modules | 0 errors | ✅ |
| Ruff F8 files | 0 findings | ✅ |
| TypeScript | 0 errors | ✅ |

## Commits (18 total: spec + plan + 7 sub-tasks + 6 polish + closure)

| Sub-task | Commit | Entrega |
|---|---|---|
| F8.a | \`588ada0\` + \`d512503\` | MasterSession model + migration 0006 + PtyProcessOps Protocol |
| F8.b | \`16959cf\` | MasterSessionRuntime + writers + SubprocessPtyOps + PTY smoke |
| F8.c | \`d7cf95b\` + \`beacfe1\` | MCP server + read tools + ASGI mount (SDK spike adapted real API) |
| F8.d | \`0a024ef\` + \`6e7f6aa\` | 3 MCP write tools + WS broadcast |
| F8.e | \`318ee95\` + \`9221825\` | /ws/master + PtyMultiplexer + lifespan + watchdog + EOF sentinel fix |
| F8.f | \`079536e\` + \`9e62a68\` | UI MasterSidebar + xterm.js + system msg banner |
| F8.g | \`e36c5b9\` | ADR-0022 + ARCHITECTURE F8 ✅ + E2E skeleton |

## Demo manual (host)

\`\`\`bash
make up
# Abre http://localhost:8765
# 1. Sidebar à direita mostra xterm.js conectando
# 2. Claude master aparece no terminal (~2s)
# 3. Digita "cria 3 tasks no projeto X com template frontend"
# 4. Claude responde + chama create_task MCP tool 3x
# 5. Tasks aparecem no Kanban em tempo real (WS broadcast)
\`\`\`

## Notes

- **Sem migração breaking**: F0-F7 suite (456 tests) passa sem mudanças
- **Graceful degradation**: spawn failure → daemon sobe sem master; UI mostra system error + close 1011
- **Watchdog**: detecta \`claude --resume\` failure em <2s e re-spawna fresh (perde história, ganha sobrevida)
- **Bundle UI**: +602KB (xterm) — warning de tamanho, code-splitting é follow-up
- **Linux/macOS only** (\`loop.add_reader\` não funciona no Windows)

## Follow-ups (não-bloqueantes, criar issues post-merge)

Ver \`scripts/f8-followups.sh\` pra criar as 7 issues sugeridas pelo final reviewer.

🎉 **F8 fecha primeira fase pós-MVP.**
EOF
)" \
  || echo "(PR creation skipped — already exists or gh error; check 'gh pr list')"

echo ""
echo "✓ Done. View PR: gh pr view --web"
