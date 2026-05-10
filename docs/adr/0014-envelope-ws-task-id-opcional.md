# ADR-0014: Envelope WS com `task_id` opcional (emenda aditiva ao ADR-0010)

- **Status:** Accepted
- **Data:** 2026-05-09
- **Decisores:** Marcos

## Contexto

F4 introduz eventos WS de Task (`task.created`, `task.updated`).
ADR-0010 fixou o envelope `{type, session_id, payload, at}` em F2.
Eventos de task não têm `session_id` natural, e a UI precisa
identificar qual Task atualizar quando recebe `session.status`.

## Decisão

Adiciona campo top-level **opcional** `task_id: str | None = None`
ao `WsEvent`. Backward-compatible:

- Eventos F2 (`session.status`/`tool_use`/`stopped`) ganham
  `task_id` preenchido a partir de `ClaudeSession.task_id`.
- Eventos F4 (`task.*`) preenchem `task_id` e deixam `session_id=""`.

Discriminador continua sendo `type`.

## Alternativas consideradas

1. **Top-level genérico `entity_id`** (rejeitada): quebra contrato F2.
2. **`session_id=""` sentinela sem `task_id`** (rejeitada): UI precisa
   manter mapa session_id → task_id próprio; smell.
3. **Canal WS separado pra tasks** (`/ws/tasks`): contradiz ADR-0010.

## Consequências

**Positivas**
- UI invalida `tasks` cache via `task_id` em qualquer evento.
- ADR-0010 contracts intactos; campo opcional novo é aditivo puro.

**Negativas**
- ~10 bytes extras por evento. Aceitável.

## Referências

- ADR-0010
- Spec F4 §4.2
