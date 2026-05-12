# UI Redesign — CIPHER identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substitui a UI vanilla atual (CSS puro, sem framework) por uma UI Tailwind v4 + shadcn/ui com identidade "CIPHER v2" (operator cyberpunk autêntico) — sem regressão funcional e sem mudanças em backend/banco além de um endpoint `/api/health` stub.

**Architecture:** Camada visual e estrutural-de-frontend somente. Componentes existentes (Kanban, TaskCard, MasterSidebar, NewTaskForm, ProjectsDrawer, BootstrapModal, RunTab, RunLogsPanel, ProjectFilters) são refatorados preservando props/behavior pra manter os 251 testes UI verdes. Novos componentes: AppShell, HudTopBar, AppHeader, StatusBar, TaskDetailSheet (substitui TaskDetailModal), NewTaskInline, QuickCommands. Hooks novos: useSystemHealth, useWebSocketRTT, useKeyboardShortcut. Endpoint novo: `GET /api/health`.

**Tech Stack:** Tailwind v4 + `@tailwindcss/vite`, shadcn/ui (Radix UI), `class-variance-authority`, `clsx`, `tailwind-merge`, `sonner` (toast), `lucide-react` (ícones sparingly). Fonts: JetBrains Mono + Space Grotesk via `@fontsource`. Backend: FastAPI (existente) + `psutil` pra métricas.

**Spec source of truth:** `docs/superpowers/specs/2026-05-12-ui-redesign-design.md`. Consulte-a sempre que houver dúvida de comportamento/visual.

**Branch & commit prefix:**
- Este plan deve ser executado em uma branch nova `feat/f9-ui-redesign`, criada a partir de `main` **depois** que `feat/f8-master-session` for mergeada. Antes do merge do F8, o plan fica em standby.
- Commit prefix: `feat(F9.X):` / `refactor(F9.X):` / `chore(F9.X):` etc. — segue convenção do repo.

**Structural notes (verified against current repo):**
- Routers ficam em `orchestrator/api/` (não em `orchestrator/routers/`).
- DB session injection: `from orchestrator.api._deps import get_db_session` (não `from orchestrator.db import get_session`).
- Models: `from orchestrator.store.models import ClaudeSession` (não `from orchestrator.models import ...`).
- WS handlers: `orchestrator/api/master_ws.py` (não `orchestrator/ws/master.py`).
- Testes: `tests/unit/` é flat (sem subdir `api/` ou `ws/`); endpoints REST com client testam-se em `tests/integration/`. Pode haver colisão de nome de arquivo — usar `test_api_health.py` (não `test_health.py`, que já existe e cobre `health_status()` puro).
- `tokens.css` contém **apenas CSS custom properties**. Decorações com pseudo-elements / animações globais (`scanlines`, `cipher-blink`) ficam em `index.css`.

---

## File structure overview

```
ui/
  src/
    app/
      AppShell.tsx                     # NEW — top-level layout (HUD + header + main + status)
    components/
      hud/
        HudTopBar.tsx                  # NEW — métricas vivas no topo
        HudMetric.tsx                  # NEW — atom de label+value
      header/
        AppHeader.tsx                  # NEW — extrai do App.tsx
        BrandMark.tsx                  # NEW — "> j-arvis_" com cursor
      status/
        StatusBar.tsx                  # NEW — tmux-style rodapé
        StatusSeg.tsx                  # NEW — atom segment
      kanban/
        Kanban.tsx                     # REFACTOR — mantém props e dnd-kit
        KanbanColumn.tsx               # REFACTOR — visual CIPHER
        TaskCard.tsx                   # REFACTOR — anatomia + 8 estados
        NewTaskInline.tsx              # NEW — quick-add no footer da coluna
      task-detail/
        TaskDetailSheet.tsx            # NEW — substitui TaskDetailModal
        OverviewTab.tsx                # NEW
        SessionsTab.tsx                # NEW
        RunTab.tsx                     # MOVE+REFACTOR (já existe em components/)
        LogsTab.tsx                    # NEW
      master/
        MasterSidebar.tsx              # REFACTOR — preserva xterm/WS/PTY
        MasterHeader.tsx               # NEW — title + actions + meta
        QuickCommands.tsx              # NEW — strip de comandos MCP
        MasterFooter.tsx               # NEW — PTY size + pid + RTT
      drawers/
        ProjectsDrawer.tsx             # REFACTOR — Sheet left, visual CIPHER
        NewTaskSheet.tsx               # REFACTOR de NewTaskForm.tsx — Sheet right
      ui/                              # shadcn primitives (auto-geradas)
        button.tsx
        sheet.tsx
        dialog.tsx
        tabs.tsx
        tooltip.tsx
        badge.tsx
        input.tsx
        dropdown-menu.tsx
        skeleton.tsx
        sonner.tsx
    hooks/
      useSystemHealth.ts               # NEW — polling /api/health
      useWebSocketRTT.ts               # NEW — WS ping pra RTT
      useKeyboardShortcut.ts           # NEW — global hotkeys
    lib/
      tokens.css                       # NEW — CSS variables (paleta + tipografia)
      utils.ts                         # NEW — cn() helper shadcn
    index.css                          # REWRITE — Tailwind directives + tokens import + scanlines
  tailwind.config.ts                   # NEW
  postcss.config.js                    # NEW (se necessário; Tailwind v4 pode dispensar)
  components.json                      # NEW — shadcn config
  package.json                         # MODIFY — deps
orchestrator/
  api/
    health.py                          # NEW — GET /api/health
    master_ws.py                       # MODIFY — adicionar pong handler (Task 2.2)
  main.py                              # MODIFY — registra health router
tests/
  integration/
    test_api_health.py                 # NEW — testes do endpoint (integration porque usa FastAPI client + DB)
    test_master_ws_pong.py             # NEW — testes do pong handler
```

**Files DELETED at end:**
- `ui/src/components/TaskDetailModal.tsx` (substituído por TaskDetailSheet)
- `ui/src/components/TaskDetailModal.test.tsx` (testes migrados pra TaskDetailSheet.test.tsx)
- `ui/src/components/NewTaskForm.tsx` (substituído por NewTaskSheet — comportamento idêntico, novo nome)
- `ui/src/components/NewTaskForm.test.tsx` (testes migrados)

---

## Phase 0 — Foundation: Tailwind + shadcn setup

### Task 0.1: Install Tailwind v4 + Vite plugin

**Files:**
- Modify: `ui/package.json`
- Test: smoke test (build passa)

- [ ] **Step 1: Add deps**

```bash
cd ui
pnpm add -D tailwindcss@^4.0 @tailwindcss/vite
pnpm add class-variance-authority clsx tailwind-merge
```

- [ ] **Step 2: Configure Vite plugin**

Modify `ui/vite.config.ts` — adiciona `@tailwindcss/vite()` no plugins array. Mantém os existentes.

- [ ] **Step 3: Smoke test build**

