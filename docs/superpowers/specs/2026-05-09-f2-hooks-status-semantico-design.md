# F2 — Status semântico via hooks (design spec)

- **Data:** 2026-05-09
- **Fase do roadmap:** F2 (`ARCHITECTURE.md` §11)
- **Pré-requisito:** F1 concluído (commits `253739b` … `272d54a`)
- **Decisões novas:** ADR-0009 (registro de hooks via `.ai-jail`), ADR-0010 (formato dos eventos no WebSocket)

## 1. Objetivo

Quando o usuário tem várias sessões Claude Code rodando, ele precisa saber em **tempo real** em qual estado cada uma está sem entrar na janela do terminal. F2 adiciona isso:

- 3 endpoints HTTP recebem hooks do Claude Code dentro da jaula.
- Daemon traduz cada hook em mudança semântica de `ClaudeSession.status`.
- WebSocket broadcasta a mudança pra UI.
- `notify-send` dispara notificação nativa do Ubuntu nas transições importantes.

Demo de aceitação: sessão é spawned → usuário simula Claude pedindo input via curl manual no container → card da UI muda pra "Aguardando você" sem reload + balão `notify-send` aparece no desktop.

## 2. Decisões fechadas

| # | Decisão | Escolha | Justificativa |
|---|---|---|---|
| 1 | Registro de hooks (ADR-0009) | Daemon escreve `.claude/settings.json` **dentro da jaula** ai-jail | Sandbox-clean: zero pegada em `~/.claude` do usuário; não vaza pra Claude Code rodando fora do J-arvis |
| 2 | Correlação hook→sessão | Token UUID por sessão na URL: `/api/hooks/<event>/<token>` | Imune a colisão (mesma worktree pode ter várias sessões); sem auth global |
| 3 | Topologia WS (ADR-0010) | Canal único `/ws` com envelope tipado `{type, session_id, payload, at}` | Escala pra F3/F4/F6 sem multiplicar canais; UI filtra por `type` |
| 4 | `PreToolUse` em F2 | Só registra audit, não muta status, não bloqueia | Bloqueio + fila ficam pra F3; F2 fica observation-only |
| 5 | `notify-send` | Só em transições `* → AWAITING_RESPONSE` e `* → IDLE`. Configurável via `JARVIS_NOTIFY=on\|off` | Não spame; foco no que precisa de atenção humana |
| 6 | Status em F2 | F2 só usa `EXECUTING`, `AWAITING_RESPONSE`, `IDLE`, `DONE`, `ERROR`. `AWAITING_APPROVAL` reservado pra F3 | Evita prometer mais do que entrega |
| 7 | Token registry | In-memory é source-of-truth em runtime; DB column é só audit/diagnóstico. Daemon é on-demand (`ARCHITECTURE.md` §1.4) — restart mata sessões; não há rebuild do registry a partir do DB | Simplicidade; nenhum cenário válido de "sessão sobrevive ao restart do daemon" no MVP |
| 8 | Path do `settings.json` no jail | Daemon escreve em `<jail_workdir>/.claude/settings.json` **antes** de invocar `ai-jail run`. `<jail_workdir>` é o mesmo path da worktree que o ai-jail bind-monta (mesmo path absoluto dentro/fora). Caminho é parte do contrato `AiJailRuntime.spawn()` — explicitado nos testes | Sem mistério: Claude Code dentro da jaula lê settings.json do `cwd/.claude/`, que é a worktree montada |
| 9 | `JARVIS_HOOK_BASE_URL` | Default derivado de `JARVIS_PORT` (também novo): `http://localhost:${JARVIS_PORT}`. Se ambos forem custom, `JARVIS_HOOK_BASE_URL` ganha precedência | Evita que `8765` vire magic number; mantém um único ponto de configuração |

## 3. Arquitetura

### 3.1 Componentes (novos / modificados)

