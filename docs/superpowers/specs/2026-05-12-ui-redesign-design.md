# UI Redesign — identidade CIPHER (operator cyberpunk autêntico) (design)

**Status:** spec em revisão, plan pending
**Data:** 2026-05-12
**Phase:** F9 (pós-MVP, paralelo ao bug F8.master)

## 1. Contexto

Após F8 fechar a estrutura funcional (kanban + sessão master + MCP + run + catalog), uma auditoria visual identificou que a UI está em estado de **protótipo funcional**: `ui/src/index.css` tem 136 linhas de CSS vanilla, sem design system, sem tokens, sem framework de UI. Badges são `.profile-yellow`/`.profile-gray` hardcoded; layout é `grid-template-columns: 1fr 400px` cru; tipografia é `system-ui` default. Os 456+251 testes passam e o produto funciona — mas o usuário descreveu como "horrível", citando 3 dores específicas (ver §3).

Esta spec define o redesign completo da UI **sem mexer em backend, banco ou contratos de API**. O escopo é puramente visual + estrutural-de-frontend.

## 2. Decisões arquiteturais

| # | Decisão | Motivação |
|---|---|---|
| 1 | **Tailwind v4 + shadcn/ui** substituem o CSS vanilla atual. CSS variables pra tokens. Radix UI por baixo (via shadcn) garante a11y. | Stack padrão pra ferramentas Linear/Vercel/Cursor-style. Custo de migração (15+ deps, configurar postcss) compensa: a11y de graça, primitivas (Dialog, Tabs, Sheet, Tooltip, Command) prontas, dark mode trivial via CSS vars. |
| 2 | **Layout 2-pane:** kanban principal + master sidebar 400px à direita (estrutura atual mantida). Header global no topo, status bar tmux-style no rodapé. | Usuário rejeitou variações (3-pane Linear, master no rodapé). Layout atual é familiar e cabe o caso de uso. |
| 3 | **Kanban clássico:** 5 colunas verticais (Ideas / Ready / In Progress / Review / Done) lado-a-lado, cards empilham verticalmente dentro de cada coluna, drag-and-drop via `@dnd-kit` (já existente). | Padrão universal de kanban, mantém affordance que o usuário espera. Reusa dnd-kit sem regressão. |
| 4 | **Drill-down via Sheet da direita** (shadcn `Sheet`, side=right). Sheet substitui a master enquanto aberto. Click no card abre Sheet; ESC ou X fecha. | Linear-style. Mantém kanban visível enquanto inspeciona uma task. Trade-off aceito: master fica escondida durante drill-down (pode reabrir fechando o Sheet). |
| 5 | **Tema dark-only.** Nenhum toggle. Sem `prefers-color-scheme` auto. | YAGNI no MVP — simplifica tokens e testes visuais. Linear/Cursor nasceram dark, dev senior persona vive em dark. Light mode pode entrar em F9+1 se houver demanda. |
| 6 | **Identidade CIPHER v2** (operator cyberpunk autêntico): JetBrains Mono dominante + Space Grotesk em labels HUD; paleta verde/preto com magenta hot pra atenção crítica; corner brackets ASCII nos cards; HUD top bar com métricas vivas; status bar tmux-style no rodapé. | Usuário escolheu CIPHER entre 3 direções (OPERATOR / SYNTHWAVE / CIPHER), pediu reforço cyberpunk. Identidade diferencia o J-arvis de ferramentas genéricas SaaS. |
| 7 | **Paleta lock-direction, tons refinar na impl.** Usuário aprovou a direção CIPHER v2 mas notou "tudo muito verde". Decisão: implementar em fases — primeiro estrutura com tons-base, depois refinar a paleta com swatches calibradas (incluir cinzas-quentes, mais variação tonal no verde, magenta como spot color disciplinado). | Bloqueia inflar o tempo de brainstorm em micro-decisão de cor que se resolve melhor in-context (com a UI rodando, dá pra ajustar com `var(--*)` rápido). |
| 8 | **Tipografia:** `JetBrains Mono` (400/500/600/700/800) como fonte default do app; `Space Grotesk` (600/700) só em labels do HUD top bar (`OPER`, `J-ARVIS // OP_CTRL`). | Mono em tudo cria a identidade "operator". Sans em labels HUD evita parecer "terminal puro" e dá ritmo tipográfico. |
| 9 | **NewTaskForm em duas modalidades:** "+ Add task" inline no rodapé da coluna (quick: só título, herda template default da coluna); "+ New task" no header abre Sheet completa com template/perfil/branch override. | Reduz fricção pra criar idea rapidamente; preserva form rico pra quando importa. |
| 10 | **Migração não quebra testes existentes.** Componentes mantêm props e behavior; só mudam estilos. Testes Vitest em `ui/src/**/*.test.tsx` continuam verdes sem mudança. Falhas que surgirem são tratadas como bug, não esperadas. | Coverage 100% UI é o gate; redesign não pode regridir testes. |
| 11 | **Status bar inferior é nova,** ocupando ~28px no rodapé. Contém: WS state, MCP endpoint, mode, profile ativo, git branch, version. | Resolve dor "falta de feedback de estado" pra info de contexto que hoje exige abrir menu/console. Inspiração tmux/vim status line. |
| 12 | **HUD top bar é nova,** ocupando ~28px no topo (acima do header). Contém: badge `OPER` piscante, label `J-ARVIS // OP_CTRL`, métricas vivas (CPU/MEM/RTT/uptime/alerts). | Identidade. Métricas de sistema são lidas via `/api/health` (a criar — endpoint stub aceitável; preencher com valores reais é follow-up). |
| 13 | **Master Session redesign mantém comportamento:** xterm.js + WebSocket /ws/master + PtyMultiplexer + claude --resume (tudo F8 atual). Só muda visual (corner brackets verdes, accent magenta no cursor, footer com RTT) e adiciona quick commands strip + 4 botões no header. | Bug F8.master fica fora desta spec (§11). Visual e comportamento são separáveis. |
| 14 | **Bug F8 master "não funcionou"** é tratado em spec separada (`2026-05-12-f8-master-bugfix-design.md` — pending). Esta spec assume que o componente Master Session é redesenhado **assumindo F8 funcional**. | Separação de concerns: redesign é estético+estrutural; bug é comportamental. Misturar bloqueia ambos. |

