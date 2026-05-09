# ADR-0003: Stack da UI — Vite 6 + React 19 + TanStack Query + Zustand

- **Status:** Accepted
- **Data:** 2026-05-08
- **Decisores:** Marcos

## Contexto

UI single-user rodando no browser local, consumindo REST + WebSocket
do daemon. Vai ter componentes com bastante estado de cache remoto
(tasks, sessões, aprovações em fila, etc.) e estado local de UI
(modais, seleção, drag-and-drop futuro).

A camada de dados precisa: invalidar/refetch eficientemente, integrar
com WebSocket pra eventos push, e ser fácil de testar em E2E.

## Decisão

- **Build/dev:** Vite 6.
- **Framework:** React 19.
- **Linguagem:** TypeScript estrito (`exactOptionalPropertyTypes`,
  `noUncheckedIndexedAccess`, etc.).
- **Cache de dados remotos:** TanStack Query 5 — invalidação fina,
  integração natural com eventos WS, defaults sensatos.
- **Estado local de UI:** Zustand — leve, sem provider hell, fácil de
  testar.
- **Testes unitários:** Vitest 3 + React Testing Library + jsdom.

## Alternativas consideradas

1. **SWR + Context API.** Leve, mas Context tem armadilhas de
   re-render e API menos rica para sync com WebSocket.
2. **fetch + useState/useReducer puros.** Sem libs. Garante controle
   total e cobertura trivial em testes, mas custa muito boilerplate
   pra cada query/mutation.
3. **Vitest 2.** Considerado, mas traz tipos do Vite 5 e quebra com
   Vite 6 (`'test' does not exist in type 'UserConfigExport'`).
   Vitest 3 é necessário.

## Consequências

**Positivas**
- TanStack Query reduz "estado remoto" a uma chave + função — testes
  E2E ficam previsíveis porque o cache invalida deterministicamente.
- Zustand não exige boilerplate de provider — stores são módulos
  exportados.
- Vite 6 + TypeScript estrito + React 19 dão bom suporte de tooling
  atual.

**Negativas**
- Duas libs de estado em vez de uma. Limite mental: cache remoto vai
  pra TanStack Query; **somente** estado de UI local vai pra Zustand.
- Vite 6 é recente; ecossistema pode ter quirks (já vimos um:
  pnpm 11 + esbuild approve-builds no Docker, ver `gotchas.md`).

**Neutras**
- Cobertura 100% só em `src/lib/` e `src/hooks/`; componentes de
  apresentação puros são cobertos pelo E2E (ver ADR-0004).

## Referências

- `ARCHITECTURE.md` §13
- `ui/package.json`, `ui/vite.config.ts`
- `gotchas.md` §3