```bash
pnpm build
```
Expected: build passa. Type errors são esperados nesta fase porque ainda não temos Tailwind classes — só pra confirmar o plugin não quebra.

- [ ] **Step 4: Commit**

```bash
git add ui/package.json ui/pnpm-lock.yaml ui/vite.config.ts
git commit -m "chore(F9.0): add tailwind v4 + class-variance-authority deps"
```

---

### Task 0.2: Create tokens.css (design tokens CSS vars)

**Files:**
- Create: `ui/src/lib/tokens.css`

- [ ] **Step 1: Write tokens.css**

```css
/* Design tokens — CIPHER v2 identity
 * Reference: docs/superpowers/specs/2026-05-12-ui-redesign-design.md §4.2
 * Note: tons exatos sujeitos a refinamento na fase 17 (less green-dominance).
 */

:root {
  /* Background scale */
  --bg-void: #030503;
  --bg-deep: #060906;
  --bg-surface: #080c08;
  --bg-elevated: #0c100c;
  --bg-muted: #0a0d0a;

  /* Border scale */
  --border-subtle: #1a2a1a;
  --border-mid: #2a3a2a;
  --border-strong: #4ade80;

  /* Text scale */
  --text-faint: #3a4a3a;
  --text-subtle: #5a6a5a;
  --text-body: #6a7a6a;
  --text-emphasis: #b8c4b3;
  --text-title: #d4e4d0;

  /* Accent + semantic */
  --accent-primary: #4ade80;
  --accent-attn: #ff10f0;
  --accent-info: #00d4ff;
  --semantic-error: #f87171;
  --semantic-warn: #fbbf24;
  --semantic-frontend: #00d4ff;
  --semantic-backend: #4ade80;
  --semantic-bugfix: #f87171;
  --semantic-refactor: #c084fc;
  --semantic-review: #a855f7;

  /* Typography */
  --font-mono: 'JetBrains Mono', ui-monospace, 'SFMono-Regular', monospace;
  --font-display: 'Space Grotesk', system-ui, sans-serif;
}
```

- [ ] **Step 2: Commit**

```bash
git add ui/src/lib/tokens.css
git commit -m "feat(F9.0): add CIPHER design tokens CSS vars"
```

---

### Task 0.3: Configure tailwind.config.ts + components.json

**Files:**
- Create: `ui/tailwind.config.ts`
- Create: `ui/components.json`
- Modify: `ui/src/index.css`

- [ ] **Step 1: Write tailwind.config.ts** mapeando tokens

```typescript
import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: {
          void: 'var(--bg-void)',
          deep: 'var(--bg-deep)',
          surface: 'var(--bg-surface)',
          elevated: 'var(--bg-elevated)',
          muted: 'var(--bg-muted)',
        },
        border: {
          subtle: 'var(--border-subtle)',
          mid: 'var(--border-mid)',
          strong: 'var(--border-strong)',
        },
        text: {
          faint: 'var(--text-faint)',
          subtle: 'var(--text-subtle)',
          body: 'var(--text-body)',
          emphasis: 'var(--text-emphasis)',
          title: 'var(--text-title)',
        },
        accent: {
          primary: 'var(--accent-primary)',
          attn: 'var(--accent-attn)',
          info: 'var(--accent-info)',
        },
        sem: {
          error: 'var(--semantic-error)',
          warn: 'var(--semantic-warn)',
          frontend: 'var(--semantic-frontend)',
          backend: 'var(--semantic-backend)',
          bugfix: 'var(--semantic-bugfix)',
          refactor: 'var(--semantic-refactor)',
          review: 'var(--semantic-review)',
        },
      },
      fontFamily: {
        mono: 'var(--font-mono)',
        display: 'var(--font-display)',
      },
    },
  },
} satisfies Config;
```

- [ ] **Step 2: Write components.json (shadcn config)**

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "default",
  "rsc": false,
  "tsx": true,
  "tailwind": {
    "config": "tailwind.config.ts",
    "css": "src/index.css",
    "baseColor": "neutral",
    "cssVariables": true
  },
  "aliases": {
    "components": "src/components",
    "utils": "src/lib/utils"
  }
}
```

- [ ] **Step 3: Rewrite index.css** com Tailwind directives + tokens + scanlines globais

```css
@import './lib/tokens.css';
@import '@fontsource/jetbrains-mono/400.css';
@import '@fontsource/jetbrains-mono/500.css';
@import '@fontsource/jetbrains-mono/600.css';
@import '@fontsource/jetbrains-mono/700.css';
@import '@fontsource/jetbrains-mono/800.css';
@import '@fontsource/space-grotesk/600.css';
@import '@fontsource/space-grotesk/700.css';
@import "tailwindcss";
@config "../tailwind.config.ts";  /* REQUIRED: Tailwind v4 does not auto-discover JS configs */

* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { height: 100%; }

body {
  background: var(--bg-void);
  color: var(--text-emphasis);
  font-family: var(--font-mono);
  font-feature-settings: 'tnum';
}

/* Scanlines overlay (CIPHER identity) */
body::before {
  content: '';
  position: fixed; inset: 0; pointer-events: none; z-index: 1;
  background-image: repeating-linear-gradient(
    0deg,
    transparent 0px,
    transparent 2px,
    rgba(74, 222, 128, 0.04) 2px,
    rgba(74, 222, 128, 0.04) 3px
  );
}

/* Blink animation for cursor and live-dots */
@keyframes cipher-blink {
  50% { opacity: 0.3; }
}
@keyframes cipher-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.35; transform: scale(0.85); }
}
```

- [ ] **Step 4: Install font deps**

```bash
cd ui
pnpm add @fontsource/jetbrains-mono @fontsource/space-grotesk
```

- [ ] **Step 5: Verify dev server boots**

```bash
make dev-ui  # or: cd ui && pnpm dev
```
Expected: Vite ready in <500ms, no Tailwind errors.

- [ ] **Step 6: Commit**

```bash
git add ui/tailwind.config.ts ui/components.json ui/src/index.css ui/package.json ui/pnpm-lock.yaml
git commit -m "feat(F9.0): wire Tailwind v4 + shadcn config + CIPHER tokens"
```

---

### Task 0.4: Create lib/utils.ts (cn helper)

**Files:**
- Create: `ui/src/lib/utils.ts`
- Test: `ui/src/lib/utils.test.ts`

- [ ] **Step 1: Write the failing test**

```typescript
// ui/src/lib/utils.test.ts
import { describe, it, expect } from 'vitest';
import { cn } from './utils';

describe('cn helper', () => {
  it('merges class names', () => {
    expect(cn('a', 'b')).toBe('a b');
  });
  it('drops falsy values', () => {
    expect(cn('a', false, null, undefined, '', 'b')).toBe('a b');
  });
  it('merges tailwind conflicts (later wins)', () => {
    expect(cn('p-2', 'p-4')).toBe('p-4');
  });
});
```

- [ ] **Step 2: Run failing test**

```bash
cd ui && pnpm test src/lib/utils.test.ts
```
Expected: FAIL with "Cannot find module './utils'"

- [ ] **Step 3: Implement utils.ts**

```typescript
// ui/src/lib/utils.ts
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
```

- [ ] **Step 4: Verify pass**

```bash
cd ui && pnpm test src/lib/utils.test.ts
```
Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add ui/src/lib/utils.ts ui/src/lib/utils.test.ts
git commit -m "feat(F9.0): cn() helper for shadcn class composition"
```