## 3. Pain points endereçados

Usuário marcou 3 dores na auditoria visual:

1. **Visual cru / sem identidade** → resolvido por: paleta dark Linear-tier + identidade CIPHER (mono + verde/magenta + corner brackets + HUD), tipografia JetBrains Mono + Space Grotesk, decorações ASCII deliberadas.
2. **Hierarquia confusa** → resolvido por: 4 níveis de atenção visual (atenção crítica `awaiting` com glow magenta > erro com borda vermelha > running com live-dot verde > idle/done sóbrios), header global concentrando ações primárias, status bar concentrando info de contexto.
3. **Falta de feedback de estado** → resolvido por: HUD top bar com métricas vivas + status bar tmux-style + live-dots pulsantes nos cards + glow magenta envelopante em estados de atenção + RTT visível na master session.

## 4. Visual identity (CIPHER v2)

### 4.1. Princípios

- **Operator, não dashboard.** A UI parece uma estação de operação (Bloomberg/Hak5/security ops), não SaaS genérico.
- **Mono dominante.** JetBrains Mono carrega 95% do texto. Espaços tabulares pra números. Variação de peso (400/500/600/700/800) faz a hierarquia.
- **Densidade alta com ritmo.** Info-rica como Linear/Bloomberg, mas com separadores claros (1px borders, scanlines sutis).
- **Decorações com propósito.** Cada elemento ASCII/glyph tem função (corner brackets nos cards = "objeto do sistema", `::` em col-head = "label técnico", `>` em prompt = "input ativo").
- **Atenção magenta.** Único uso de `#ff10f0` é estado `awaiting_response`. Tóxico, impossível ignorar. Não pra decoração.

