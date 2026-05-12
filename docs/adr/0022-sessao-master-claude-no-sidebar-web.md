# ADR-0022: Sessão master Claude no sidebar web

**Status:** Accepted — 2026-05-12
**Decisores:** marcosdid + Claude
**Contexto:** F8 (primeira fase pós-MVP)

## Contexto

ARCHITECTURE.md §11 originalmente definia F8 como "Planner meta-agente —
usuário cola épico → preview de subtasks → backlog. Sessão efêmera, tela
de preview, bulk insert."

Durante brainstorm, a feature foi reformulada pra uma ambição maior:
uma **sessão master Claude global, persistente, renderizada num sidebar
web** que gerencia o app inteiro via tools que mexem no banco do J-arvis.
O caso de uso "decompor épico em subtasks" continua coberto, mas agora
como uma das interações possíveis com o master (você pede via chat,
Claude usa o tool `create_task` N vezes), não como UI dedicada.

Decidir:
1. Se F8 substitui o original ou coexiste
2. Onde a UI vive (browser sidebar vs terminal nativo)
3. Como o daemon "fala" com Claude headless
4. Quais ações o master pode executar
5. Como persistir conversas através de restart
6. Escopo (global vs per-project)

## Decisão

- **F8 substitui o original**. Decompor épico vira tool no chat genérico.
- **UI: sidebar web no J-arvis com xterm.js + PTY backend**. Tecnologia
  igual VSCode terminals (xterm.js + os.openpty()).
- **Tech: mesma de F1+** — ai-jail + `claude --dangerously-skip-permissions`,
  porém em PTY pair (não terminal emulator nativo). Reusa toda a infra
  de F1+.
- **Tool surface ampla**: list/get/create/update/discard tasks + projetos.
  Fora de scope inicial: start_session, start_run, manage worktrees.
- **Persistência via Claude CLI `--resume <session-id>`**. Daemon grava
  `claude_session_id` no banco; restart spawna `claude --resume <id>` →
  Claude lembra naturalmente do jsonl que ele mesmo persiste.
- **Uma sessão global** (não per-project, não múltiplas conversas).
- **MCP protocol**: Streamable HTTP + JSON-RPC 2.0 via SDK oficial `mcp>=1.27`.
  Endpoint único `POST /api/mcp`. Auth via `Authorization: Bearer <token>`
  com token rotativo a cada boot.
- **Hooks F2 NÃO participam** no master: settings.json do master tem só
  `mcpServers` config + token, não hooks.

## Alternativas consideradas

- **Manter F8 original (planner épico) + adicionar master como F9**:
  rejeitado — master subsume o épico via tool.
- **Anthropic API direta**: rejeitado — diverge do padrão "tudo via Claude
  CLI" estabelecido em F1-F7.
- **REST endpoints per-tool em `/api/mcp/<tool>`**: rejeitado durante
  reviews — não é o protocolo MCP real (real é JSON-RPC).
- **Múltiplas conversas paralelas (estilo Cursor)**: rejeitado pra primeira
  iteração — YAGNI.

## Consequências

**Positivas:**
- Sem trabalho custom de persistência de conversa (Claude `--resume`).
- Reusa infra completa de F1+ (ai-jail, Claude CLI).
- Tool surface bem definida com schemas JSON validados.
- Daemon sobe mesmo se master falha (estado degradado).
- Master integra naturalmente com F7 (create_task com template via tool).
- Watchdog 2s detecta `--resume` failure (jsonl corrompido) e re-spawna
  fresh — recovery automático.

**Negativas:**
- Adiciona dep `mcp>=1.27` Python + xterm.js + addon-fit no UI.
- Múltiplas tabs compartilham mesma sessão (typo numa = todas veem). Mitigado
  por hint visível.
- Master é privilegiado (sem ai-jail isolation pra tools); risco maior se
  daemon for comprometido — token rotativo + scope reduzido (sem start_session)
  mitigam.
- `loop.add_reader` é Linux/macOS only; Windows out of scope.
- Bundle UI cresce ~602KB com xterm (warning de tamanho; code-splitting
  futuro se virar problema).

## Referências

- Spec: `docs/superpowers/specs/2026-05-11-f8-master-session-design.md`
- Plan: `docs/superpowers/plans/2026-05-11-f8-master-session.md`
- ARCHITECTURE.md §11 (roadmap), §13 (decisões)
- Código: `orchestrator/mcp/`, `orchestrator/sandbox/pty_runtime.py`,
  `orchestrator/api/master_ws.py`, `ui/src/components/MasterSidebar.tsx`