```
orchestrator/
├── hooks/
│   ├── router.py           NOVO  FastAPI router /api/hooks/<event>/<token>
│   ├── parser.py           NOVO  parse_notification, parse_pretooluse, parse_stop
│   ├── tokens.py           NOVO  generate_token() + TokenRegistry (memória)
│   └── audit.py            NOVO  PreToolUseEvent dataclass + repo append-only
├── events/
│   ├── envelope.py         NOVO  WsEvent dataclass + factories
│   └── broadcaster.py      NOVO  WsBroadcaster Protocol + InMemoryWsBroadcaster
├── notifications/
│   ├── sink.py             NOVO  NotifierSink Protocol + should_notify()
│   └── notify_send.py      NOVO  NotifySendNotifier (subprocess) + NoopNotifier
├── api/
│   └── ws.py               NOVO  GET /ws (WebSocket endpoint)
├── core/
│   └── sessions.py         EDITADO  novo update_status(db, sid, new) idempotente
├── sandbox/
│   └── aijail.py           EDITADO  spawn agora aceita token+base_url; escreve settings.json no jail
├── store/
│   └── models.py           EDITADO  ClaudeSession: + hook_token, + last_hook_at
├── alembic/versions/
│   └── 0002_hook_columns.py NOVO    migration aditiva
├── config.py               EDITADO  + JARVIS_NOTIFY, + JARVIS_HOOK_BASE_URL
└── main.py                 EDITADO  registra hooks_router + ws_router; injeta broadcaster + notifier
```

```
ui/src/
├── lib/
│   ├── ws.ts               NOVO  connectWs(onEvent) com reconnect+backoff
│   └── events.ts           NOVO  WsEvent type + dispatcher por tipo
├── hooks/
│   └── useSessionEvents.ts NOVO  invalida queryKeys.sessions ao receber session.status
└── App.tsx                 EDITADO  monta useSessionEvents
```

### 3.2 Acoplamento — abordagem direta

Decidida no brainstorming: hook handler chama 4 colaboradores explicitamente (parser → repo.update_status → broadcaster.publish → notifier.maybe_notify). Sem EventBus em memória, sem outbox no DB. Quando F3/F4 trouxerem novos eventos, refatoramos.

### 3.3 Fluxo

```
Claude Code (dentro da jaula)
  ↓ executa hook command (curl POST)
POST /api/hooks/<event>/<token>
  ↓
TokenRegistry.resolve(token) → session_id  (404 se não existir)
  ↓
parser.parse(payload) → SessionStatus | None  (422 se payload malformado)
  ↓
core.sessions.update_status(db, session_id, new_status)
  → row.status = new_status; row.last_hook_at = now(); commit
  → returns (previous_status, new_status)
  ↓ (se previous != new)
ws_broadcaster.publish(WsEvent.session_status(...))
notifier.maybe_notify(session_id, previous, new)
  ↓
return 204 (Notification/Stop) | 200 {"continue": true} (PreToolUse)
```

Tudo dentro de uma transação DB. Broadcaster e notifier rodam **após** commit; se broadcaster falhar, DB já está consistente. Erros do notifier são logados e ignorados.

## 4. Contratos

### 4.1 HTTP

| Método | Path | Body | Status | Resposta |
|---|---|---|---|---|
| POST | `/api/hooks/Notification/{token}` | Claude payload | `204` | (vazio) |
| POST | `/api/hooks/PreToolUse/{token}` | Claude payload | `200` | `{"continue": true}` |
| POST | `/api/hooks/Stop/{token}` | Claude payload | `204` | (vazio) |
| GET | `/ws` | — | `101` | upgrade WebSocket |

Erros:
- Token inválido / desconhecido / revogado → `404` sem body.
- Payload JSON malformado → `422 {"error": "invalid payload"}`.
- DB falha → `500`.

Nenhum endpoint loga payload completo (pode conter conteúdo de prompt). Loga `event_type`, `session_id`, status anterior/novo.

### 4.2 WebSocket — envelope

```ts
type WsEvent =
  | { type: "session.status";    session_id: string; payload: { status: string; previous: string }; at: string }
  | { type: "session.tool_use";  session_id: string; payload: { tool: string };                     at: string }
  | { type: "session.stopped";   session_id: string; payload: {};                                   at: string };
```

- `at`: ISO-8601 UTC (`datetime.now(UTC).isoformat()`).
- Sem auth no `/ws` — local-only single-user (ADR-0001 §3).
- Sem retry/buffer no servidor: clientes que perdem evento revalidam via `invalidateQueries` no reconnect.

### 4.3 Settings.json injetado na jaula

