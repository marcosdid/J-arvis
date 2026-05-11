# F7 — Templates + perfis de permissão (design)

**Status:** spec aprovada, plan pending
**Data:** 2026-05-11
**Fecha:** MVP (F0 → F7) per ARCHITECTURE.md §11

## 1. Contexto

Desde F4 as colunas `Task.template` e `Task.permission_profile` (`String(64)`, nullable) existem
mas ficaram NULL — F4 deixou pra F7 popular. Hoje todo spawn (F1+) usa
`["claude", "--dangerously-skip-permissions"]` hardcoded em `write_aijail_config()`
(orchestrator/sandbox/aijail.py:71-78). Não há nenhum perfil de permissão configurável
nem semântica de "tipo de trabalho" aplicada à task.

F7 entrega o que ARCHITECTURE.md §11 promete: "Templates frontend/backend/refactor/bugfix
com perfil pré-aprovado. Catálogo, perfil aplicado no spawn." Encerra o MVP.

## 2. Decisões architecturais

| # | Decisão | Motivação |
|---|---|---|
| 1 | **`permission_profile` controla só flags do Claude CLI** | Escopo enxuto. ai-jail (rw_maps, allow_tcp_ports etc.) fica fora — é dimensão ortogonal de segurança que F7 não toca. |
| 2 | **Template carrega payload mínimo**: `name + description + default_permission_profile + branch_prefix` | YAGNI. Sem CLAUDE.md snippets, sem prompt inicial. Templates são curadoria, não automação. |
| 3 | **Catálogo é YAML curado em `orchestrator/config/catalog.yml`** | Match perfeito com "pré-aprovado" do roadmap. Sem migração nova, sem CRUD, sem UI de admin. Editar = commit. |
| 4 | **UI entry point único: dropdown "Template" no form de criar task** | Sem override no session start. Sem edit pós-create. Mantém Kanban/sessões simples. |
| 5 | **Catálogo: 3 perfis (`yolo`, `default`, `read-only`) + 4 templates + fallback `yolo`** | `yolo` mantém comportamento atual de F1-F6 pra tasks NULL. 3 perfis cobrem dev rápido, postura cuidadosa, e exploração. |
| 6 | **Snapshot-at-create**: `Task.permission_profile` é gravado no POST, não relido do catálogo no spawn | Catálogo editado depois não muda comportamento de tasks existentes. Importante pra reprodutibilidade. |
| 7 | **Hard fail no spawn se perfil sumiu do catálogo**: 422 com detalhe | Fere o contrato "pré-aprovado" silenciosamente. Melhor falhar e fazer admin restaurar ou usuário recriar a task. |

## 3. Conteúdo do catálogo

`orchestrator/config/catalog.yml`:

```yaml
version: "1"
fallback_permission_profile: yolo

permission_profiles:
  yolo:
    description: "Skip todos os prompts — modo dev rápido"
    claude_args: ["--dangerously-skip-permissions"]
  default:
    description: "Claude pergunta a cada tool — postura cuidadosa"
    claude_args: []
  read-only:
    description: "Plan mode + tools de leitura — exploração/code review"
    claude_args: ["--permission-mode", "plan", "--allowed-tools", "Read,Grep,Glob,LS"]

templates:
  frontend:
    description: "UI/UX, componentes, estilo"
    default_permission_profile: yolo
    branch_prefix: "feat-ui/"
  backend:
    description: "API, modelos, lógica de servidor"
    default_permission_profile: default
    branch_prefix: "feat-be/"
  refactor:
    description: "Limpeza estrutural sem mudar comportamento"
    default_permission_profile: default
    branch_prefix: "refactor/"
  bugfix:
    description: "Correção de defeito específico"
    default_permission_profile: yolo
    branch_prefix: "fix/"
```

## 4. Modelo Pydantic

`orchestrator/core/catalog.py`:

```python
from typing import Literal, Self
from pydantic import BaseModel, ConfigDict, Field, model_validator

class CatalogValidationError(Exception):
    pass

class PermissionProfileSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str
    claude_args: list[str] = []

class TemplateSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str
    default_permission_profile: str
    branch_prefix: str = Field(pattern=r"^[a-z][a-z0-9-]*/$")

class Catalog(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal["1"]
    fallback_permission_profile: str
    permission_profiles: dict[str, PermissionProfileSpec]
    templates: dict[str, TemplateSpec]

    @model_validator(mode="after")
    def _check_refs(self) -> Self:
        if self.fallback_permission_profile not in self.permission_profiles:
            raise CatalogValidationError(
                f"fallback_permission_profile {self.fallback_permission_profile!r} "
                f"not in permission_profiles"
            )
        for tname, tspec in self.templates.items():
            if tspec.default_permission_profile not in self.permission_profiles:
                raise CatalogValidationError(
                    f"template {tname!r}.default_permission_profile "
                    f"{tspec.default_permission_profile!r} not in permission_profiles"
                )
        return self

def load_catalog(path: Path) -> Catalog:
    """Lê YAML, valida (Pydantic + refs), retorna Catalog. Raise
    CatalogValidationError se inválido."""
```

Validação no startup: daemon recusa subir se `catalog.yml` inválido. Catalog é
load-bearing — fail fast é correto.

## 5. Schema do banco

**Sem migração nova.** `Task.template` e `Task.permission_profile` (String(64) nullable)
existem desde F4. F7 só populá-las.

Tasks F4-F6 existentes continuam com NULL/NULL e usam `fallback_permission_profile`
(que é `yolo` — comportamento idêntico ao atual). Sem backfill, sem quebra silenciosa.

## 6. API contract

### `GET /api/catalog`

Read-only, cacheable. Retorna dict|list serializado do `Catalog`:

```json
{
  "version": "1",
  "fallback_permission_profile": "yolo",
  "permission_profiles": [
    {"name": "yolo", "description": "...", "claude_args": ["--dangerously-skip-permissions"]},
    {"name": "default", "description": "...", "claude_args": []},
    {"name": "read-only", "description": "...", "claude_args": ["--permission-mode", "plan", "--allowed-tools", "Read,Grep,Glob,LS"]}
  ],
  "templates": [
    {"name": "frontend", "description": "...", "default_permission_profile": "yolo", "branch_prefix": "feat-ui/"},
    {"name": "backend", "description": "...", "default_permission_profile": "default", "branch_prefix": "feat-be/"},
    {"name": "refactor", "description": "...", "default_permission_profile": "default", "branch_prefix": "refactor/"},
    {"name": "bugfix", "description": "...", "default_permission_profile": "yolo", "branch_prefix": "fix/"}
  ]
}
```

Note: dicts viram listas com `name` adicionado pra ordem estável. UI faz fetch 1x com
`staleTime: Infinity` (catálogo só muda com restart do daemon).

### `POST /api/tasks` — mudanças

```python
class TaskCreatePayload(BaseModel):
    project_id: str
    title: str
    description: str = ""
    branch: str | None = None
    template: str | None = None  # NEW — opcional
```

**Server-side resolution** em `create_task`:

```python
async def create_task(db, *, project_id, title, description, branch, template, catalog):
    if template is not None:
        if template not in catalog.templates:
            raise InvalidTemplateError(template, list(catalog.templates.keys()))
        tspec = catalog.templates[template]
        permission_profile = tspec.default_permission_profile
        if branch is None:
            branch = f"{tspec.branch_prefix}{slugify(title)}"
    else:
        permission_profile = None
    # ... resto idêntico a F4
```

Comportamento:
- `template=None`: NULL/NULL (back compat F4-F6)
- `template="frontend"`, `branch=None`: `template="frontend"`, `permission_profile="yolo"`, `branch="feat-ui/<slug>"`
- `template="frontend"`, `branch="custom"`: `template="frontend"`, `permission_profile="yolo"`, `branch="custom"` (override respeitado, prefix ignorado)
- `template="inexistente"`: 422 `template_not_in_catalog`

## 7. Spawn integration

### `write_aijail_config` (aijail.py)

Hoje:
```python
'command = ["claude", "--dangerously-skip-permissions"]\n'
```

F7:
```python
def write_aijail_config(cwd: Path, *, claude_args: list[str]) -> None:
    """`claude_args` é o claude_args do perfil resolvido (caller responsibility)."""
    full_argv = ["claude", *claude_args]
    args_json = json.dumps(full_argv)
    (cwd / ".ai-jail").write_text(
        f"command = {args_json}\n"
        f"rw_maps = {rw_block}\n"
        ...
    )
```

