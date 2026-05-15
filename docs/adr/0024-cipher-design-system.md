# ADR-0024: CIPHER v2 — operator cyberpunk design identity

**Status:** Accepted — 2026-05-12 (paleta sujeita a refinamento Phase 14)
**Decisores:** marcosdid + Claude
**Contexto:** F9 (UI redesign pós-MVP)

## Contexto

A UI MVP não tinha identidade visual — era CSS funcional mas anônimo. Pra F9 o objetivo era dar ao J-arvis uma cara que comunique seu propósito: **ferramenta de operador** (não consumer app, não dashboard genérico), com **leitura técnica imediata** (densidade alta, mono dominante, métricas live no topo).

Durante brainstorming foi explorado 3 identidades visuais (visual companion com mockups HTML). O usuário escolheu "CIPHER" e pediu pra ficar **mais cyberpunk** que o protótipo inicial.

## Decisão

**CIPHER v2** — operator cyberpunk autêntico:

### Paleta

- **Dark-only** (sem light mode). UI sempre escura, operator-friendly.
- **Verde matrix** (`#4ade80`) como accent primário — usado em CPU/MEM/RTT/uptime metrics, brand `j-arvis`, button outlines, focus rings.
- **Magenta hot** (`#ff10f0`) como **spot color** disciplinado — usado APENAS em `tone='hot'` (alertas > 0) e cursor piscante. Comunica atenção.
- **Background scale**: 5 tons void→muted (`#030503` → `#0a0d0a`), todos green-tinted.
- **Border scale**: 3 tons subtle/mid/strong + `#4ade80` pra elementos vivos.
- **Text scale**: 5 tons faint/subtle/body/emphasis/title (de `#3a4a3a` a `#d4e4d0`).
- **Semantic colors**: error vermelho (`#f87171`), warn âmbar (`#fbbf24`), info ciano (`#00d4ff`), refactor purple (`#c084fc`), review violet (`#a855f7`).

### Tipografia

- **JetBrains Mono** dominante (400/500/600/700/800, latin subset apenas).
- **Space Grotesk** (600/700) pra HUD labels/títulos de seção (display font).
- `font-feature-settings: 'tnum'` no body pra tabular numerals — métricas não tremem ao atualizar.

### Decorações

- **Scanlines overlay** global via `body::before` com `repeating-linear-gradient` (verde 4% opacity, z-index 1 — abaixo de Radix portals em z-50).
- **Corner brackets** em cards/columns via pseudo-elements (planejado; minimalist no MVP).
- **HUD top bar** com badge `OPER` piscante (`@keyframes cipher-blink`) + título `J-ARVIS // OP_CTRL` em Space Grotesk tracking-wide.
- **Brand cursor** magenta piscante (`after:animate-[cipher-blink_1s_steps(1)_infinite]`).

### Layout

- 2-pane: kanban main (1fr) + master sidebar (400px right).
- 5-column kanban clássico (idea / ready / in_progress / review / done).
- Sheet right pra TaskDetail (substitui modal); Sheet left pra Projects (substitui custom drawer); Dialog pra Bootstrap.

### Estados de TaskCard (8)

`idle | hover | running | awaiting | error | done | dragging | multi`. Os 5 estados data-driven (`idle/running/awaiting/error/done`) são derivados pelo pure helper `deriveCardState(task, runStatus)`. Visuais aplicados via `data-[card-state=...]:...` Tailwind variants:
- `awaiting`: border magenta + glow magenta (chama atenção).
- `running`: border verde.
- `error`: border vermelho + bg vermelho leve.
- `done`: opacity 60%.

## Consequências

**Positivas:**
- UI tem cara — é reconhecivelmente "J-arvis" e não confundível com outro dashboard.
- Disciplina visual: magenta SÓ em alertas evita poluição. Operator vê o que importa.
- Densidade técnica alta — tabular nums + mono dominante = scan rápido de métricas.
- Acessibilidade preservada (focus rings via `--ring`, ARIA via Radix).

**Negativas (assumidas):**
- Paleta atual está **green-dominante** demais. Phase 14 (deferido) deve adicionar cinzas-quentes neutros pra texto secundário e suavizar saturação dos backgrounds.
- `--text-faint` (`#3a4a3a`) e `--text-body` (`#6a7a6a`) ficam abaixo do WCAG AA pra body text contra `--bg-void`. Aceitável pra timestamps decorativos (faint by design), mas body precisa subir 1 step na Phase 14.
- Dark-only — sem light mode. Não é problema pro use case (ferramenta de dev, 99% dark) mas é uma escolha que limita.

**Operacionais:**
- Refinamento de paleta = editar `ui/src/lib/tokens.css`. Nenhum componente precisa mudar.
- Adicionar nova cor semantic = adicionar var no `tokens.css` + entrada no `tailwind.config.ts` `colors.sem.*`.