```jsonc
{
  "hooks": {
    "Notification": [
      { "matcher": "*", "hooks": [{ "type": "command",
          "command": "curl -sS -X POST '<BASE_URL>/api/hooks/Notification/<TOKEN>' --data-binary @-" }] }
    ],
    "PreToolUse": [
      { "matcher": "*", "hooks": [{ "type": "command",
          "command": "curl -sS -X POST '<BASE_URL>/api/hooks/PreToolUse/<TOKEN>' --data-binary @-; exit 0" }] }
    ],
    "Stop": [
      { "matcher": "*", "hooks": [{ "type": "command",
          "command": "curl -sS -X POST '<BASE_URL>/api/hooks/Stop/<TOKEN>' --data-binary @-" }] }
    ]
  }
}
```

`<TOKEN>` e `<BASE_URL>` são substituídos no momento do spawn. `<BASE_URL>` vem de `JARVIS_HOOK_BASE_URL` (default derivado de `JARVIS_PORT`). O `; exit 0` em `PreToolUse` garante que F2 nunca bloqueie o Claude.

A configuração `.ai-jail` precisa **permitir egress pra `localhost:<port>`**. Validação dessa flag específica do ai-jail é parte da fase de implementação; se não houver suporte, escala virou bloqueador (abrir ADR-0011).

**Path de escrita do `settings.json`:** daemon escreve `<worktree>/.claude/settings.json` **antes** de invocar `ai-jail run`. `ai-jail` bind-monta a worktree no mesmo path absoluto dentro da jaula (decisão do `ai-jail`), então o Claude Code dentro do jail lê `./` `/.claude/settings.json` a partir do `cwd`. O arquivo é **removido em `stop_session`** (ou quando o daemon detecta processo morto via `Process.poll()`); se o arquivo já existir antes do spawn (resíduo de crash anterior), é sobrescrito sem warning. Daemon adiciona `.claude/settings.json` em `<worktree>/.gitignore` na 1ª escrita (idempotente: append-only se a linha não existir).

## 5. Modelo de dados

```sql
ALTER TABLE sessions ADD COLUMN hook_token TEXT;
ALTER TABLE sessions ADD COLUMN last_hook_at TIMESTAMP;
CREATE UNIQUE INDEX ix_sessions_hook_token ON sessions(hook_token) WHERE hook_token IS NOT NULL;
```

- `hook_token`: UUID hex; `NULL` em sessões antigas e em sessões com `runtime=null` que não usam hooks; populado por `start_session` em runtime real. **DB é só audit/diagnóstico**: o registry em memória é o source-of-truth em runtime. Daemon on-demand (`ARCHITECTURE.md` §1.4) — restart mata sessões, então não rebuildamos o registry a partir do DB.
- `last_hook_at`: atualizado em **todo** hook recebido (mesmo `PreToolUse`, mesmo se status não muda). Sinal de "vivo" pra dashboard futuro.
- Migration `0002_hook_columns.py` aditiva — não quebra DB existente.

## 6. Status semantics

### Mapeamento

| Hook | Decisão F2 | Novo status |
|---|---|---|
| `Notification` (qualquer) | sempre | `AWAITING_RESPONSE` |
| `Stop` | sempre | `IDLE` |
| `PreToolUse` | só registra audit, não muta status | (status atual mantido) |

Nota: F2 trata todo `Notification` como `AWAITING_RESPONSE` pra não duplicar com F3. F3 vai refinar quando a fila de aprovações entrar; aí `AWAITING_APPROVAL` ganha vida.

### Máquina de estados (F2)

```
                start_session
                     │
                     ▼
                ┌──────────┐
                │EXECUTING │◄─────────────┐
                └──────────┘              │
                  │      │                │
        Notification│   │Stop             │
                  ▼      ▼                │
        AWAITING_RESPONSE   IDLE          │
                  │              │        │
                  └──────┬───────┘        │
                         │                │
                  (próximo hook)──────────┘

        stop_session (botão Stop UI)               → DONE
        Process.poll() detecta exit code 0         → DONE   (graceful, refina ADR-0008)
        Process.poll() detecta exit code != 0      → ERROR  (refina ADR-0008: ADR só fala "done")
        runtime.kill levanta exceção               → ERROR
        Hook chega mas DB já em DONE/ERROR         → no-op (no warning log)
```

### Regras

- `update_status` é idempotente: aplicar mesmo status → retorna `(prev, prev)` e **não** dispara WS event.
- Status terminal (`DONE`, `ERROR`) bloqueia transições por hook. Hook chegando pra sessão terminal → loga warning e retorna 204/200 sem mutar nada (race entre `Stop` do Claude e `stop_session` do botão).
- `last_hook_at` atualiza sempre, independente de mudança de status.

