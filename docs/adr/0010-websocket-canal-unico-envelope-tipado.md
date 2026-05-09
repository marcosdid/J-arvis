# ADR-0010: WebSocket único em `/ws` com envelope tipado

- **Status:** Accepted
- **Data:** 2026-05-09
- **Decisores:** Marcos

## Contexto

F2 precisa publicar eventos de status do daemon pra UI em tempo real.
F3 vai adicionar `approval.created/decided`, F4 `task.updated`, F6 logs
do Run from Panel. A arquitetura inicial (§4) menciona "WebSocket único,
broadcast de eventos" mas não fixa o formato.

Quatro abordagens consideradas:

1. **Canal único `/ws` com envelope tipado** — todos os eventos passam
   por um socket; UI filtra por `type`.
2. **Canal por recurso** — `/ws/sessions`, `/ws/approvals`, `/ws/tasks`.
   Cada componente assina o que precisa.
3. **Canal por sessão + global** — `/ws` global pra eventos cross-recurso
   + `/ws/sessions/<id>` pra detalhes (transcript stream em F8).
4. **Server-Sent Events em vez de WS** — `text/event-stream`,
   reconnect automático nativo, mais simples.

## Decisão

Adotamos a alternativa **1**: WebSocket único em `/ws`, sem auth
(local-only single-user, ADR-0001), com envelope tipado:

```ts
type WsEvent =
  | { type: "session.status";   session_id: string; payload: { status: string; previous: string }; at: string }
  | { type: "session.tool_use"; session_id: string; payload: { tool: string };                     at: string }
  | { type: "session.stopped";  session_id: string; payload: {};                                   at: string };
```

Cliente filtra por `type` (TanStack Query invalida queries específicas).
`at` é ISO-8601 UTC. Sem retry/buffer no servidor: clientes que perdem
evento revalidam via `invalidateQueries` no reconnect.

Backend usa `InMemoryWsBroadcaster` (`set[WebSocket]` + `asyncio.gather`
com `return_exceptions=True`; clientes que falham `send_json` são
descartados).

Frontend usa `connectWs` com reconnect+backoff exponencial (1s → 30s),
e `dispatch` discriminated union pra type-safety.

## Alternativas consideradas

1. **Canais por recurso** (`/ws/sessions`, etc.): rejeitada — gasta
   connection slots em browsers (limite ~6 por origem); duplicaria
   código de keepalive/reconnect; acoplaria URL ao modelo de domínio
   (toda nova fase precisaria de novo endpoint).
2. **Canal por sessão + global**: rejeitada pra MVP — over-engineering;
   payoff só aparece em F8 (stream de transcript), e mesmo lá pode ser
   resolvido com filtro por `session_id` no envelope global.
3. **SSE em vez de WS**: rejeitada — contradiz ARCHITECTURE.md §4 que
   já fixou WebSocket; sem ganho técnico significativo (SSE simplifica
   reconnect mas isso é trivial em ws.ts custom). Se um dia precisarmos
   bidirectional (ex: cliente confirmar recebimento), WS já está pronto.

## Consequências

**Positivas**

- F3/F4/F6 adicionam novos `type`s sem multiplicar canais nem mudar
  contrato.
- Cliente revalida queries seletivamente por tipo — UI estado fresco
  sem reload manual.
- Reconnect simples (cliente faz, servidor não rastreia).
- Sem state no servidor além do `set[WebSocket]` em memória.

**Negativas**

- Sem replay no servidor: se o cliente perdeu eventos durante
  reconnect, depende de `queryClient.invalidateQueries(...)` pra puxar
  estado fresco. Aceitável pra status (idempotente); pode virar dor
  pra logs (F6) — endereçaremos quando F6 chegar.
- Sem auth: aceitável só porque o daemon é local-only. Se um dia
  J-arvis virar multi-user, ADR-0010 vira obsoleto e supersede.

**Neutras**

- TanStack Query já estava no stack (ADR-0003) — `invalidateQueries`
  encaixa naturalmente; nenhum novo client de cache.
- Envelope tipado em TS via discriminated union: type-safety no
  cliente sem custo de runtime.

## Referências

- Spec: `docs/superpowers/specs/2026-05-09-f2-hooks-status-semantico-design.md` §4.2
- ADR-0001 (single-user / local-only)
- ADR-0003 (TanStack Query no stack UI)