### 4.2. Design tokens (direção; refinar tons na impl)

**Background scale (dark):**

```
--bg-void      : #030503   /* fundo absoluto, statusbar/scanlines */
--bg-deep      : #060906   /* pane backgrounds */
--bg-surface   : #080c08   /* cards, master pane */
--bg-elevated  : #0c100c   /* hover state */
--bg-muted     : #0a0d0a   /* col body */
```

**Border scale:**

```
--border-subtle : #1a2a1a  /* default 1px */
--border-mid    : #2a3a2a  /* hover / column dividers */
--border-strong : #4ade80  /* active focus, attn cards */
```

**Text scale:**

```
--text-faint    : #3a4a3a  /* metadata, timestamps */
--text-subtle   : #5a6a5a  /* labels, secondary */
--text-body     : #6a7a6a  /* default text */
--text-emphasis : #b8c4b3  /* body in cards */
--text-title    : #d4e4d0  /* card titles, terminal output */
```

**Accent + semantic:**

```
--accent-primary  : #4ade80   /* matrix green; brand, count, ok */
--accent-attn     : #ff10f0   /* magenta hot; awaiting_response */
--accent-info     : #00d4ff   /* cyan; hex IDs, info */
--semantic-error  : #f87171   /* red; exit code != 0 */
--semantic-warn   : #fbbf24   /* amber; idle, secondary warning */
--semantic-frontend : #00d4ff
--semantic-backend  : #4ade80
--semantic-bugfix   : #f87171
--semantic-refactor : #c084fc
--semantic-review   : #a855f7
```

**Open during impl:** usuário pediu "less green-dominance" — refinar adicionando 1-2 cinzas-quentes neutros pra texto não-emphasizado, suavizar saturação do verde em backgrounds, considerar `bg-surface` menos verde-dominante (mais neutro).

### 4.3. Tipografia

| Uso | Fonte | Pesos | Notas |
|---|---|---|---|
| Default app | JetBrains Mono | 400/500/600/700 | Variant: `tabular-nums` em métricas |
| Brand mark `> j-arvis_` | JetBrains Mono | 800 | Cursor magenta piscante anexado |
| Card titles | JetBrains Mono | 500 | Tracking -0.005em |
| HUD labels (`OPER`, `J-ARVIS // OP_CTRL`) | Space Grotesk | 700 | Tracking 0.16em uppercase |
| Terminal body | JetBrains Mono | 400 | Line-height 1.7 |
| Hex IDs, números | JetBrains Mono | 600 | `tabular-nums`, `letter-spacing: 0.06em` |

### 4.4. Iconografia & decorações

- **Corner brackets nos cards:** pseudo-elements `::before` / `::after` formam `┏━┓` superior-esquerdo e `┗━┛` inferior-direito. Cor segue estado (subtle / accent / attn).
- **Col header marker:** prefixo `::` antes do nome da coluna.
- **Prompt marker:** `>` em brand, `❯` em terminal.
- **Cursor:** bloco magenta sólido, piscando 0.8s steps(1).
- **Scanlines:** repeating-linear-gradient 2px transparent + 1px `rgba(74,222,128,0.04)` em overlay sobre toda a app. Não-interativo (`pointer-events:none`).
- **Vinheta superior direita:** radial-gradient verde sutil pra dar profundidade ao HUD.

## 5. Layout system