### `AiJailRuntime.spawn`

```python
class PermissionProfileNotInCatalogError(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(f"permission_profile {name!r} not in catalog")
        self.name = name

async def spawn(
    self,
    worktree: Path,
    *,
    permission_profile: str | None,
    catalog: Catalog,
    token: str | None = None,
    base_url: str | None = None,
) -> JailHandle:
    name = permission_profile or catalog.fallback_permission_profile
    if name not in catalog.permission_profiles:
        raise PermissionProfileNotInCatalogError(name)
    claude_args = catalog.permission_profiles[name].claude_args
    if token is not None and base_url is not None:
        write_settings_into_jail(worktree, token=token, base_url=base_url)
        ensure_gitignore_entry(worktree)
    write_aijail_config(worktree, claude_args=claude_args)
    # ... resto idêntico
```

### `SessionRuntime` Protocol

Ganha `permission_profile: str | None` + `catalog: Catalog` nos kwargs de `spawn`.
`NullSessionRuntime` (test fake) aceita e ignora. Só `AiJailRuntime` consome.

### `start_session`

`orchestrator/core/sessions.start_session` recebe `catalog` via DI e passa adiante
no `runtime.spawn(...)`. Mesmo padrão de `git_ops`/`docker_ops`/`port_allocator`.

API: `POST /api/tasks/{id}/sessions` ganha `Depends(resolve_catalog)`.

### Erro path

Spawn raise `PermissionProfileNotInCatalogError` → API converte para HTTP 422
`permission_profile_not_in_catalog` com `detail` formatado:
`"perfil 'X' foi removido do catalog.yml — edite a task ou restaure o perfil"`.

Caso de uso: admin editou `catalog.yml`, removeu `yolo`, restart, task com
`permission_profile="yolo"` tenta iniciar sessão. Sem fallback silencioso.

## 8. UI changes

### Form de criar task

Componente `NewTaskForm` (ou onde mora hoje o `<input>` de título). Adiciona:

```
Template: [▼ (nenhum)                ]
         ├─ (nenhum) — sem prefil
         ├─ frontend — UI/UX…
         ├─ backend  — API…
         ├─ refactor — Limpeza…
         └─ bugfix   — Correção…
```

- `<select aria-label="template">` com opção vazia + 4 do catálogo
- Hint dinâmico abaixo:
  - Sem template: ""
  - Template + branch vazio: `"Branch será: feat-ui/fix-logout"` (calculado client-side via slugify)
  - Template + branch preenchido: `"Branch override — prefix ignorado"`
- Submit envia `{template: "frontend"}` ou `{template: null}` (omit se null)

### `TaskCard`

Dois chips quando template/permission_profile não-NULL:

```
[bugfix] [yolo]
```

- `<span data-template-name="bugfix">bugfix</span>`
- `<span data-permission-profile="yolo">yolo</span>`
- Cores por perfil: yolo=amarelo, default=cinza, read-only=verde
- Tooltip on hover com `description` do catálogo

### `TaskDetailModal`

Seção "Configuração" read-only mostrando template + permission_profile + branch.
Sem botão de editar.

### `useCatalog` hook

```typescript
// ui/src/hooks/useCatalog.ts
export function useCatalog() {
  return useQuery({
    queryKey: queryKeys.catalog(),
    queryFn: () => api.getCatalog(),
    staleTime: Infinity,
  });
}
```

`queryKeys.catalog = () => ['catalog'] as const`.

## 9. Testing strategy

### Backend unit (tests/unit/)

- `test_catalog.py`: load YAML válido → Catalog; load com extra fields → forbid; load com fallback_permission_profile dangling → CatalogValidationError; load com template.default_permission_profile dangling → CatalogValidationError; branch_prefix sem `/` → ValidationError; version != "1" → ValidationError; load_catalog raise FileNotFoundError se ausente
- `test_tasks_create_with_template.py`: template válido + branch None → resolve prefix; template válido + branch="x" → respeita override; template inválido → InvalidTemplateError; template None → NULL/NULL
- `test_aijail_spawn_args.py`: write_aijail_config emite JSON correto pra cada perfil; AiJailRuntime.spawn com permission_profile=None usa fallback; com perfil válido injeta claude_args; com perfil ausente do catalog raise PermissionProfileNotInCatalogError