---

### Task 0.5: Install shadcn primitives

**Files:**
- Auto-generated: `ui/src/components/ui/{button,sheet,dialog,tabs,tooltip,badge,input,dropdown-menu,skeleton,sonner}.tsx`

- [ ] **Step 1: Init shadcn (interactive — answer "y" to all)**

```bash
cd ui
pnpx shadcn@latest init
```
Expected: prompts for style/base color/cssVariables. Use existing `components.json` (já criado em 0.3). Should answer compatibility.

- [ ] **Step 2: Add primitives**

```bash
pnpx shadcn@latest add button sheet dialog tabs tooltip badge input dropdown-menu skeleton sonner
```

- [ ] **Step 3: Verify imports compile**

Create a temporary `ui/src/_smoke_shadcn.tsx`:
```tsx
import { Button } from './components/ui/button';
import { Sheet } from './components/ui/sheet';
export const _smoke = () => <><Button>x</Button><Sheet open={false} /></>;
```

```bash
cd ui && pnpm tsc --noEmit
```
Expected: no errors.

- [ ] **Step 4: Delete smoke file + commit**

```bash
rm ui/src/_smoke_shadcn.tsx
git add ui/src/components/ui ui/package.json ui/pnpm-lock.yaml
git commit -m "feat(F9.0): install shadcn primitives (button, sheet, dialog, tabs, tooltip, badge, input, dropdown-menu, skeleton, sonner)"
```

---

## Phase 1 — Backend: /api/health endpoint

> **Note:** the existing `/health` (em `main.py:256`) é um liveness simples que retorna `{"status": "ok"}` — **não tocar**. O novo endpoint é `/api/health` (path diferente), com responsabilidade ampliada (métricas). Test `tests/unit/test_health.py` existente cobre apenas `health_status()` core function — também não tocar.

### Task 1.1: Add /api/health endpoint

**Files:**
- Create: `orchestrator/api/health.py`
- Modify: `orchestrator/main.py` (registra router junto aos outros `include_router`)
- Test: `tests/integration/test_api_health.py` (integração — usa FastAPI client + DB session real)

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_api_health.py
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


async def test_health_returns_expected_shape(client: AsyncClient):
    r = await client.get('/api/health')
    assert r.status_code == 200
    data = r.json()
    assert set(data.keys()) >= {
        'cpu_pct',
        'mem_used_bytes',
        'mem_total_bytes',
        'uptime_seconds',
        'active_alerts_count',
    }
    assert isinstance(data['cpu_pct'], (int, float))
    assert data['mem_total_bytes'] > 0
    assert data['active_alerts_count'] >= 0
```

(Use the same `client` fixture as other integration tests; ver `tests/integration/test_health_route.py` ou `tests/integration/conftest.py` pra confirmar o nome).

- [ ] **Step 2: Run failing test**

```bash
uv run pytest tests/integration/test_api_health.py -v
```
Expected: FAIL (404 ou import error).

- [ ] **Step 3: Implement router**

```python
# orchestrator/api/health.py
from __future__ import annotations

import time
from typing import Annotated

import psutil
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.api._deps import get_db_session
from orchestrator.store.models import ClaudeSession

router = APIRouter(tags=['health'])

_startup_time = time.time()


class HealthResponse(BaseModel):
    cpu_pct: float
    mem_used_bytes: int
    mem_total_bytes: int
    uptime_seconds: int
    active_alerts_count: int


@router.get('/health', response_model=HealthResponse)
async def get_health(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> HealthResponse:
    mem = psutil.virtual_memory()
    alerts_count = await session.scalar(
        select(func.count())
        .select_from(ClaudeSession)
        .where(ClaudeSession.status == 'awaiting_response')
    )
    return HealthResponse(
        cpu_pct=psutil.cpu_percent(interval=None),
        mem_used_bytes=mem.used,
        mem_total_bytes=mem.total,
        uptime_seconds=int(time.time() - _startup_time),
        active_alerts_count=int(alerts_count or 0),
    )
```

- [ ] **Step 4: Register router in main.py**

Modify `orchestrator/main.py`: import `from orchestrator.api.health import router as health_api_router` then add `app.include_router(health_api_router, prefix="/api")` next to other `include_router` calls (around line 120-132).

- [ ] **Step 5: Add psutil dep**

```bash
uv add psutil
```

- [ ] **Step 6: Run test, verify pass**

```bash
uv run pytest tests/integration/test_api_health.py -v
```
Expected: PASS

- [ ] **Step 7: Verify backend coverage gate**

```bash
make test-all
```
Expected: all unit + integration tests pass, coverage 100%.

- [ ] **Step 8: Commit**

```bash
git add orchestrator/api/health.py orchestrator/main.py tests/integration/test_api_health.py pyproject.toml uv.lock
git commit -m "feat(F9.1): add /api/health endpoint (cpu/mem/uptime/alerts)"
```

---

## Phase 2 — Hooks foundation

### Task 2.1: useSystemHealth hook (polling /api/health)

**Files:**
- Create: `ui/src/hooks/useSystemHealth.ts`
- Test: `ui/src/hooks/useSystemHealth.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// ui/src/hooks/useSystemHealth.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useSystemHealth } from './useSystemHealth';

const wrapper = ({ children }: { children: React.ReactNode }) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
};

describe('useSystemHealth', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: true,
      json: async () => ({
        cpu_pct: 12.4,
        mem_used_bytes: 2147483648,
        mem_total_bytes: 34359738368,
        uptime_seconds: 16380,
        active_alerts_count: 1,
      }),
    })));
  });
  afterEach(() => vi.unstubAllGlobals());

  it('fetches health data', async () => {
    const { result } = renderHook(() => useSystemHealth(), { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data?.cpu_pct).toBe(12.4);
    expect(result.current.data?.active_alerts_count).toBe(1);
  });
});
```

- [ ] **Step 2: Run failing test** — `cd ui && pnpm test useSystemHealth`. Expected FAIL.

- [ ] **Step 3: Implement hook**

```typescript
// ui/src/hooks/useSystemHealth.ts
import { useQuery } from '@tanstack/react-query';

export type SystemHealth = {
  cpu_pct: number;
  mem_used_bytes: number;
  mem_total_bytes: number;
  uptime_seconds: number;
  active_alerts_count: number;
};

async function fetchHealth(): Promise<SystemHealth> {
  const r = await fetch('/api/health');
  if (!r.ok) throw new Error(`health endpoint ${r.status}`);
  return r.json();
}