```
┌────────────────────────────────────────────────────────────────────┐
│  HUD top bar (28px)                                                │
│  ▌OPER  J-ARVIS // OP_CTRL    cpu 12% │ mem 2.1G │ rtt 49ms │ ...  │
├────────────────────────────────────────────────────────────────────┤
│  App header (52px)                                                 │
│  > j-arvis_  3 proj · 14 tsk · 2 active    [/] [P] [R] [+N]        │
├──────────────────────────────────────────────────┬─────────────────┤
│  Kanban board (flex 1)                           │  Master Session │
│                                                  │  (400px fixed)  │
│  ┃ ideas    ┃ ready    ┃ doing*    ┃ review     │                 │
│  ┏━━━━━━━━┓ ┏━━━━━━━━┓ ┏━━━━━━━━┓ ┏━━━━━━━━┓    │  [head]         │
│  ┃ card   ┃ ┃ card   ┃ ┃ card!  ┃ ┃ card   ┃    │  [quick cmds]   │
│  ┗━━━━━━━━┛ ┗━━━━━━━━┛ ┗━━━━━━━━┛ ┗━━━━━━━━┛    │  [xterm.js]     │
│                                                  │  [foot RTT]     │
├──────────────────────────────────────────────────┴─────────────────┤
│  Status bar (28px)                                                 │
│  state: connected │ ws ✓ │ mcp ✓ │ alerts 1 │ mode ops │ ...       │
└────────────────────────────────────────────────────────────────────┘
```

**Drill-down state** (Sheet open):

```
┌────────────────────────────────────────────────────────────────────┐
│  HUD top bar                                                       │
├────────────────────────────────────────────────────────────────────┤
│  App header                                                        │
├────────────────────────────────────────────┬───────────────────────┤
│  Kanban (continua visível, master oculta)  │  Sheet (380px-420px)  │
│                                            │   [task title]        │
│  ┃ ... ┃ ... ┃ ...                         │   [chips]             │
│                                            │   [tabs: Overview /   │
│                                            │    Sessions / Run /   │
│                                            │    Logs]              │
│                                            │   [scrollable body]   │
├────────────────────────────────────────────┴───────────────────────┤
│  Status bar                                                        │
└────────────────────────────────────────────────────────────────────┘
```

ESC fecha o Sheet, restaurando master.

## 6. Componentes — specs detalhadas

### 6.1. `<HudTopBar />` — NOVA

**Props:** none (lê de hooks).

**Hooks:**
- `useSystemHealth()` — polling `/api/health` 5s. Retorna `{ cpu_pct, mem_used_gb, mem_total_gb, ws_rtt_ms, uptime_seconds, active_alerts_count }`.
- Endpoint `/api/health` é **novo** (criar stub que retorna campos calculados ou hardcoded onde necessário; preencher real é follow-up).

**Layout:** flex row, padding 6px 14px, height 28px. Border-bottom 1px subtle.

**Left:** `<Badge variant="oper-live">OPER</Badge>` (verde piscante) + label Space Grotesk `J-ARVIS // OP_CTRL` + separator + métrica `env`.

**Right:** métricas (cpu / mem / rtt / uptime / alerts) separadas por `│`. Cada métrica é `<HudMetric label={...} value={...} kind={...} />`. Kind `hot` aplica magenta + text-shadow.

**Accessibility:** `role="status"`, `aria-live="polite"` em métricas dinâmicas.

### 6.2. `<AppHeader />` — REFACTOR

**Props:** lê de stores existentes (`projects`, `tasks`).

**Layout:** flex row, padding 12px 18px, height 52px.

**Left:** brand mark `> j-arvis_` (JetBrains Mono 800, cursor magenta piscante via `::after`) + brand meta `3 proj · 14 tsk · 2 active`. Counts vêm de queries existentes (`useTasks`, `useProjects`).

**Right:** ações em ordem visual: `[/] Filter`, `[P] Projects`, `[R] Run` (novo, abre RunPanel — TBD), `[N] + New task` (primary).

**Keyboard shortcuts** (registrados via `useKeyboardShortcut` custom hook):
- `/` → focar Filter input
- `P` → toggle ProjectsDrawer
- `R` → toggle RunPanel — **registered no-op no MVP redesign** (atalho catalogado pra forward-compat; handler retorna sem ação). RunPanel real é F9+1.
- `N` → abrir Sheet "New task"

