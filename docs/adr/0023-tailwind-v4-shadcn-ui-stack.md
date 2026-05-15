# ADR-0023: Tailwind v4 + shadcn/ui (Radix) como design system

**Status:** Accepted — 2026-05-12
**Decisores:** marcosdid + Claude
**Contexto:** F9 (UI redesign pós-MVP)

## Contexto

A UI MVP (F0→F8) usava CSS vanilla — ~140 LOC em `index.css` com classes ad-hoc (`.kanban-column`, `.task-card`, `.template-badge`, `.profile-yellow`). Acumulou três dores:

1. **Sem disciplina**: cada componente inventou cores e espaçamentos próprios; nada cruzava o threshold pra virar token.
2. **Sem primitives**: `TaskDetailModal` reimplementou backdrop+focus-trap+ESC-to-close à mão; `ProjectsDrawer` reimplementou slide-in à mão; ambos com bugs de a11y e UX inconsistentes.
3. **Sem velocity**: cada feature nova exigia decisões de baixo nível (padding, border-radius, focus ring). Trabalho de "design" comia tempo de feature.

Pra F9 (operator UI legível, com identidade visual coerente), precisava de:
- Sistema de tokens (cores, espaçamento, tipografia) com refresh-de-paleta cheap.
- Primitives de UI testados (Sheet, Dialog, Tabs, Tooltip) com a11y de fábrica.
- Utility classes pra evitar 1 arquivo CSS gigante.

## Decisão

**Tailwind v4 + shadcn/ui sobre primitives Radix UI.**

- **Tailwind v4** (`@tailwindcss/vite`): CSS-first, JIT compilation, suporte a arbitrary values. Configurado via `@config "../tailwind.config.ts";` directive em `ui/src/index.css` (auto-discovery de JS config foi removido em v4).
- **shadcn/ui**: copia-cola de componentes em `ui/src/components/ui/`. Versionado no repo, customizável. Não é dependência runtime — é código nosso.
- **Radix UI** como base de cada primitive (Dialog/Sheet/Tabs/etc.): a11y + keyboard nav + focus management de fábrica.
- **Tokens em CSS variables** (`ui/src/lib/tokens.css`) mapeados pra theme do Tailwind: refresh de paleta = 1 arquivo, não rewrite de componentes.

Alternativas descartadas:
- **CSS Modules**: resolve naming mas não resolve primitives nem tokens.
- **MUI / Chakra**: design system pronto, mas opinião forte demais — não casa com CIPHER (cyberpunk operator, dark-only).
- **Headless UI + custom CSS**: a11y boa, mas falta a malha de utility classes pra evitar CSS gigante.

## Consequências

**Positivas:**
- Velocity de UI subiu — componentes ficam pequenos (~20-80 LOC) e focados.
- A11y "de graça" — Radix tem ARIA + keyboard nav corretos por padrão.
- Tokens centralizados — paleta refresh é 1 arquivo (`tokens.css`).
- 100% test coverage continua viável (hooks/stores em `src/lib`, `src/hooks`, `src/stores`).

**Negativas:**
- Bundle CSS cresceu de ~6kB pra ~32kB (cobertura de utility classes + animations + scanlines + 7 weights de JetBrains Mono em latin subset). Aceitável pro use case (local-dev tool, não SSR).
- shadcn-generated files às vezes falham com `exactOptionalPropertyTypes: true` — precisam de patch manual (`?? false`, `?? "system"`). Re-run de `pnpx shadcn add` re-introduz o problema. Documentado no commit `fix(F9.0): wire tw-animate-css plugin + clean up shadcn install side effects`.
- `bg-bg-void` / `text-text-emphasis` / `border-border-subtle` — namespace echo (nested config no `tailwind.config.ts`). Funcional mas verbose. Suggestion pra flatten em fase futura.

**Operacionais:**
- Tailwind v4 não auto-discovers JS config. Sempre usar `@config "../tailwind.config.ts";` no `index.css`.
- `tw-animate-css` é CSS-only (sem JS entry) — usar `@import "tw-animate-css";`, não `@plugin`.
- shadcn CLI deve ficar em `devDependencies` — `pnpx shadcn add` move pra `dependencies` por padrão; corrigir manualmente.