### Notify

| Transição | Notifica? | Conteúdo |
|---|---|---|
| `* → AWAITING_RESPONSE` | sim | title=`J-arvis`, summary=`<projeto> · <branch>`, body=`Aguarda você`, icon=`dialog-information` |
| `* → IDLE` | sim | summary=`<projeto> · <branch>`, body=`Concluído`, icon=`emblem-default` |
| qualquer outra | não | — |

Falha de `notify-send` (binário ausente, dbus indisponível): warning na 1ª vez por processo, depois silencia. Daemon não morre.

## 7. Concorrência

- Vários hooks pra mesma sessão concorrentes: SQLite serializa writes; **dentro de `update_status()`** chamamos `session.refresh(row)` antes de mutar `row.status`, pra evitar leitura stale quando a mesma `AsyncSession` é compartilhada. Documentamos no código a expectativa pra quando virarmos Postgres.
- Vários clientes WS conectados: `InMemoryWsBroadcaster` faz `asyncio.gather` em todos os `send_json`. Cliente que falha `send_json` é removido do set.

## 8. Plano de testes

### 8.1 Unit (`tests/unit/`)

- `test_hooks_parser.py`: 3 parsers + payload malformado.
- `test_token_registry.py`: register/resolve/revoke + idempotência.
- `test_session_update_status.py`: muta status + last_hook_at; idempotência; transição a partir de terminal é no-op.
- `test_ws_envelope.py`: factories produzem dict serializável; `at` ISO-8601 UTC.
- `test_notifier_sink.py`: `should_notify` cobre apenas `* → AWAITING_RESPONSE` e `* → IDLE`.
- `test_aijail_settings_writer.py`: `build_settings_json` produz JSON com 3 hooks; `write_settings_into_jail` cria arquivo 0644; `ensure_gitignore_entry` é append-idempotente (1ª chamada adiciona linha, 2ª não duplica, arquivo `.gitignore` ausente é criado).

Fakes: `FakeBroadcaster`, `FakeNotifier`, `FakeTokenRegistry`. `FakeProcessOps` já existe.

### 8.2 Integration (`tests/integration/`)

- `test_hooks_routes.py`: 404 token bad; 204 + status muta; PreToolUse 200; Stop 204; payload malformado 422.
- `test_hooks_concurrency.py`: 10 POSTs concorrentes na mesma sessão não corrompem nem geram duplo evento.
- `test_ws_endpoint.py`: conecta WS, dispara hook → recebe envelope; hook que não muda status → nenhum evento.
- `test_session_lifecycle_with_hooks.py`: start → Notification → Stop → stop_session, eventos publicados na ordem certa.

Real: `Database` testcontainer, `WsBroadcaster` real, `NoopNotifier` na fixture.

### 8.3 E2E (`tests/e2e/`)

- `test_hooks_e2e_flow.py`: container do daemon up → `start_session` via API → `container.exec curl http://localhost:8000/api/hooks/Notification/<token>` simula Claude → Playwright vê "Aguardando você" no card sem reload → `Stop` simula → "Concluído".

E2E **não** roda Claude real nem ai-jail (impossível dentro do container CI). Simulamos com curl o que o hook command faria — funciona porque o curl roda no próprio container do daemon, batendo no loopback (`localhost:8000`) onde o FastAPI está bound; sem necessidade de egress de jaula nesta camada de teste.

### 8.4 Frontend (`ui/src/lib/`, `ui/src/hooks/`)

- `ws.test.ts`: reconnect com backoff em close; mensagem inválida (não-JSON) loga e segue.
- `events.test.ts`: dispatcher chama handler certo por `type`; tipos desconhecidos não quebram.
- `useSessionEvents.test.ts`: `session.status` → `queryClient.invalidateQueries(queryKeys.sessions)`.

### 8.5 Cobertura

- Backend: 100% sobre `hooks/`, `events/`, `notifications/`. Delta em `core/sessions.py` (`update_status`) e `sandbox/aijail.py` (settings writer).
- `# pragma: no cover` permitido em: branch defensivo de `notify-send` ausente; `_build_production_app()` ao registrar novos routers (já é pragma desde F1).
- UI: 100% sobre `lib/ws.ts`, `lib/events.ts`, `hooks/useSessionEvents.ts`.

## 9. Ordem TDD planejada (preview pro plan)