### 6.3. `<Kanban />` + `<KanbanColumn />` — REFACTOR

Estrutura DOM e props inalteradas (testes preservados). Mudam estilos + adicionam decorações.

**`<KanbanColumn />` mudanças:**
- Background `--bg-surface`, border `--border-subtle`.
- Corner brackets ASCII via pseudo-elements no canto superior (verdes).
- Header: prefixo `::` + name lowercase + count em pill outline.
- Body: padding 7px, gap 7px.
- Footer "+ Add task" border-top dashed `--border-subtle`, hover acende verde.

### 6.4. `<TaskCard />` — REFACTOR (anatomia + estados)

**Estados visuais** (mutuamente exclusivos exceto hover):

| State | Trigger (existente) | Visual |
|---|---|---|
| `idle` | nenhuma sessão ativa | Background `--bg-surface`, border subtle, brackets cinza |
| `hover` | mouse over | Background `--bg-elevated`, brackets verde |
| `running` | session status = `executing` | Border verde, bracket verde, footer `running Nm` com live-dot verde pulsante |
| `awaiting` | session status = `awaiting_response` | Border magenta `#ff10f0`, box-shadow magenta glow, brackets magenta, footer `awaiting Nmss` com live-dot magenta pulsante. **Sobrescreve running** quando ambos. |
| `error` | session status = `error` | Border vermelha, box-shadow vermelho sutil, footer `exit N` sem animação |
| `done` | task state = `done` | Opacity 0.4, brackets cinza |
| `dragging` | dnd-kit drag | Rotate 2deg, scale 1.03, box-shadow lift, brackets verde |

**ID hex prefix** (novo elemento):
- Primeira linha do card: `id::{hex4} · {ago|live-meta}`. Hex = primeiros 4 chars do `task.id` (uuid). Live-meta substitui `ago` quando estado é live (`awaiting 04m12s`, `pid 39102`, `running 12m`).
- Calcular hex sem mudar `task.id`: `task.id.replace(/-/g, '').slice(0, 4)`.
- **Display-only**, não é identificador único (espaço ~65k chars; colisão esperada com hundreds of tasks). Operações continuam usando `task.id` completo. Hex é puramente visual/identitário.

**Chips** (templates + permission profile):
- Mantém mapping existente (frontend/backend/bugfix/refactor + permission profile).
- Visual: outline 1px (não filled), background com 5% alpha. Cor segue `--semantic-{template}`.

**Click:** abre `<TaskDetailSheet />` (substitui `<TaskDetailModal />`).

### 6.5. `<TaskDetailSheet />` — NOVO (substitui `<TaskDetailModal />`)

Implementado sobre shadcn `<Sheet side="right" />`. Width: 380-420px responsivo.

**Estrutura:**
- Header: title + close (×). Chips abaixo do título.
- Tabs (shadcn `<Tabs />`): Overview / Sessions / Run / Logs.
- **Overview tab:** status atual + ago + branch + permission_profile + template + cwd + última atividade.
- **Sessions tab:** lista de sessions (existente em F1+); cada item com pid + status + started_at + transcript link.
- **Run tab:** RunInstance status (F6) — services com chips de URL/port + logs SSE inline.
- **Logs tab:** stream consolidado.

**Comportamento:** Sheet aberto **substitui** master pane visualmente (ambos ocupam right ~400px; master é unmount enquanto Sheet open pra economizar PTY traffic? Ou só visually hidden? Decisão: **CSS hidden, mantém WS conectado**. Custo: nenhum, master continua recebendo updates. Benefit: reabre sem reconnect).

**ESC closes** + click on backdrop closes.

### 6.6. `<MasterSidebar />` — REFACTOR (preserva behavior, redesigna visual)

Componente F8 existente. Funcional inalterado (xterm.js + WS /ws/master + PtyMultiplexer + claude --resume).

