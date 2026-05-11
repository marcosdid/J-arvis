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
| 6 | **Snapshot-at-create do nome do perfil** (não dos args): `Task.permission_profile` grava só o nome (string). No spawn, o nome é re-resolvido no catálogo carregado em `app.state.catalog` pra extrair `claude_args`. Se admin editar `claude_args` de um perfil existente e **reiniciar o daemon**, tasks existentes verão o args novo na próxima sessão; se admin remover o perfil (e reiniciar), tasks existentes recebem 422 (decisão 7). | Snapshot do nome (não dos args) preserva reprodutibilidade de qual perfil foi escolhido (audit trail), mas evita carregar args duplicados em milhares de rows. Admin sabe que editar `claude_args` é alteração propagante após restart. |
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
    branch_prefix: str = Field(pattern=r"^[a-z][a-z0-9-]*/$")  # single-segment only (uma `/` no fim)

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

**Lifecycle:** `load_catalog()` é chamado **exatamente uma vez** no `lifespan`
do FastAPI (`orchestrator/main.py:create_app`), guardado em `app.state.catalog`,
e **nunca recarregado** durante o uptime do daemon. Editar `catalog.yml` em
runtime não tem efeito até restart. Isso é intencional — match com semântica
de "pré-aprovado" (catálogo é estável durante a vida do daemon).

Validação no startup: daemon recusa subir se `catalog.yml` inválido. Catalog é
load-bearing — fail fast é correto.

**Validação de nomes:** chaves de `permission_profiles` e `templates` devem bater
regex `^[a-z][a-z0-9-]*$` (mesma do `branch_prefix` sem a `/` final). Pydantic
validator adicional no `Catalog.model_validator(mode="after")`.

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
from orchestrator.core.slug import slugify_for_branch, InvalidBranchSlugError

async def create_task(db, *, project_id, title, description, branch, template, catalog):
    if template is not None:
        if template not in catalog.templates:
            raise InvalidTemplateError(template, list(catalog.templates.keys()))
        tspec = catalog.templates[template]
        permission_profile = tspec.default_permission_profile
        if branch is None:
            # slugify_for_branch já é usado em start_session (F1+); raise
            # InvalidBranchSlugError pra title impossível (ex.: "!!!").
            branch = f"{tspec.branch_prefix}{slugify_for_branch(title)}"
    else:
        permission_profile = None
    # ... resto idêntico a F4
```

**Slugify contract.** Backend usa `orchestrator/core/slug.py:slugify_for_branch`
(já existe, usado em `start_session` desde F1). Frontend usa
`ui/src/lib/slug.ts` (já existe). O módulo backend tem comentário explícito:
*"NB: this function MUST stay in 1:1 sync with ui/src/lib/slug.ts"*. F7 não
introduz slugify novo — só consome ambos. Lambda branch_prefix + slugify do
title é simples concatenação de string.

Comportamento:
- `template=None`: NULL/NULL (back compat F4-F6)
- `template="frontend"`, `branch=None`: `template="frontend"`, `permission_profile="yolo"`, `branch="feat-ui/<slug>"`
- `template="frontend"`, `branch="custom"`: `template="frontend"`, `permission_profile="yolo"`, `branch="custom"` (override **literal**, prefix nunca aplicado mesmo se "custom" começar com "feat-ui/")
- `template="frontend"`, `branch=None`, `title="!!!"`: `InvalidBranchSlugError` → 422 (mesmo path que F1+ usa hoje quando título degenerado)
- `template="inexistente"`: 422 `template_not_in_catalog` com `detail.valid_templates: [...]`

## 7. Spawn integration

### `write_aijail_config` (aijail.py)

Assinatura atual (`aijail.py:61`):

```python
def write_aijail_config(cwd: Path) -> None:
    git_dirs = _discover_git_dirs(cwd)
    rw_lines = ",\n".join(f'    "{p}"' for p in git_dirs)
    rw_block = f"[\n{rw_lines},\n]" if git_dirs else "[]"
    (cwd / ".ai-jail").write_text(
        'command = ["claude", "--dangerously-skip-permissions"]\n'
        f"rw_maps = {rw_block}\n"
        'ro_maps = []\n'
        'hide_dotdirs = []\n'
        'mask = []\n'
        'allow_tcp_ports = []\n'
    )
```

F7 muda **apenas a linha `command`** — `rw_maps`/`ro_maps`/`hide_dotdirs`/`mask`/`allow_tcp_ports`
seguem idênticos. Nova assinatura:

```python
def write_aijail_config(cwd: Path, *, claude_args: list[str]) -> None:
    """`claude_args` vem resolvido do perfil de permissão da task (caller
    responsibility). `claude_args=[]` produz `command = ["claude"]` (perfil
    `default`)."""
    git_dirs = _discover_git_dirs(cwd)
    rw_lines = ",\n".join(f'    "{p}"' for p in git_dirs)
    rw_block = f"[\n{rw_lines},\n]" if git_dirs else "[]"
    full_argv = ["claude", *claude_args]
    args_json = json.dumps(full_argv)
    (cwd / ".ai-jail").write_text(
        f"command = {args_json}\n"
        f"rw_maps = {rw_block}\n"
        'ro_maps = []\n'
        'hide_dotdirs = []\n'
        'mask = []\n'
        'allow_tcp_ports = []\n'
    )
