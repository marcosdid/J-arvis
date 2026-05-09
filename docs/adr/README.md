# Architecture Decision Records (ADRs)

Registro de decisões arquiteturais. Estilo Michael Nygard.

## Convenções

- Nome do arquivo: `NNNN-slug-curto.md` (4 dígitos, kebab-case).
- Status: `Proposed` → `Accepted` → opcionalmente `Deprecated` ou
  `Superseded by NNNN`.
- ADRs **não se editam após `Accepted`**. Para mudar, criamos um novo
  ADR que supersede o anterior, e atualizamos o status do antigo.
- Linguagem: PT-BR no corpo; títulos curtos.

## Índice

| Nº | Título | Status | Data |
|---|---|---|---|
| [0001](0001-sandbox-via-ai-jail-externo.md) | Sandbox via ai-jail externo, com `SessionRuntime` abstrato | Accepted | 2026-05-08 |
| [0002](0002-stack-do-daemon.md) | Stack do daemon: Python 3.13 + FastAPI + SQLAlchemy 2 async + Alembic | Accepted | 2026-05-08 |
| [0003](0003-stack-da-ui.md) | Stack da UI: Vite 6 + React 19 + TanStack Query + Zustand | Accepted | 2026-05-08 |
| [0004](0004-tdd-iron-law-100-cobertura.md) | TDD como regra de ferro com 100% de cobertura em três camadas | Accepted | 2026-05-08 |
| [0005](0005-run-from-panel-manifesto-explicito.md) | Run from Panel: manifesto explícito (`.orchestrator/run.yml`) com bootstrap por Claude | Accepted | 2026-05-08 |
| [0006](0006-db-descartavel-por-execucao.md) | DB do Run from Panel: container Docker descartável por execução | Accepted | 2026-05-08 |
| [0007](0007-task-first-em-vez-de-session-first.md) | Modelo de domínio: task-first em vez de session-first | Accepted | 2026-05-08 |
| [0008](0008-sessao-em-terminal-nativo-do-desktop.md) | Sessão de Claude Code abre em terminal nativo do desktop | Accepted | 2026-05-08 |
| [0009](0009-hooks-via-settings-no-jail.md) | Registro de hooks via `settings.json` injetado dentro do jail | Accepted | 2026-05-09 |
| [0010](0010-websocket-canal-unico-envelope-tipado.md) | WebSocket único em `/ws` com envelope tipado | Accepted | 2026-05-09 |