**Mudanças visuais:**
- Header: title `master_001` em verde 600, live indicator (`● live` verde piscante), 4 action buttons (clear/copy id/restart/min).
- Meta line abaixo: `claude --resume master_001 · 80x24 · pid {n}`.
- Quick commands strip (NOVO): chips abaixo do header com 4-5 comandos MCP comuns (`list tasks`, `create task`, `update state`, `discard`). Click injeta o comando no PTY como input.
- Terminal body: xterm.js inalterado, mas com theme custom (verde matrix + cursor magenta).
- Footer: `pty 80x24 · pid 41203 · live · 49ms`. RTT vem do hook `useWebSocketRTT()` (novo).

**Estados auxiliares:**
- `disconnected`: empty state "WebSocket caiu — reconectando" + retry button.
- `cold start` (sem MasterSession no banco): empty state "Master não iniciada" + "Iniciar master" button → POST `/api/master/start`.
- `fatal error`: empty state com mensagem específica (exit code + razão) + "Ver logs" button.

### 6.7. `<StatusBar />` — NOVA

Layout: flex row, padding 5px 14px, height 28px. Border-top 1px subtle.

**Left segments** (cada `<StatusSeg label value>`):
- `state` → `connected` / `reconnecting` / `offline`
- `ws` → `/ws ✓` ou `✗`
- `mcp` → `/api/mcp ✓` ou `✗`
- `alerts` → contagem de tasks em `awaiting` (magenta se > 0)

**Right segments:**
- `mode` → `ops` (placeholder; pode virar `read-only` se futuro modo de auditoria)
- `profile` → permission profile ativo da sessão master ou da última task focada
- `git` → branch da worktree primária (lê do `/api/projects`)
- `v` → version do app (lê de `package.json` via build-time const)

**Reusable:** `<StatusSeg label value tone />` onde `tone` é `default | warn | error`.

### 6.8. `<NewTaskInline />` (NOVO, leve) e `<NewTaskSheet />` (refactor do `<NewTaskForm />`)

**`<NewTaskInline />`** no rodapé de cada coluna. Click expande inline:
- Input título único (autofocus).
- Enter cria com state = state da coluna, template = `default` (yolo), branch auto.
- ESC cancela.

**`<NewTaskSheet />`** abre via header button `[N] + New task` ou pelo TaskDetailSheet em modo edição. Sheet right (mesma stack do drill-down — fecha o outro se aberto). Form completo com:
- Title (input)
- State (dropdown: ideas/ready)
- Template (dropdown da `/api/catalog`)
- Permission profile (dropdown derivado do template ou override)
- Branch prefix (input com hint do template)
- Project (dropdown se >1 project)
- Submit / Cancel.

Lógica é a `<NewTaskForm />` existente, só com layout shadcn.

### 6.9. `<ProjectsDrawer />` — REFACTOR (visual)

Mantém estrutura (tree projects → worktrees → orphans). Migra pra shadcn `<Sheet side="left" />`.

**Visual CIPHER:**
- Background `--bg-deep`, border-right subtle.
- Items com `::` prefix em headers.
- Hover acende verde.
- Counts em pills outline.

### 6.10. `<BootstrapModal />` — REFACTOR (visual)

Migra pra shadcn `<Dialog />`. Conteúdo (file watcher polling, manifest bootstrap explanation) mantido.

### 6.11. Empty / loading / error states globais

**Empty kanban** (no tasks): centered illustration ASCII ("`[no tasks yet]`" + brackets) + CTA "+ New task".
**Loading** (initial fetch): skeleton cards com pulse animation verde sutil.
**Error** (API offline): banner top abaixo do HUD com `aria-live="assertive"` + retry button. Status bar `state: offline` magenta.
**Master cold start:** já coberto em §6.6.

## 7. Interactions

### 7.1. Drag-and-drop