export function useSystemHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 5_000,
    staleTime: 4_000,
  });
}
```

- [ ] **Step 4: Verify test passes** → `pnpm test useSystemHealth`. Expected PASS.

- [ ] **Step 5: Commit**

```bash
git add ui/src/hooks/useSystemHealth.ts ui/src/hooks/useSystemHealth.test.tsx
git commit -m "feat(F9.2): useSystemHealth hook polls /api/health every 5s"
```

---

### Task 2.2: useWebSocketRTT hook

**Files:**
- Create: `ui/src/hooks/useWebSocketRTT.ts`
- Test: `ui/src/hooks/useWebSocketRTT.test.tsx`

**Behavior:** sends `{type:"ping", ts: <now_ms>}` over WS every 1s, measures RTT when matching pong returns.

- [ ] **Step 1: Write the failing test**

```tsx
// ui/src/hooks/useWebSocketRTT.test.tsx
import { describe, it, expect, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useWebSocketRTT } from './useWebSocketRTT';

class FakeWS {
  readyState = WebSocket.OPEN;
  sent: string[] = [];
  onmessage: ((ev: MessageEvent) => void) | null = null;
  send(s: string) { this.sent.push(s); }
  close() {}
}

describe('useWebSocketRTT', () => {
  it('records RTT after pong', async () => {
    vi.useFakeTimers();
    const ws = new FakeWS();
    const { result } = renderHook(() => useWebSocketRTT(ws as unknown as WebSocket));
    // simulate ping cycle
    await act(async () => { vi.advanceTimersByTime(1000); });
    const sent = JSON.parse(ws.sent[0]);
    expect(sent.type).toBe('ping');
    await act(async () => {
      ws.onmessage?.({ data: JSON.stringify({ type: 'pong', ts: sent.ts }) } as MessageEvent);
    });
    expect(result.current).toBeGreaterThanOrEqual(0);
    vi.useRealTimers();
  });
});
```

- [ ] **Step 2: Run failing test.** Expected FAIL.

- [ ] **Step 3: Implement hook**

```typescript
// ui/src/hooks/useWebSocketRTT.ts
import { useEffect, useRef, useState } from 'react';

export function useWebSocketRTT(ws: WebSocket | null): number | null {
  const [rtt, setRtt] = useState<number | null>(null);
  const inflightRef = useRef<number | null>(null);

  useEffect(() => {
    if (!ws) return;

    const handler = (ev: MessageEvent) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === 'pong' && typeof msg.ts === 'number' && msg.ts === inflightRef.current) {
          setRtt(Date.now() - msg.ts);
          inflightRef.current = null;
        }
      } catch { /* ignore */ }
    };
    ws.addEventListener('message', handler);

    const interval = setInterval(() => {
      if (ws.readyState !== WebSocket.OPEN) return;
      const ts = Date.now();
      inflightRef.current = ts;
      ws.send(JSON.stringify({ type: 'ping', ts }));
    }, 1000);

    return () => {
      clearInterval(interval);
      ws.removeEventListener('message', handler);
    };
  }, [ws]);

  return rtt;
}
```

- [ ] **Step 4: Verify pass**.

- [ ] **Step 5: Backend pong support** — Modify `orchestrator/api/master_ws.py`: no message handler do WebSocket, se incoming msg `{"type":"ping", "ts": <n>}`, respond `{"type":"pong", "ts": <same_n>}` imediatamente (sem passar pro PTY). Adicionar test em `tests/integration/test_master_ws_pong.py` que conecta no `/ws/master`, envia ping, valida pong com mesmo `ts`.

- [ ] **Step 6: Verify both UI and backend pass**

```bash
cd ui && pnpm test useWebSocketRTT
uv run pytest tests/integration/test_master_ws_pong.py -v
```

- [ ] **Step 7: Commit**

```bash
git add ui/src/hooks/useWebSocketRTT.ts ui/src/hooks/useWebSocketRTT.test.tsx orchestrator/api/master_ws.py tests/integration/test_master_ws_pong.py
git commit -m "feat(F9.2): useWebSocketRTT hook + ws pong handler for RTT measurement"
```

---

### Task 2.3: useKeyboardShortcut hook

**Files:**
- Create: `ui/src/hooks/useKeyboardShortcut.ts`
- Test: `ui/src/hooks/useKeyboardShortcut.test.tsx`

**Behavior:** registers global keydown listener. Skips when event target is an `<input>`/`<textarea>`/`[contenteditable]`. Supports modifier keys via `{meta, ctrl, shift, alt}` options.

- [ ] **Step 1: Test (concise)** — assert handler fires on key, not fires on input focus, not fires on wrong key.

- [ ] **Step 2: Implement hook**

```typescript
// ui/src/hooks/useKeyboardShortcut.ts
import { useEffect } from 'react';

type Opts = { meta?: boolean; ctrl?: boolean; shift?: boolean; alt?: boolean };

export function useKeyboardShortcut(
  key: string,
  handler: (e: KeyboardEvent) => void,
  opts: Opts = {},
) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      if (target?.matches('input, textarea, [contenteditable=true]')) return;
      if (e.key.toLowerCase() !== key.toLowerCase()) return;
      if (!!opts.meta !== e.metaKey) return;
      if (!!opts.ctrl !== e.ctrlKey) return;
      if (!!opts.shift !== e.shiftKey) return;
      if (!!opts.alt !== e.altKey) return;
      e.preventDefault();
      handler(e);
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [key, handler, opts.meta, opts.ctrl, opts.shift, opts.alt]);
}
```

- [ ] **Step 3: Verify pass.**

- [ ] **Step 4: Commit**

```bash
git add ui/src/hooks/useKeyboardShortcut.ts ui/src/hooks/useKeyboardShortcut.test.tsx
git commit -m "feat(F9.2): useKeyboardShortcut for global hotkeys"
```

---

## Phase 3 — HUD top bar

### Task 3.1: HudMetric atom

**Files:**
- Create: `ui/src/components/hud/HudMetric.tsx`
- Test: `ui/src/components/hud/HudMetric.test.tsx`

- [ ] **Step 1: Failing test** — renders label + value, applies `hot` class when prop set.

- [ ] **Step 2: Implement**

```tsx
// ui/src/components/hud/HudMetric.tsx
import { cn } from '@/lib/utils';

type Props = {
  label: string;
  value: string | number;
  tone?: 'default' | 'hot';
};