### Backend integration (tests/integration/)

- `test_api_catalog.py`: GET /api/catalog retorna 200 + estrutura completa; sem auth required
- `test_api_tasks_template.py`: POST com template=frontend → 201 com permission_profile=yolo + branch=feat-ui/<slug>; POST com template=inexistente → 422 template_not_in_catalog com lista de válidos; POST sem template → 201 com NULL/NULL
- `test_sessions_uses_profile.py`: criar task com template=read-only, start_session, verificar via FakeProcessOps que `.ai-jail` tem `command = ["claude", "--permission-mode", "plan", "--allowed-tools", "Read,Grep,Glob,LS"]`

### UI (ui/src/**/*.test.{ts,tsx})

- `useCatalog.test.ts`: cacheia infinito, expõe data, calls api.getCatalog 1x
- `NewTaskForm.test.tsx`: dropdown renderiza 4 opções + (nenhum); selecionar template mostra hint de branch; preencher branch oculta hint de prefix; submit envia template no payload; template=(nenhum) → payload omite template
- `TaskCard.test.tsx`: badges renderizam quando template/permission_profile presentes; ausentes quando NULL

### E2E (tests/e2e/, host-only, skipped no sandbox)

- `test_f7_create_task_with_template.py`: abre form, escolhe "frontend", verifica branch hint, criar, ver badge no card

## 10. Sub-task breakdown (preview)

| ID | Entrega | Tests |
|---|---|---|
| **F7.a** | catalog.yml + Catalog Pydantic + load_catalog + ref validation | unit (test_catalog.py) |
| **F7.b** | GET /api/catalog endpoint + resolve_catalog DI helper + lifespan wiring | integration (test_api_catalog.py) |
| **F7.c** | create_task aceita template, resolve prefix + permission_profile + InvalidTemplateError | unit + integration |
| **F7.d** | write_aijail_config + AiJailRuntime.spawn recebem claude_args via catalog; PermissionProfileNotInCatalogError → 422 | unit (test_aijail_spawn_args) + integration (test_sessions_uses_profile) |
| **F7.e** | useCatalog hook + queryKeys.catalog + NewTaskForm dropdown + hint dinâmico | UI |
| **F7.f** | TaskCard badges + TaskDetailModal Configuração section + cores por perfil | UI |
| **F7.g** | ADR-0021 (catalog YAML curado) + ARCHITECTURE.md §11 ✅ + E2E skeletons (host) + closure | docs + e2e |

7 sub-tasks. Menor que F6 (13). F7 é CRUD-light + 1 ponto de mudança no spawn + UI dropdown/badges.

## 11. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Catalog inválido derruba daemon no boot | Mensagem clara no startup; admin edita YAML e restarta. Sem auto-fallback. |
| Tasks F4-F6 (NULL) mudam comportamento na próxima sessão | Fallback é `yolo` = idêntico ao hardcoded atual. Sem regressão observável. |
| Catálogo editado, perfil de task X sumiu | Spawn 422 explícito com mensagem acionável; admin restaura YAML OU user recria task. Sem dado perdido. |
| UI cacheia catálogo, daemon restarta com YAML novo | `staleTime: Infinity` significa SPA precisa reload pra ver novo catálogo. Aceitável — restart de daemon é evento raro e operador-driven. |
| Slugify do title produz branch já existente | `start_session` já tem CwdAlreadyExistsError (F5). Erro 422 atual cobre. |

## 12. Não-objetivos

- CRUD UI de templates/perfis (DB-backed + admin page) — F8+ se necessário
- Override de perfil no session start (UI engrenagem) — fora de scope per decisão #4
- Perfis afetando ai-jail (rw_maps, allow_tcp_ports) — fora de scope per decisão #1
- Edit de template/permission_profile via TaskDetailModal — fora de scope per decisão #4
- CLAUDE.md snippets, initial_prompt — fora de scope per decisão #2
- Override por projeto (`.orchestrator/catalog.yml`) — fora de scope per decisão #3