Mantém `@dnd-kit/core` + `@dnd-kit/sortable` (já em deps). Mudanças visuais:
- Card em drag: rotate(2deg) scale(1.03) + box-shadow lift + brackets verdes acesos.
- Column drop zone: borda dashed verde sutil enquanto card over.
- Animation: `transition: transform 0.18s ease` no card drop.

Gotcha #12 (PointerSensor.activationConstraint) preservada.

### 7.2. Keyboard shortcuts

Hook `useKeyboardShortcut(key, handler, { meta? })` registra global.

| Key | Action |
|---|---|
| `/` | Focar Filter input |
| `P` | Toggle ProjectsDrawer |
| `N` | Abrir NewTaskSheet |
| `ESC` | Fechar Sheet / Drawer / Dialog ativo |
| `J` / `K` | Navegar entre cards (próximo / anterior) — futuro |
| `Enter` (em card selecionado) | Abrir TaskDetailSheet — futuro |

Shortcuts visíveis no header e tooltips. `kbd` styled como mini-chip outline verde.

### 7.3. Live updates

WebSocket `/ws` existente (envelope `{type, session_id, payload, at}`) continua entregando `session.status`, `task.created`, etc. UI consome via TanStack Query invalidation (já implementado).

**Adições:**
- WS heartbeat ping a cada 5s pra calcular RTT → `useWebSocketRTT()` retorna ms pro footer master + status bar.
- WS reconnect com backoff exponencial (existente em F2/F8) — UI mostra `state: reconnecting` no status bar.

## 8. Tech stack & implementation strategy

### 8.1. Stack adicionada

```
tailwindcss@^4.0
@tailwindcss/vite     (Vite plugin v4)
@radix-ui/react-*     (via shadcn)
class-variance-authority
clsx
tailwind-merge
lucide-react          (icons, mas usar com parcimônia — CIPHER é ASCII-first)
sonner                (toast)
cmdk                  (Command palette — futuro)
```

shadcn components a instalar inicialmente: `button`, `sheet`, `dialog`, `tabs`, `dropdown-menu`, `tooltip`, `toast` (sonner), `badge`, `input`, `command` (futuro).

### 8.2. Estrutura de arquivos

```
ui/
  src/
    app/
      AppShell.tsx        # layout: HudTopBar + AppHeader + main grid + StatusBar
      AppRoutes.tsx       # se router; senão, conditional render
    components/
      hud/
        HudTopBar.tsx
        HudMetric.tsx
      header/
        AppHeader.tsx
        BrandMark.tsx
      kanban/
        Kanban.tsx        (refactor)
        KanbanColumn.tsx  (refactor)
        TaskCard.tsx      (refactor; mantém testes)
        NewTaskInline.tsx (novo)
      task-detail/
        TaskDetailSheet.tsx       (substitui TaskDetailModal)
        OverviewTab.tsx
        SessionsTab.tsx
        RunTab.tsx                (refactor)
        LogsTab.tsx
      master/
        MasterSidebar.tsx         (refactor visual)
        MasterHeader.tsx
        QuickCommands.tsx         (novo)
        MasterFooter.tsx
      drawers/
        ProjectsDrawer.tsx        (refactor)
        NewTaskSheet.tsx          (refactor de NewTaskForm)
      status/
        StatusBar.tsx
        StatusSeg.tsx
      ui/                         # shadcn primitives auto-geradas
        button.tsx
        sheet.tsx
        dialog.tsx
        tabs.tsx
        ...
    hooks/
      useSystemHealth.ts          (novo; chama /api/health)
      useWebSocketRTT.ts          (novo; ping-based)
      useKeyboardShortcut.ts      (novo)
      useCatalog.ts               (existente)
    lib/
      tokens.css                  # CSS vars (paleta + tipografia)
      utils.ts                    # cn() helper do shadcn
    index.css                     # import tokens.css + tailwind diretivas
  tailwind.config.ts              # extend.colors mapeados pros CSS vars
  postcss.config.js
```

### 8.3. Ordem de implementação proposta (a writing-plans desenvolve)