export function HudMetric({ label, value, tone = 'default' }: Props) {
  return (
    <span className="inline-flex gap-1.5 items-center" data-testid={`hud-metric-${label}`}>
      <span className="text-text-faint">{label}</span>
      <span
        className={cn(
          'font-semibold tabular-nums',
          tone === 'hot' ? 'text-accent-attn drop-shadow-[0_0_6px_rgba(255,16,240,0.6)]' : 'text-accent-primary',
        )}
      >
        {value}
      </span>
    </span>
  );
}
```

(Note: `@/lib/utils` requires path alias setup in `tsconfig.json` + `vite.config.ts` — set it now if not done: `paths: { "@/*": ["src/*"] }`.)

- [ ] **Step 3: Verify pass + commit**

```bash
cd ui && pnpm test HudMetric
git add ui/src/components/hud/HudMetric.tsx ui/src/components/hud/HudMetric.test.tsx ui/tsconfig.json ui/vite.config.ts
git commit -m "feat(F9.3): HudMetric atom (label + value + tone)"
```

---

### Task 3.2: HudTopBar component

**Files:**
- Create: `ui/src/components/hud/HudTopBar.tsx`
- Test: `ui/src/components/hud/HudTopBar.test.tsx`

- [ ] **Step 1: Failing test** — mocks `useSystemHealth` to return canned data, asserts CPU/MEM/UPTIME/ALERTS appear, and `hot` tone applies when alerts > 0.

- [ ] **Step 2: Implement**

```tsx
// ui/src/components/hud/HudTopBar.tsx
import { useSystemHealth } from '@/hooks/useSystemHealth';
import { HudMetric } from './HudMetric';

function formatBytes(b: number): string {
  if (b < 1024) return `${b}B`;
  if (b < 1024 ** 2) return `${(b / 1024).toFixed(0)}K`;
  if (b < 1024 ** 3) return `${(b / 1024 ** 2).toFixed(0)}M`;
  return `${(b / 1024 ** 3).toFixed(1)}G`;
}

function formatUptime(s: number): string {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return `${h}h${m.toString().padStart(2, '0')}m`;
}

