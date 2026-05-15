# ADR-0025: Component architecture — AppShell + folder por domínio

**Status:** Accepted — 2026-05-12
**Decisores:** marcosdid + Claude
**Contexto:** F9 (UI redesign pós-MVP)

## Contexto

A UI MVP tinha `ui/src/components/` flat — 15+ arquivos no mesmo nível (Kanban.tsx, TaskCard.tsx, MasterSidebar.tsx, NewTaskForm.tsx, ProjectsDrawer.tsx, BootstrapModal.tsx, RunTab.tsx, etc.). Funcional, mas três problemas:

1. **Sem boundaries claros**: TaskDetailModal carregava 194 LOC com title/desc/state/branch editing + sub-componentes inline (`BranchEditField`). Não dava pra reusar pedaços.
2. **App.tsx fazia layout**: header com `<h1>J-arvis</h1>` + projects drawer toggle inline. Mistura de concerns.
3. **Sem operator surface**: F9 introduz HUD top bar + StatusBar pra métricas live. Precisam de layout outermost — não pode ser `App.tsx` decidindo isso.

## Decisão

**AppShell como container outermost** + **folder-por-domínio em `ui/src/components/`**.

### AppShell (`ui/src/app/AppShell.tsx`)

Grid `grid-rows-[auto_auto_auto_1fr_auto]` montando:
1. `HudTopBar` — métricas live no topo (always-on).
2. `ErrorBanner` — alerta quando WS offline/reconnecting (conditional).
3. `AppHeader` — brand + counts + 4 action buttons + keyboard shortcuts.
4. `{children}` — Kanban (área principal).
5. `StatusBar` — tmux-style footer.

`App.tsx` foca em data + state (queries, drawer toggles, sheet open state). Layout é responsabilidade do AppShell.

### Folder-por-domínio

```
ui/src/
├── app/
│   └── AppShell.tsx               # layout outermost
├── components/
│   ├── hud/                       # HUD top bar (operator chrome)
│   │   ├── HudTopBar.tsx
│   │   └── HudMetric.tsx          # atom
│   ├── header/                    # App header + brand
│   │   ├── AppHeader.tsx
│   │   └── BrandMark.tsx
│   ├── status/                    # Status bar + error banner
│   │   ├── StatusBar.tsx
│   │   ├── StatusSeg.tsx          # atom
│   │   └── ErrorBanner.tsx
│   ├── kanban/                    # Kanban board
│   │   ├── Kanban.tsx
│   │   ├── KanbanColumn.tsx
│   │   ├── TaskCard.tsx
│   │   ├── TaskCardSkeleton.tsx
│   │   ├── NewTaskInline.tsx
│   │   └── taskCardState.ts       # pure helper
│   ├── master/                    # Master Claude session sidebar
│   │   ├── MasterSidebar.tsx      # xterm + WS
│   │   ├── MasterHeader.tsx
│   │   ├── QuickCommands.tsx
│   │   └── MasterFooter.tsx
│   ├── task-detail/               # TaskDetailSheet + tabs
│   │   ├── TaskDetailSheet.tsx
│   │   ├── OverviewTab.tsx
│   │   ├── SessionsTab.tsx
│   │   ├── RunTab.tsx
│   │   └── LogsTab.tsx
│   ├── drawers/                   # Right-side sheets
│   │   ├── ProjectsDrawer.tsx
│   │   └── NewTaskSheet.tsx
│   ├── dialogs/                   # Modal dialogs
│   │   └── BootstrapModal.tsx
│   └── ui/                        # shadcn primitives (auto-generated)
│       ├── button.tsx
│       ├── sheet.tsx
│       └── ...
├── hooks/                         # useSystemHealth, useWebSocketRTT, ...
├── lib/                           # api, utils, tokens, formatters
└── stores/                        # zustand stores (wsConnection)
```

Regras:
- Cada folder = 1 domínio coeso (HUD, kanban, master session, etc.).
- Atoms (HudMetric, StatusSeg, BrandMark) ficam no mesmo folder do composer principal.
- Pure helpers (`taskCardState.ts`, `formatBytes`) ficam ao lado dos componentes que os usam.
- `ui/` é exceção — shadcn primitives auto-geradas com regras próprias.

### Padrões de teste

- Cada componente tem `.test.tsx` no mesmo folder.
- Hooks e helpers puros em `src/hooks/` e `src/lib/` têm 100% coverage gate (em `vite.config.ts`).
- Stores em `src/stores/` também 100% coverage.
- Componentes não têm gate de cobertura strict, mas testes existem pra cada um.

## Consequências

**Positivas:**
- Boundaries claros — cada folder tem 1 responsabilidade reconhecível.
- `App.tsx` ficou ~80 LOC focado em data + state.
- Reuso possível — TaskDetailSheet tabs vivem em `task-detail/`, podem ser reorganizadas sem tocar shell.
- Atoms isolados — HudMetric/StatusSeg são primitives próprios, testáveis sem o composer.

**Negativas:**
- Mais folders = mais imports relativos longos (`../../lib/api`). Mitigado pelo path alias `@/*` configurado em `tsconfig.json` + `vite.config.ts` (set up pelo shadcn init em Task 0.5).
- Pra adicionar nova feature, decidir qual folder pode pausar momentaneamente. Mas a regra "domínio" geralmente resolve.

**Operacionais:**
- Pra adicionar um novo domínio (ex.: "search"), criar folder novo, não enfiar em `kanban/` ou `header/`.
- Atoms novos vão no mesmo folder do seu primeiro composer.
- Pure helpers viram seu próprio `.ts` quando ficam grandes ou compartilhados — caso contrário inlinem no componente.