1. Parser + registry + update_status — núcleo puro de domínio.
2. WS envelope + notifier sink — também puros.
3. Settings writer + integração `start_session` (gera token, registra).
4. Migration `0002_hook_columns.py`.
5. Routes integration por endpoint.
6. WS endpoint integration.
7. Glue de produção em `main.py` (broadcaster + notifier reais).
8. UI ws.ts + useSessionEvents + integração no `App.tsx`.
9. E2E flow.

Cada passo: RED → GREEN → REFACTOR. Commits pequenos por slice (target ~9 commits).

## 10. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| ai-jail pode não permitir egress pra `localhost:<port>` | Validar na fase de impl; se bloqueador, abrir ADR-0011 com alternativa (Unix socket no jail, fallback para hooks via stdin/stdout do processo) |
| Token vaza em logs (path da URL) | Daemon não loga path; usa `event_type + session_id` em logs estruturados |
| `notify-send` indisponível em alguns desktops (KDE puro, Wayland sem libnotify) | Falha silenciosa após 1º warning; sem morte de daemon. Usuário pode setar `JARVIS_NOTIFY=off` |
| WS broadcast lento bloqueia hook handler | `gather` paralelo; clients que falham são removidos. Hook handler retorna 204 em <100ms target |
| Race entre `Stop` do Claude e `stop_session` do botão | Status terminal é absorvente: hook em sessão terminal vira no-op silencioso (já tratado) |

## 11. Fora de escopo (F2)

- Fila central de aprovações (F3).
- Bloqueio real em `PreToolUse` (F3).
- Refinamento do parser pra distinguir tipos de `Notification` (F3).
- Auto-resumo via leitura de transcript (F8 / v1.5).
- Persistência de `WsEvent` (não há replay; clientes revalidam no reconnect).
- Auth no WebSocket (single-user / local-only, ADR-0001).
- **Token rotation**: token é gerado em `start_session`, revogado em `stop_session` ou em detecção de `Process.poll()` morto. Não há renovação no meio da sessão; se vazar, basta parar e recriar a sessão.
- **Rebuild do TokenRegistry no boot do daemon**: daemon on-demand mata sessões no shutdown; tokens em sessões `EXECUTING` órfãs no DB são tratados como expirados (registry inicia vazio).
- **Sweep de sessões órfãs**: linhas `ClaudeSession` com `status=EXECUTING` deixadas no DB de um run anterior **não** são marcadas como `ERROR` no boot — ficam como estão e continuam aparecendo na UI até o usuário clicar Stop (que vai falhar porque o token sumiu — daemon então marca `ERROR`). Sweep automático fica pra fase posterior se virar dor.

## 12. Definition of Done

- [ ] Migration `0002_hook_columns.py` aplicada e verificável via `alembic upgrade head`.
- [ ] 3 endpoints de hooks + endpoint WS funcionando end-to-end.
- [ ] `start_session` no `AiJailRuntime` escreve `<worktree>/.claude/settings.json` com token + URLs corretos; `stop_session` remove.
- [ ] UI atualiza status sem reload via WS.
- [ ] `notify-send` dispara em transições corretas.
- [ ] Unit/Integration/E2E/Vitest todos verdes.
- [ ] Cobertura 100% (pós-pragmas justificados) sobre código novo + delta dos editados.
- [ ] ADR-0009 (registro de hooks via `.ai-jail`) e ADR-0010 (envelope WS) criados em `docs/adr/`, indexados em `docs/adr/README.md`.
- [ ] `ARCHITECTURE.md` §4 atualizado pra refletir o que F2 entrega vs o que fica pra F3 (nota explícita: `Notification` → `AWAITING_RESPONSE` em F2, refinado em F3; `PreToolUse` audit-only em F2, vira `ApprovalRequest` em F3).
- [ ] `ARCHITECTURE.md` §13 atualizado com as duas novas linhas de ADR.
- [ ] **Demo A (NullSessionRuntime, automatizada via E2E)**: spawn sessão com `runtime=null` → curl no `/api/hooks/Notification/<token>` direto no daemon → UI muda de status sem reload. Valida o caminho hook→DB→WS→UI.
- [ ] **Demo B (AiJailRuntime, manual)**: spawn sessão real → conferir que `<worktree>/.claude/settings.json` foi escrito com token+URL corretos → rodar Claude dentro do jail → confirmar hooks chegando ao daemon. Valida o caminho settings-injection. Não bloqueia merge se ai-jail estiver indisponível no host de CI.
