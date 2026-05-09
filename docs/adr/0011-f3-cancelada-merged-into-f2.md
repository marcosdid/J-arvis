# ADR-0011: F3 cancelada — funcionalidade absorvida em F2

- **Status:** Accepted
- **Data:** 2026-05-09
- **Decisores:** Marcos

## Contexto

O roadmap original (ARCHITECTURE.md §11) previa **F3 — Fila central de
aprovações**: promover `AWAITING_APPROVAL` de placeholder a status real,
fazer `PreToolUse` bloquear de verdade (sync decision via daemon), e
adicionar painel único agregando approval requests por sessão. O
objetivo era oferecer UX de operador estilo "fila de pendências"
controlada pelo J-arvis.

Ao brainstormar F3 surgiu uma constatação central: **o usuário decide
permissões diretamente no terminal nativo do Claude Code**, que já
implementa prompt interativo (`[y/n/always]`) e suporta configuração
permanente via `permissions.allow`/`deny` no `settings.json` por
projeto. J-arvis não controla essa decisão. J-arvis observa e alerta.

F2 já entrega o caminho de alerta:

- `Notification` hook → status `AWAITING_RESPONSE` → `notify-send`
  dispara → badge e cor diferentes na UI → usuário sabe que a sessão
  precisa de atenção.
- Ao abrir o terminal nativo (ADR-0008), o usuário decide local com a
  UX que o Claude Code já oferece nativamente.

Adicionar `ApprovalRequest` no DB, fila ativa, endpoints de
approve/deny e bloqueio sync via `asyncio.Event` duplicaria a
infraestrutura que o Claude Code já fornece — e introduziria um
caminho de decisão paralelo ao terminal nativo, abrindo espaço pra
inconsistências (DB diz "approved", terminal continua mostrando
prompt; ou vice-versa).

## Decisão

**F3 cancelada como fase distinta.** O escopo "alertar quando sessão
precisa de aprovação" é coberto por F2 (`Notification` →
`AWAITING_RESPONSE` + `notify-send`). Não criamos `ApprovalRequest`,
não adicionamos endpoints de aprovação, não bloqueamos `PreToolUse`
no daemon.

Como consequência:

- `SessionStatus.AWAITING_APPROVAL` (reservado no enum desde F1) é
  **removido**. Não existem rows com esse valor em produção (nunca foi
  setado). YAGNI.
- `ARCHITECTURE.md` §11 marca F3 como cancelada/fundida em F2.
  Numeração F4-F8 **mantida** pra não quebrar referências em
  specs/plans/ADRs já escritos.
- `PreToolUse` segue audit-only como em F2: registra evento, retorna
  `{"continue": true}`, broadcasta `session.tool_use` para a UI mostrar
  atividade. Sem bloqueio, sem fila.

## Alternativas consideradas

1. **F3 com auto-decide no daemon (blocklist/allowlist em DB):**
   rejeitada. Duplica `permissions.allow`/`deny` do `settings.json`,
   adiciona caminho paralelo de decisão, e exige rule engine no daemon.
2. **F3 com fila ativa + bloqueio sync (`asyncio.Event`):** rejeitada.
   Funcional, mas conflita com prompt interativo do terminal nativo
   (Claude pergunta `[y/n/always]` e espera no terminal — daemon não
   tem evento pra interceptar antes do prompt). Passar pelo daemon
   exigiria desligar o prompt interativo do Claude, perdendo a UX
   nativa que o usuário já conhece.
3. **F3 mínima — só alerta diferente:** distinguir Notification de
   permission-request vs Notification genérica e setar
   `AWAITING_APPROVAL` no primeiro caso. Rejeitada por **YAGNI**:
   `notify-send` + `AWAITING_RESPONSE` já alerta o suficiente; cor/ícone
   diferente é refinamento cosmético sem ganho de capacidade.

## Consequências

**Positivas**

- Menos código pra manter: zero infraestrutura de fila, zero endpoints
  de approval, zero migration de tabela `approval_requests`.
- Decisão de permissão fica no Claude Code (one source of truth via
  `settings.json` + prompt interativo).
- Roadmap encurta uma fase. Próxima é F4 (backlog kanban).

**Negativas**

- Se um dia o usuário quiser headless approval (decidir tudo via UI
  web sem abrir terminal), F3 precisa renascer. Esse cenário não está
  no horizonte (single-user, local-only — ADR-0001).
- ADR-0010 menciona `approval.created/decided` como uso futuro do
  envelope WS único. Esses tipos não vão existir; ADR-0010 segue
  válido (envelope tipado é genérico, novos tipos surgem com novas
  fases — F4 traz `task.updated`, F6 traz logs do Run from Panel).

**Neutras**

- Specs/plans escritos antes deste ADR (ex.: spec da F2) mencionam F3
  e `AWAITING_APPROVAL` como "reservado pra F3". Documentos de
  spec/plan são imutáveis por design — não editamos, apenas
  referenciamos este ADR para contexto histórico.

## Referências

- ARCHITECTURE.md §3 (status enum atualizado)
- ARCHITECTURE.md §11 (roadmap atualizado)
- ADR-0001 (single-user / local-only)
- ADR-0008 (sessão em terminal nativo do desktop)
- ADR-0009 (settings.json no jail — onde `permissions.allow`/`deny`
  ficaria, hoje gerenciado pelo usuário fora do daemon)