```

Resto da função (corpo `_discover_git_dirs` etc.) inalterado.

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

### `SessionRuntime` Protocol — breaking change

```python
class SessionRuntime(Protocol):
    async def spawn(
        self,
        worktree: Path,
        *,
        permission_profile: str | None,  # NEW — required kwarg, sem default
        catalog: Catalog,                # NEW — required kwarg, sem default
        token: str | None = None,
        base_url: str | None = None,
    ) -> JailHandle: ...
```

Os dois novos kwargs são **obrigatórios** (sem default). Razão: spawn não
tem como adivinhar `catalog` (precisa do DI parent) — passar como required
força call sites a serem explícitos e os erros aparecem no import/type-check,
não em runtime.

**Callers enumerados (grepped):**

| Caller | Como passa novos kwargs |
|---|---|
| `orchestrator/core/sessions.py:start_session` (linha 196) | `permission_profile=task.permission_profile, catalog=catalog` (catalog vem via param do start_session) |
| `orchestrator/api/bootstrap.py:60` (F6 bootstrap session) | `permission_profile=None, catalog=catalog` — bootstrap é efêmero, usa fallback do catálogo |
| `tests/unit/test_null_runtime.py` (3 chamadas) | `permission_profile=None, catalog=_test_catalog_fixture` — fixture mínima |
| `tests/unit/test_session_start_atomic.py` | mesmo |
| `tests/integration/test_bootstrap_endpoint.py` | já usa FakeSessionRuntime; fixture aceita novos kwargs |

`NullSessionRuntime` (test fake): aceita os novos kwargs e ignora — sem comportamento real. `AiJailRuntime`: consome ambos (descrito acima).

### `start_session`

```python
# orchestrator/core/sessions.py — current line 196
handle = await runtime.spawn(cwd, token=token, base_url=base_url)
# F7 →
handle = await runtime.spawn(
    cwd,
    permission_profile=task.permission_profile,
    catalog=catalog,
    token=token,
    base_url=base_url,
)
```

`start_session` recebe `catalog: Catalog` como param (vem do `Depends(resolve_catalog)`
na rota API). Mesmo padrão de `git_ops`/`docker_ops`/`port_allocator`.

API: `POST /api/tasks/{id}/sessions` ganha `Depends(resolve_catalog)`. Bootstrap
endpoint (F6) também ganha; passa adiante na chamada `runtime.spawn`.

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
- Cores conhecidas: `yolo=amarelo`, `default=cinza`, `read-only=verde`. Perfis fora dessa lista (futuro admin adicionou no YAML) → fallback **cinza**.
- Tooltip on hover com `description` do catálogo (texto verbatim do YAML — sem i18n, sem truncação)

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

- `test_api_catalog.py`:
  - GET /api/catalog retorna 200 + estrutura completa
  - Shape pinning: response tem `permission_profiles` e `templates` como **listas** com `name` adicionado (não dicts), ordem alfabética
  - Sem auth required
- `test_api_tasks_template.py`:
  - POST com template=frontend → 201 com `permission_profile=yolo` + `branch=feat-ui/<slug>`
  - POST com template=inexistente → 422 `template_not_in_catalog` com `detail.valid_templates=[...]`
  - POST sem template → 201 com NULL/NULL (back compat)
  - POST com template + branch="custom" → respeita branch literal, prefix ignorado
  - POST com template + title degenerado ("!!!") → 422 `InvalidBranchSlugError`
  - **Branch collision**: POST com template=frontend dois títulos que slugificam pro mesmo branch — segundo não falha aqui (task aceita); start_session é quem retorna `CwdAlreadyExistsError` ao tentar criar worktree (já testado em F5; aqui só verifica que POST aceita branches duplicados)
- `test_sessions_uses_profile.py`:
  - Criar task com template=read-only, start_session, verificar via observador no FakeProcessOps que `.ai-jail` tem `command = ["claude", "--permission-mode", "plan", "--allowed-tools", "Read,Grep,Glob,LS"]`
  - **Back-compat NULL**: criar task SEM template (`permission_profile=NULL`), start_session, verificar `.ai-jail` tem `command = ["claude", "--dangerously-skip-permissions"]` (fallback=yolo idêntico ao hardcoded F1-F6)
  - **422 stale profile**: criar task com `permission_profile="yolo"`, mockar `app.state.catalog` com catálogo SEM `yolo`, tentar start_session → 422 `permission_profile_not_in_catalog` com mensagem citando `'yolo'` e instrução "edite a task ou restaure o perfil"
  - **Bootstrap**: F6 bootstrap session usa `permission_profile=None` → resolve via fallback do catálogo, escreve `.ai-jail` correspondente

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