1. Setup Tailwind + shadcn (deps + configs + tokens base).
2. Migrar `<AppShell />` (HudTopBar + AppHeader + StatusBar) — mais visível.
3. Migrar Kanban + Column + Card (mantém todos os testes passando).
4. Substituir TaskDetailModal por TaskDetailSheet + tabs.
5. Migrar MasterSidebar visual + adicionar QuickCommands.
6. Migrar ProjectsDrawer + NewTaskForm (vira Sheet).
7. Adicionar `/api/health` endpoint stub + useSystemHealth.
8. Refinar paleta (less green-dominance, ajustar tons in-context).
9. Empty/loading/error states.
10. Keyboard shortcuts.
11. Polish: animations, transitions, focus rings.

### 8.4. Endpoint novo necessário

`GET /api/health` — retorna `{ cpu_pct, mem_used_bytes, mem_total_bytes, ws_rtt_ms, uptime_seconds, active_alerts_count }`.

- `cpu_pct` / `mem_*`: lê via `psutil`.
- `ws_rtt_ms`: **preferência: WS ping client-side (1s)** — UI envia ping, daemon responde pong, RTT calculado no client e exposto via hook. HTTP `/api/health` não carrega RTT (não faz sentido — endpoint serve métricas de sistema 5s-polling). Mantém cada canal com sua responsabilidade.
- `uptime_seconds`: `time.time() - daemon.startup_time`.
- `active_alerts_count`: count de Sessions com `status='awaiting_response'`.

Endpoint pode entrar em ADR-0023 se justificar.

## 9. Open questions / follow-ups

- [ ] Paleta refinamento: depois da impl base, abrir PR de tuning com swatches calibradas (less green-dominance, cinzas-quentes pra texto secundário, magenta como spot color disciplinado).
- [ ] `/api/health` real-time vs polling: polling 5s aceitável no MVP, mas RTT precisa update mais rápido (1s WS ping) — definir na impl.
- [ ] Command palette (cmdk) — `Ctrl+K` global pra search/jump-to-task: scope de F9+1.
- [ ] Filter input no header: scope desta spec? Decisão: **stub UI nessa spec** (botão acende focus em input fantasma), implementar filter logic em F9+1.
- [ ] Light mode: out of scope MVP redesign. Considerar F9+2.
- [ ] Status bar `mode` segment: o que isso significa de fato? Placeholder no MVP; semantic real em follow-up.
- [ ] HUD `OPER` badge: clicar nele faz algo? Default: nada (decorativo). Se for clickable, abre `/health` dashboard — fora de scope.

## 10. Out of scope desta spec

- **Bug F8 master "não funcionou"** — tratado em spec separada. Esta spec assume Master Session funcional.
- Backend changes além do endpoint `/api/health` stub.
- Migration de banco (zero alterações no schema).
- Mobile/responsive layouts (J-arvis é desktop-only).
- I18n (UI em inglês, decisão F0).
- Telemetry / analytics.
- Themes alternativos (light, alternate accent).

## 11. ADRs derivadas

A criar durante impl (numeração após ADR-0022 do F8.g, confirmado):

- **ADR-0023:** `/api/health` endpoint + useSystemHealth hook pattern + WS ping-pong pra RTT.
- **ADR-0024:** Tailwind v4 + shadcn/ui adoption + Radix UI primitives.
- **ADR-0025 (opcional):** Identidade visual CIPHER e tokens canônicos.

## 12. Decisão final

CIPHER v2 com paleta-refinar-na-impl, estrutura A (kanban + master 400px), Tailwind v4 + shadcn, JetBrains Mono + Space Grotesk, HUD top bar + status bar tmux-style, TaskDetailSheet substituindo Modal, NewTaskInline+Sheet em duas modalidades, Master Session preserva comportamento + adiciona quick commands strip.

Aprovação implícita pendente: revisão do usuário sobre esta spec antes de partir pra `writing-plans`.