export function HudTopBar({ wsRtt }: { wsRtt: number | null }) {
  const { data } = useSystemHealth();

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center justify-between px-4 py-1.5 text-[0.62rem] tracking-wider border-b border-border-subtle bg-bg-deep text-text-subtle"
    >
      <div className="flex items-center gap-3.5">
        <span className="bg-accent-primary text-bg-void px-1.5 py-0.5 font-bold tracking-wider before:content-['●'] before:mr-1 before:animate-[cipher-blink_1.2s_steps(1)_infinite]">
          OPER
        </span>
        <span className="font-display font-bold tracking-[0.16em] text-accent-primary text-[0.65rem]">
          J-ARVIS // OP_CTRL
        </span>
        <span className="text-border-subtle">│</span>
        <HudMetric label="env" value="linux/x86_64" />
      </div>
      <div className="flex items-center gap-3.5">
        {data && (
          <>
            <HudMetric label="cpu" value={`${data.cpu_pct.toFixed(1)}%`} />
            <span className="text-border-subtle">│</span>
            <HudMetric label="mem" value={`${formatBytes(data.mem_used_bytes)}/${formatBytes(data.mem_total_bytes)}`} />
            <span className="text-border-subtle">│</span>
          </>
        )}
        <HudMetric label="rtt" value={wsRtt !== null ? `${wsRtt}ms` : '—'} />
        {data && (
          <>
            <span className="text-border-subtle">│</span>
            <HudMetric label="uptime" value={formatUptime(data.uptime_seconds)} />
            <span className="text-border-subtle">│</span>
            <HudMetric
              label="alert"
              value={data.active_alerts_count}
              tone={data.active_alerts_count > 0 ? 'hot' : 'default'}
            />
          </>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Verify pass + commit**

```bash
cd ui && pnpm test HudTopBar
git add ui/src/components/hud/HudTopBar.tsx ui/src/components/hud/HudTopBar.test.tsx
git commit -m "feat(F9.3): HudTopBar component with live metrics + alerts tone"
```

---

## Phase 4 — App header + brand

### Task 4.1: BrandMark component

**Files:**
- Create: `ui/src/components/header/BrandMark.tsx`
- Test: `ui/src/components/header/BrandMark.test.tsx`

- [ ] **Step 1: Test** — renders `> j-arvis` text, has blinking cursor via class.

- [ ] **Step 2: Implement**

```tsx
// ui/src/components/header/BrandMark.tsx
export function BrandMark() {
  return (
    <div className="flex items-center" aria-label="J-arvis brand">
      <span className="font-mono font-extrabold text-[1.05rem] tracking-tighter text-accent-primary drop-shadow-[0_0_8px_rgba(74,222,128,0.4)] before:content-['>'] before:mr-1 after:content-['_'] after:text-accent-attn after:animate-[cipher-blink_1s_steps(1)_infinite]">
        j-arvis
      </span>
    </div>
  );
}
```

- [ ] **Step 3: Verify pass + commit**.

---

### Task 4.2: AppHeader component

**Files:**
- Create: `ui/src/components/header/AppHeader.tsx`
- Test: `ui/src/components/header/AppHeader.test.tsx`

**Behavior:** brand + counts + 4 action buttons (Filter / Projects / Run / +New). Registers keyboard shortcuts `/`, `P`, `R`, `N`. `R` is a no-op stub (see spec §6.2/§7.2 — registered for forward-compat).

- [ ] **Step 1: Test** — render with counts, asserts buttons present, asserts `N` keyboard fires `onNewTask`.

- [ ] **Step 2: Implement**

```tsx
// ui/src/components/header/AppHeader.tsx
import { Button } from '@/components/ui/button';
import { BrandMark } from './BrandMark';
import { useKeyboardShortcut } from '@/hooks/useKeyboardShortcut';

type Props = {
  projectsCount: number;
  tasksCount: number;
  activeCount: number;
  onFilter?: () => void;
  onToggleProjects?: () => void;
  onNewTask?: () => void;
};

export function AppHeader({
  projectsCount, tasksCount, activeCount,
  onFilter, onToggleProjects, onNewTask,
}: Props) {
  useKeyboardShortcut('/', () => onFilter?.());
  useKeyboardShortcut('p', () => onToggleProjects?.());
  useKeyboardShortcut('n', () => onNewTask?.());
  useKeyboardShortcut('r', () => {/* no-op — F9+1 RunPanel placeholder */});

  return (
    <header className="flex justify-between items-center px-4 py-3 border-b border-border-subtle bg-bg-deep">
      <div className="flex items-center gap-3">
        <BrandMark />
        <div className="text-text-subtle text-[0.7rem] tracking-wide border-l border-border-subtle pl-3">
          <span className="text-accent-primary font-semibold">{projectsCount}</span> proj
          <span className="mx-1">·</span>
          <span className="text-accent-primary font-semibold">{tasksCount}</span> tsk
          <span className="mx-1">·</span>
          <span className="text-accent-primary font-semibold">{activeCount}</span> active
        </div>
      </div>
      <div className="flex gap-1.5 items-center">
        <Button variant="outline" size="sm" onClick={onFilter}>
          <span className="text-accent-primary font-bold mr-1">[/]</span>filter
        </Button>
        <Button variant="outline" size="sm" onClick={onToggleProjects}>
          <span className="text-accent-primary font-bold mr-1">[p]</span>projects
        </Button>
        <Button variant="outline" size="sm" disabled title="F9+1">
          <span className="text-accent-primary font-bold mr-1">[r]</span>run
        </Button>
        <Button variant="default" size="sm" onClick={onNewTask}>
          <span className="font-bold mr-1">[n]</span>new task
        </Button>
      </div>
    </header>
  );
}
```

- [ ] **Step 3: Verify pass + commit**.

---

## Phase 5 — Status bar

### Task 5.1: StatusSeg atom

**Files:**
- Create: `ui/src/components/status/StatusSeg.tsx`
- Test: `ui/src/components/status/StatusSeg.test.tsx`

- [ ] **Step 1: Test + impl** — atom: `label`, `value`, `tone='default'|'warn'|'error'`. Render as `<span>label value</span>` colored.

- [ ] **Step 2: Commit**.

---

### Task 5.2: StatusBar component

**Files:**
- Create: `ui/src/components/status/StatusBar.tsx`
- Test: `ui/src/components/status/StatusBar.test.tsx`
- (Optionally) Create: `ui/src/stores/wsState.ts` se não existir abstração equivalente

**Behavior:** flex row segments (left + right) separated by `│`. Spec §6.7.

**Pre-task: resolver dependência de WS state.** Antes de implementar StatusBar, investigar `ui/src/hooks/useSessionEvents.ts` (existente, usado em App.tsx) — verificar se ele já expõe estado de conexão (`connected | reconnecting | offline`). Se sim, consumir. Se não, criar um pequeno store zustand `useWsConnectionStore` que `useSessionEvents` atualiza (set state ao open/close/error). Comprimento: <40 linhas.

- [ ] **Step 1: Inspect useSessionEvents** — abrir o arquivo, anotar se já há estado exposto.

- [ ] **Step 2: Se necessário, criar store + hook** + atualizar useSessionEvents.

- [ ] **Step 3: Write failing test pra StatusBar** — mocks hooks pra retornar canned WS state e health data; asserta segmentos visíveis com tones corretos.

- [ ] **Step 4: Implement StatusBar** seguindo spec §6.7. Segments:
  - Left: `state` / `ws` / `mcp` / `alerts`
  - Right: `mode` (hardcoded `ops` no MVP) / `profile` (lê de master session metadata se disponível, senão `—`) / `git` (lê de `/api/projects` primary worktree branch) / `v` (lê de `import.meta.env.PACKAGE_VERSION` via Vite define ou hardcoded constant).

- [ ] **Step 5: Verify pass + commit**.

---

## Phase 6 — AppShell layout

### Task 6.1: AppShell wires HUD + Header + Main + StatusBar

**Files:**
- Create: `ui/src/app/AppShell.tsx`
- Modify: `ui/src/App.tsx` (envelopa em `AppShell`)
- Test: `ui/src/app/AppShell.test.tsx`

**Behavior:** layout grid — rows `auto auto 1fr auto`. Renders HudTopBar / AppHeader / `{children}` / StatusBar.

- [ ] **Step 1: Test + impl**.

- [ ] **Step 2: Refactor App.tsx** — moves brand/header logic to AppHeader. Remove `<h1>J-arvis</h1>` + `<button onClick={() => setDrawerOpen(true)}>Projetos ▾</button>` (já está no AppHeader).

- [ ] **Step 3: Verify all existing UI tests pass** (esp. ProjectsDrawer.test.tsx, Kanban.test.tsx).

- [ ] **Step 4: Commit**.

---

## Phase 7 — Kanban refactor (preserves tests)

### Task 7.1: KanbanColumn visual refactor

**Files:**
- Modify: `ui/src/components/KanbanColumn.tsx`
- Move to: `ui/src/components/kanban/KanbanColumn.tsx`
- Modify: `ui/src/components/kanban/KanbanColumn.test.tsx` (rename import path only)

**Behavior:** preserve props/DOM contract testado. Apenas mudam classes Tailwind + adicionam decorações (`::` prefix, corner brackets via `::before`/`::after`).

- [ ] **Step 1: Move file** — preserve git history with `git mv`.

```bash
git mv ui/src/components/KanbanColumn.tsx ui/src/components/kanban/KanbanColumn.tsx
git mv ui/src/components/KanbanColumn.test.tsx ui/src/components/kanban/KanbanColumn.test.tsx
```

- [ ] **Step 2: Update imports** — find/replace `from '../KanbanColumn'` → `from './kanban/KanbanColumn'` etc.

- [ ] **Step 3: Refactor JSX/CSS** — replace inline styles with Tailwind. Add corner brackets via pseudo-elements. **Onde colocar as regras decorativas:** em `index.css` (com classe utilitária `.cipher-col`), **não** em `tokens.css` (esse arquivo é apenas CSS custom properties). Alternativa: usar Tailwind arbitrary variants `before:content-['']` direto no JSX se a regra for curta.

- [ ] **Step 4: Run existing tests, verify pass**.

```bash
cd ui && pnpm test KanbanColumn
```
Expected: all existing tests pass.

- [ ] **Step 5: Commit**.

---

### Task 7.2: Kanban refactor

Same pattern. `git mv` to `kanban/Kanban.tsx`, refactor JSX/CSS, preserve dnd-kit logic and props contract.

- [ ] **Steps 1-5** as 7.1.

---

## Phase 8 — TaskCard refactor + 8 states

### Task 8.1: TaskCard state derivation logic

**Files:**
- Create: `ui/src/components/kanban/taskCardState.ts`
- Test: `ui/src/components/kanban/taskCardState.test.ts`

**Behavior:** pure function `deriveCardState(task, runStatus) → { kind: 'idle'|'running'|'awaiting'|'error'|'done', meta?: string }`. Encapsula a regra "awaiting beats running", "done = task.state === 'done'", etc.

- [ ] **Step 1: Write failing tests** — 8 cases (idle / running / awaiting / error / done / hover / dragging / multi).

- [ ] **Step 2: Implement** — switch on `task.state` and session status. Hover/dragging are UI states, not data-derived; deriva apenas o data-driven (idle/running/awaiting/error/done).

- [ ] **Step 3: Commit**.

---

### Task 8.2: TaskCard JSX refactor

**Files:**
- Move: `ui/src/components/TaskCard.tsx` → `ui/src/components/kanban/TaskCard.tsx`
- Test: existing `TaskCard.test.tsx` (preserved)

**Behavior:** preserve props + DOM attrs the tests assert (e.g., `data-template-name`, `data-permission-profile`, `data-testid="template-badge"`). Mudam visuals: corner brackets + ID hex + chip styles + states.

- [ ] **Step 1: Move file + update imports**.

- [ ] **Step 2: Refactor JSX** — see spec §6.4 anatomy. Add hex prefix (`task.id.replace(/-/g,'').slice(0,4)`). Apply state via `cn()` + `deriveCardState`.

- [ ] **Step 3: Run TaskCard tests, verify pass.**

- [ ] **Step 4: Commit**.

---

### Task 8.3: TaskCard live-state polish (awaiting/running/error glow)

**Files:**
- Modify: `ui/src/components/kanban/TaskCard.tsx`
- Test: `ui/src/components/kanban/TaskCard.test.tsx` — add visual state assertions

**Behavior:** add data-attrs `data-card-state="idle|running|awaiting|error|done"` so tests can assert. Style via Tailwind variants on the data-attr.

- [ ] **Step 1: Write new tests** — `expect(card).toHaveAttribute('data-card-state', 'awaiting')` for an awaiting task.

- [ ] **Step 2: Implement** — wire `deriveCardState` output to data-attr + className.

- [ ] **Step 3: Verify pass + commit**.

---

## Phase 9 — TaskDetailSheet (substitui TaskDetailModal)

### Task 9.1: TaskDetailSheet shell (with shadcn Sheet + tabs)

**Files:**
- Create: `ui/src/components/task-detail/TaskDetailSheet.tsx`
- Test: `ui/src/components/task-detail/TaskDetailSheet.test.tsx`

- [ ] **Step 1: Failing test** — open=true renders Sheet, displays task title, has 4 tabs (Overview/Sessions/Run/Logs), ESC fires onClose.

- [ ] **Step 2: Implement** com shadcn `<Sheet side="right">` + `<Tabs>`.

- [ ] **Step 3: Commit**.

---

### Task 9.2: OverviewTab

`ui/src/components/task-detail/OverviewTab.tsx` — task.state, ago, branch, permission_profile, template, cwd, last activity. Reuse same data shapes the existing TaskDetailModal uses.

- [ ] **Steps 1-3**: test + impl + commit.

---

### Task 9.3: SessionsTab

Lista sessions da task (via existing endpoint `/api/tasks/:id/sessions`). Each item: pid + status + started_at + transcript link.

- [ ] **Steps 1-3**.

---

### Task 9.4: RunTab migration

Move `ui/src/components/RunTab.tsx` → `ui/src/components/task-detail/RunTab.tsx`. Adjust for narrower width (380-420px). Tests preserved.

- [ ] **Steps 1-4**: `git mv` + visual refactor + verify tests + commit.

---

### Task 9.5: LogsTab

New component — stream consolidado de logs via SSE existente. Display tail última 100 linhas with auto-scroll toggle.

- [ ] **Steps 1-3**.

---

### Task 9.6: Replace TaskDetailModal usage

**Files:**
- Modify: `ui/src/App.tsx` — replace `<TaskDetailModal>` import + usage with `<TaskDetailSheet>`.
- Delete: `ui/src/components/TaskDetailModal.tsx`
- Delete: `ui/src/components/TaskDetailModal.test.tsx` (migrated content to TaskDetailSheet.test.tsx)

- [ ] **Step 1: Verify TaskDetailSheet.test.tsx covers all behaviors from old test** (read both files).

- [ ] **Step 2: Replace usage in App.tsx**.

- [ ] **Step 3: Run all UI tests + verify pass**.

```bash
cd ui && pnpm test
```
Expected: all pass (251 → 251+ tests, none regressed).

- [ ] **Step 4: Delete old files**.

```bash
git rm ui/src/components/TaskDetailModal.tsx ui/src/components/TaskDetailModal.test.tsx
```

- [ ] **Step 5: Commit**.

```bash
git commit -m "refactor(F9.9): TaskDetailModal → TaskDetailSheet (shadcn Sheet right + tabs)"
```

---

## Phase 10 — MasterSidebar refactor

### Task 10.1: MasterHeader component

**Files:**
- Create: `ui/src/components/master/MasterHeader.tsx`
- Test: `ui/src/components/master/MasterHeader.test.tsx`

**Behavior:** title `master_001` + dot (connected/disconnected/error) + 4 action buttons (clear/copy id/restart/min) + meta line `claude --resume master_001 · 80×24 · pid {n}`.

- [ ] **Steps 1-3**.

---

### Task 10.2: QuickCommands strip

**Files:**
- Create: `ui/src/components/master/QuickCommands.tsx`
- Test: `ui/src/components/master/QuickCommands.test.tsx`

**Behavior:** 5 chips (list tasks / create task / update state / discard / show doing). Click injects command into PTY via `onInject(command: string)` prop. Component is dumb — App wires PTY connection.

- [ ] **Steps 1-3**.

---

### Task 10.3: MasterFooter

**Files:**
- Create: `ui/src/components/master/MasterFooter.tsx`
- Test: `ui/src/components/master/MasterFooter.test.tsx`

**Behavior:** displays `pty 80x24 · pid {n} · ● live · {rtt}ms`. RTT from prop.

- [ ] **Steps 1-3**.

---

### Task 10.4: MasterSidebar refactor (preserve xterm/WS)

**Files:**
- Modify: `ui/src/components/MasterSidebar.tsx` → move to `ui/src/components/master/MasterSidebar.tsx`
- Test: `ui/src/components/master/MasterSidebar.test.tsx`

**Behavior:** preserves the entire xterm.js + WebSocket logic from current file (PTY input/output/resize, system messages handling). Adds:
- Wraps children with new MasterHeader (top) + QuickCommands (below header) + MasterFooter (bottom).
- Uses `useWebSocketRTT(ws)` to pass RTT to MasterFooter.
- Empty states: cold start (no MasterSession), disconnected, fatal error — switch based on a state machine: `idle | connecting | connected | disconnected | error`.
- xterm.js theme update: `background: #030503`, `foreground: #d4e4d0`, `cursor: #ff10f0`.

- [ ] **Step 1: Failing test** — render in disconnected state shows "WebSocket caiu" empty state. Render in connected state shows xterm.

- [ ] **Step 2: Implement** — preserve all current behavior, restructure JSX. Use existing tests in `MasterSidebar.test.tsx` as baseline.

- [ ] **Step 3: Run all master tests, verify pass.**

- [ ] **Step 4: Commit**.

---

## Phase 11 — NewTask flows (inline + sheet)

### Task 11.1: NewTaskInline component

**Files:**
- Create: `ui/src/components/kanban/NewTaskInline.tsx`
- Test: `ui/src/components/kanban/NewTaskInline.test.tsx`

**Behavior:** click on `+ Add task` button in column footer expands inline form (title input only). Enter creates with `state` = column state, `template` = `default` (yolo profile). Mutation via existing `api.createTask`.

- [ ] **Steps 1-3**: test (renders form on click, Enter submits, ESC cancels), implement, commit.

---

### Task 11.2: NewTaskSheet (refactor of NewTaskForm)

**Files:**
- `git mv ui/src/components/NewTaskForm.tsx → ui/src/components/drawers/NewTaskSheet.tsx`
- Update test file path + imports.
- Modify: `ui/src/App.tsx` to use NewTaskSheet (opened by header `[N]` button) instead of inline form.

**Behavior:** entire form (title/state/template/profile/branch/project) inside shadcn Sheet (side=right). Reuses all existing mutation logic.

- [ ] **Step 1: Move + rename + update imports**.
- [ ] **Step 2: Wrap in `<Sheet>` + restyle with Tailwind**.
- [ ] **Step 3: Wire from AppHeader `onNewTask` prop.**
- [ ] **Step 4: Run existing NewTaskForm tests (renamed) verify pass + add Sheet open/close test**.
- [ ] **Step 5: Commit**.

---

## Phase 12 — ProjectsDrawer + BootstrapModal migration

### Task 12.1: ProjectsDrawer → shadcn Sheet (left)

`git mv ui/src/components/ProjectsDrawer.tsx → ui/src/components/drawers/ProjectsDrawer.tsx`. Migrate from existing drawer to shadcn `<Sheet side="left">`. Preserve content (projects tree, worktrees, orphans). Restyle.

- [ ] **Steps 1-4**: move, rewrite shell, verify tests pass, commit.

---

### Task 12.2: BootstrapModal → shadcn Dialog

`git mv ui/src/components/BootstrapModal.tsx → ui/src/components/dialogs/BootstrapModal.tsx`. Migrate from existing modal to shadcn `<Dialog>`. Preserve content (file watcher status, manifest explanation).

- [ ] **Steps 1-4**.

---

## Phase 13 — Empty / loading / error states

### Task 13.1: Empty state for kanban (no tasks)

**Files:**
- Modify: `ui/src/components/kanban/Kanban.tsx`
- Test: `ui/src/components/kanban/Kanban.test.tsx` (add empty case)

**Behavior:** when `tasks.length === 0`, render centered ASCII illustration `[no tasks yet]` + corner brackets + CTA "+ New task".

- [ ] **Steps 1-3**.

---

### Task 13.2: Skeleton loading states

**Files:**
- Create: `ui/src/components/kanban/TaskCardSkeleton.tsx`
- Modify: `Kanban.tsx` (render skeletons while `isLoading`)
- Test: skeleton component shows when loading.

- [ ] **Steps 1-3**.

---

### Task 13.3: Error banner + offline indicator

**Files:**
- Create: `ui/src/components/status/ErrorBanner.tsx`
- Modify: `ui/src/app/AppShell.tsx` (render banner below HUD when API offline)
- Modify: `StatusBar.tsx` (state segment turns magenta when offline)

- [ ] **Steps 1-3**.

---

## Phase 14 — Palette refinement (user-requested follow-up)

### Task 14.1: Calibrate palette tones (less green-dominance)

**Files:**
- Modify: `ui/src/lib/tokens.css`

**Behavior:** ajustar valores `--*` em `tokens.css` testando in-context com `make dev`. Heurística:
- Adicionar 1-2 cinzas-quentes neutros (`--text-neutral: #98a195`?) pra texto secundário não-emphasis.
- Suavizar saturação dos `--bg-*` (menos `green-tinge`, mais neutro escuro).
- Magenta `--accent-attn` mantém como spot color — uso disciplinado só em `awaiting`.

- [ ] **Step 1: Make dev server up**.

```bash
make dev
```

- [ ] **Step 2: Iterate paleta** — abrir várias telas (kanban com tasks, sheet aberto, master cold-start, error state) e ajustar `tokens.css` até bater no que o usuário definir como "less green".

- [ ] **Step 3: Verify all tests still pass**.

```bash
make test-all
```

- [ ] **Step 4: Commit**.

```bash
git commit -am "feat(F9.14): refine CIPHER palette tones (less green-dominance, neutral grays)"
```

---

### Task 14.2: Verify visual quality screenshots

**Files:**
- Create: `docs/screenshots/F9-redesign/` com PNGs das principais telas.

- [ ] **Step 1: Tirar screenshots manuais** (or via Playwright snapshot test) das telas:
  - Empty kanban
  - Kanban com 5 cards estados diferentes
  - TaskDetailSheet aberto em Overview tab
  - Master cold start
  - Master connected ativo
  - HUD + StatusBar em sync

- [ ] **Step 2: Commit screenshots pra referência**.

---

## Phase 15 — Polish

### Task 15.1: Animations + transitions

**Files:**
- Modify: relevant Tailwind classes ou `tokens.css` `@keyframes`.

**Behavior:** adicionar transições suaves (180ms ease) em:
- Card hover (border + bg)
- Sheet open/close (shadcn já fornece)
- StatusSeg tone transition
- ProjectsDrawer slide

- [ ] **Steps**: review each component, add transitions, verify no test regression.

---

### Task 15.2: Focus rings + a11y verification

**Files:**
- Modify: `tokens.css` + `index.css`.

**Behavior:** adicionar focus rings visíveis com `--accent-primary` em todos os interactive elements (Button, Input, Sheet trigger, etc — shadcn provides defaults, tune to fit CIPHER).

- [ ] **Steps**: review keyboard navigation by tabbing through app, fix focus order, commit.

---

### Task 15.3: Final smoke test + screenshot

**Files:** none.

- [ ] **Step 1: Full test suite**.

```bash
make test-all
```
Expected: all backend + UI tests pass. Coverage gates met.

- [ ] **Step 2: Visual smoke** — `make dev`, navigate through all flows manually:
  - Create task inline
  - Create task via Sheet
  - Open task detail Sheet (all 4 tabs)
  - Drag card between columns
  - Open ProjectsDrawer
  - Trigger BootstrapModal
  - Master Session: type, see RTT updating, restart, clear
  - HUD metrics updating
  - StatusBar reflects state

- [ ] **Step 3: Document any open issues** in `docs/F9-redesign-followups.md`.

- [ ] **Step 4: Final commit**.

```bash
git commit -am "feat(F9): UI redesign — CIPHER identity, Tailwind v4 + shadcn, complete"
```

- [ ] **Step 5: Update ARCHITECTURE.md §11 roadmap** with F9 ✅ entry.

- [ ] **Step 6: Update CHANGELOG.md** with F9 entry.

- [ ] **Step 7: Create ADRs 0023-0024-0025** per spec §11.

---

## Open follow-ups (post-merge)

- [ ] Filter input logic (header `/` shortcut) — currently stub.
- [ ] RunPanel implementation (header `[R]`) — currently no-op.
- [ ] Command palette (cmdk) on `Ctrl+K`.
- [ ] Kanban keyboard navigation (J/K + Enter).
- [ ] Bug F8 master session — separate spec.

---

## Coverage gates (must hold)

- Backend (Python): 100% statement coverage maintained.
- UI (Vitest): 100% statement coverage on `src/lib/`, `src/hooks/`, `src/stores/`. Component tests preserve all `data-testid` and behavioral assertions from prior tests.
- E2E (Playwright host-only): all 9 skeletons continue to pass (none should break — only visual).

If a test breaks during refactor, investigate root cause (visual change vs behavioral change). Do NOT skip or soften assertions; fix the component to satisfy the contract.

---

## Skill references

- @superpowers:test-driven-development — every task uses TDD.
- @superpowers:verification-before-completion — verify before claiming task done.
- @superpowers:systematic-debugging — when a test breaks unexpectedly.
- @superpowers:subagent-driven-development — execution mode (recommended).
