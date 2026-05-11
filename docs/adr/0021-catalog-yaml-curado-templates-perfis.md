# ADR-0021: Catálogo curado (YAML) de templates + perfis de permissão

**Status:** Accepted — 2026-05-11
**Decisores:** marcosdid + Claude
**Contexto:** F7 (última fase do MVP)

## Contexto

`Task.template` e `Task.permission_profile` (colunas `String(64)` nullable) existem
desde F4 mas nunca foram populadas. ARCHITECTURE.md §11 promete na F7:
"Templates frontend/backend/refactor/bugfix com perfil pré-aprovado. Catálogo,
perfil aplicado no spawn." Spawn (F1+) usa `--dangerously-skip-permissions`
hardcoded em `write_aijail_config()`.

Decidir:
1. Onde mora o catálogo (DB / YAML / Python const / híbrido)
2. Quem escreve nele (admin via UI / commit no repo)
3. O que muda no spawn

## Decisão

- **YAML curado em `orchestrator/config/catalog.yml`**, versionado no repo. Sem
  CRUD via API, sem UI de admin, sem migração de banco.
- Carregado **1x no lifespan** via Pydantic v2 (`extra="forbid"` + cross-field
  validation). Daemon recusa subir se inválido.
- 3 perfis no catálogo inicial: `yolo` (`--dangerously-skip-permissions`),
  `default` (`[]`), `read-only` (`--permission-mode plan` + tools de leitura).
- 4 templates: `frontend` (yolo + `feat-ui/`), `backend` (default + `feat-be/`),
  `refactor` (default + `refactor/`), `bugfix` (yolo + `fix/`).
- `fallback_permission_profile=yolo`: tasks F4-F6 com NULL/NULL spawnam com
  yolo — comportamento bit-identical ao hardcoded F1-F6.
- **Snapshot-at-create do nome** (não dos args): `Task.permission_profile`
  grava o nome do perfil. No spawn, nome é re-resolvido no catálogo carregado
  pra extrair `claude_args`.
- **Hard fail no spawn** se task aponta pra perfil que foi removido do catálogo
  (admin editou + reiniciou): HTTP 422 `permission_profile_not_in_catalog`.
- UI: dropdown único de Template no form de criar task. Sem override no spawn,
  sem edit pós-create.

## Alternativas consideradas

- **DB-backed com CRUD**: rejeitado — overkill pro MVP, nenhum requerimento de
  admin runtime. Custo (migration + endpoints + invariantes) sem retorno.
- **Hardcoded em Python const**: alternativa razoável. Rejeitada por
  ergonomia — editar perfil via PR review com diff YAML é mais legível que
  dataclass.
- **Híbrido (YAML global + override por projeto)**: rejeitado — fere
  simplicidade do MVP. Pode ser reintroduzido em fase futura.

## Consequências

**Positivas:**
- Sem migração, sem coupling adicional ao schema do banco.
- Catálogo auditável via git log + diff YAML legível.
- Editar perfil = commit + restart, fluxo familiar pra equipe.
- F4-F6 tasks NULL spawnam com yolo (idêntico ao hardcoded F1-F6) — zero regressão observável.

**Negativas:**
- Editar `claude_args` de um perfil **após** snapshot-at-create afeta tasks
  existentes na próxima sessão (após restart). Admin precisa saber disso.
- Sem UI de admin: alguém precisa entender YAML pra adicionar perfis. Aceitável
  no MVP (1 dev).
- Catalog reload requer restart do daemon. Restart de daemon é raro mas observável.

## Referências

- Spec: `docs/superpowers/specs/2026-05-11-f7-templates-perfis-design.md`
- Plan: `docs/superpowers/plans/2026-05-11-f7-templates-perfis.md`
- ARCHITECTURE.md §11 (roadmap), §13 (decisões)
- Código: `orchestrator/core/catalog.py`, `orchestrator/config/catalog.yml`,
  `orchestrator/sandbox/aijail.py` (`write_aijail_config`, `PermissionProfileNotInCatalogError`)
