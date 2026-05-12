#!/usr/bin/env bash
# F8 — Create follow-up GitHub issues
#
# Creates 7 follow-up issues identified by F8 final reviewer.
# Non-blocking — F8 already merged when these are created.
#
# Run after the PR is merged (so issues link to merged work).
# Requires: gh (GitHub CLI), authenticated.
#
# Idempotent-ish: gh will let you create duplicates if you run twice.
# Skip lines you don't want via comment-out before running.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

LABEL="F8-followup"

# Ensure label exists (idempotent — gh ignores if already there)
gh label create "$LABEL" --description "F8 master session follow-up items" --color "F9D71C" 2>/dev/null || true

echo "→ Creating 7 F8 follow-up issues..."

gh issue create \
  --title "F8: PID-reuse race em cleanup_orphan_master_at_startup" \
  --label "$LABEL,bug" \
  --body "$(cat <<'EOF'
**Origem:** F8.e code review

**Problema:** \`orchestrator/core/master_session.py:14-17\` faz \`os.killpg(os.getpgid(pid), SIGKILL)\` direto. Se o PID do daemon antigo foi reciclado entre crash e restart, mata-mos um process group não-relacionado.

**Probabilidade:** baixa (PID reuse em janela curta de boot)
**Severidade:** alta se ocorrer (kill em processo de outro usuário)

**Mitigação proposta:**

1. Persistir \`pgid\` + \`started_at\` em \`MasterSession\` row no spawn
2. No cleanup, ler \`/proc/{pid}/cmdline\` ou similar pra confirmar que ainda é \`ai-jail\` antes de matar
3. OU usar \`process_start_time\` cross-check via \`/proc/{pid}/stat\`

Tracking issue criada após F8 merge.
EOF
)"

gh issue create \
  --title "F8: Watchdog re-spawn ordering window (handle swap antes de mux.shutdown)" \
  --label "$LABEL,bug" \
  --body "$(cat <<'EOF'
**Origem:** F8 final review

**Problema:** Em \`orchestrator/main.py:_resume_watchdog\` o \`app.state.master_handle\` é setado para o novo handle ANTES de \`master_multiplexer.shutdown()\` ser awaited. Janela: WS connect entre esses dois steps captura o NOVO handle mas subscribe no VELHO multiplexer.

**Sintoma:** primeiro frame da nova WS sumiria (EOF sentinel arriva e fecha) — usuário vê "disconnect", reconecta, OK.

**Fix:** atomic swap — shutdown old mux + clear handle + spawn new + set new handle + new mux, idealmente sob um lock. Ou: shutdown old PRIMEIRO, depois atomic swap.

\`# pragma: no cover\` na branch — host-only behavior. Adicionar integration test com mock pra cobrir essa ordering.
EOF
)"

gh issue create \
  --title "F8: term.write coverage gap em MasterSidebar.test.tsx" \
  --label "$LABEL,tests" \
  --body "$(cat <<'EOF'
**Origem:** F8.f code review

**Problema:** \`ui/src/components/MasterSidebar.test.tsx\` tem 3 tests (header render + WS connect + system banner). Falta assertion no path \`{type:"output", data:"..."}\` → \`term.write(data)\`.

**Fix proposto** (~5 linhas):

\`\`\`typescript
it('writes output data to terminal', async () => {
  render(<MasterSidebar />);
  await new Promise((r) => setTimeout(r, 10));
  wsInstance!.onmessage?.(new MessageEvent('message', {
    data: JSON.stringify({ type: 'output', data: 'hello' }),
  }));
  // Mock xterm Terminal has vi.fn() on .write — assert chamado com 'hello'
  expect(mockTerminalInstance.write).toHaveBeenCalledWith('hello');
});
\`\`\`

Pega regression se output handler quebrar.
EOF
)"

gh issue create \
  --title "F8: Window resize não propaga pra xterm.fit()" \
  --label "$LABEL,enhancement" \
  --body "$(cat <<'EOF'
**Origem:** F8.f code review

**Problema:** \`MasterSidebar.tsx\` chama \`fit.fit()\` uma vez no mount. Resize do browser deixa o xterm em geometria stale (linhas cortadas, scroll quebrado).

**Fix proposto:** \`ResizeObserver\` em \`containerRef.current\`:

\`\`\`typescript
const observer = new ResizeObserver(() => {
  fit.fit();
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'resize', rows: term.rows, cols: term.cols }));
  }
});
observer.observe(containerRef.current!);
// cleanup: observer.disconnect()
\`\`\`

UX gap previsível — usuário vai redimensionar antes de F9.
EOF
)"

gh issue create \
  --title "F8: Bundle splitting — xterm em vendor chunk separado" \
  --label "$LABEL,performance" \
  --body "$(cat <<'EOF'
**Origem:** F8.f code review

**Problema:** \`pnpm build\` warn que JS chunk passou de 602KB (gzip ~170KB). xterm + addon-fit dominam.

**Fix proposto** (Vite config):

\`\`\`ts
// vite.config.ts
build: {
  rollupOptions: {
    output: {
      manualChunks: {
        xterm: ['@xterm/xterm', '@xterm/addon-fit'],
      },
    },
  },
},
\`\`\`

OU \`React.lazy(() => import('./MasterSidebar'))\` + Suspense fallback (defer carregamento até primeira render).

Não-urgente. Revisitar se TTFB virar problema.
EOF
)"

gh issue create \
  --title "F8: _MASTER_PORT hardcoded — sourcing de Settings" \
  --label "$LABEL,enhancement" \
  --body "$(cat <<'EOF'
**Origem:** F8.e code review

**Problema:** \`orchestrator/main.py:59\` tem \`_MASTER_PORT = 8765\` com self-TODO. Deploy atrás de reverse proxy com porta diferente quebra o \`mcp_url\` que master usa.

**Fix proposto:** ler de \`Settings.port\` (já existe em \`orchestrator/config/__init__.py\`). Build URL via:

\`\`\`python
mcp_url = f"http://localhost:{settings.port}/api/mcp"
\`\`\`

Easy follow-up. Remove o TODO comment.
EOF
)"

gh issue create \
  --title "F8: Janitorial — limpar 41 ruff baseline errors no repo" \
  --label "$LABEL,chore" \
  --body "$(cat <<'EOF'
**Origem:** F8 final review

**Problema:** \`uv run ruff check orchestrator tests\` reporta 41 findings — todos pre-existentes (não introduzidos por F8). Ruído acumulado durante MVP F0-F7.

**Fix proposto:**
1. \`uv run ruff check --fix orchestrator tests\` pega auto-fixes
2. Manual review dos restantes — PLC0415 em \`core/tasks.py:195\` é intencional (circular import avoidance), comment ele com \`# noqa: PLC0415\`
3. Outros findings: priorizar por severidade
4. Commit separado: \`chore: clear ruff baseline\`

Não-urgente mas higiênico. F9 vai ficar mais limpo com baseline zero.
EOF
)"

echo ""
echo "✓ Done. View issues: gh issue list --label $LABEL"
