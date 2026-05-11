# F7 — Templates + perfis de permissão (plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar catálogo curado de templates (frontend/backend/refactor/bugfix) + perfis de permissão (yolo/default/read-only) aplicados no spawn da sessão Claude, fechando o MVP (F7 = última fase do roadmap).

**Architecture:** YAML estático em `orchestrator/config/catalog.yml` carregado 1x no lifespan via Pydantic. UI ganha dropdown único de template no form de criar task. Backend grava `Task.permission_profile` como snapshot do nome (colunas já existem desde F4) e `AiJailRuntime.spawn` resolve `claude_args` do catálogo em runtime. Sem migração de banco.

**Tech Stack:** Python 3.13 + FastAPI + Pydantic v2 + pyyaml; React 19 + Vite 6 + TanStack Query + Vitest; pytest (unit/integration/E2E Playwright host-only).

**Spec:** `docs/superpowers/specs/2026-05-11-f7-templates-perfis-design.md`

---

## Test fan-out — fixtures shared

F7 muda 2 assinaturas críticas:
- `create_task(...)` ganha `template: str | None` + `catalog: Catalog` (required kwarg)
- `SessionRuntime.spawn(...)` ganha `permission_profile: str | None` + `catalog: Catalog` (required kwargs)

**13 arquivos de teste existentes** chamam `create_task` ou `start_session` direto.
Pra evitar iteração caótica, **F7.a step 8** define um helper `_TEST_CATALOG` em
`tests/conftest.py` (module-level, carrega catalog.yml curado) + fixture pytest
`catalog`. F7.c step 8 e F7.d step 9 enumeram explicitamente os arquivos a tocar.

**Lista de arquivos que precisam `catalog=` adicionado (create_task callers):**

- `tests/unit/test_task_crud.py`
- `tests/unit/test_task_title_validation.py`
- `tests/unit/test_task_branch_validation.py`
- `tests/unit/test_project_delete_blocked.py`
- `tests/unit/test_task_auto_transition.py`
- `tests/unit/test_session_per_task_lock.py`
- `tests/unit/test_session_token_lifecycle.py`
- `tests/unit/test_session_start_atomic.py`
- `tests/unit/test_session_start_re_iniciar.py`
- `tests/unit/test_session_start_branch_clash.py`
- `tests/unit/test_session_start_no_worktree_id.py`
- `tests/unit/test_bootstrap_watcher.py`
- `tests/integration/test_branch_override_field.py`
- `tests/integration/test_task_session_route.py` (API route — vai via DI, não precisa explicit kwarg; só vai via spawn ratio)

**FakeSessionRuntime** em `tests/integration/conftest.py` precisa aceitar
`permission_profile`/`catalog` com default `None` (e ignorar).

---

## File structure

### Files to create

| Path | Responsibility |
|---|---|
| `orchestrator/config/__init__.py` | namespace (empty) |
| `orchestrator/config/catalog.yml` | dados curados — 3 perfis + 4 templates + fallback |
| `orchestrator/core/catalog.py` | Pydantic models, `load_catalog()`, errors |
| `orchestrator/api/catalog.py` | rota `GET /api/catalog` |
| `tests/unit/test_catalog.py` | Pydantic + load + validation |
| `tests/unit/test_tasks_create_with_template.py` | resolução server-side |
| `tests/unit/test_aijail_spawn_args.py` | write_aijail_config + spawn args |
| `tests/integration/test_api_catalog.py` | GET /api/catalog |
| `tests/integration/test_api_tasks_template.py` | POST /api/tasks com template |
| `tests/integration/test_sessions_uses_profile.py` | E2E backend: profile aplica no spawn |
| `tests/e2e/test_f7_create_task_with_template.py` | Playwright host-only |
| `ui/src/hooks/useCatalog.ts` | TanStack Query hook (staleTime: Infinity) |
| `ui/src/hooks/useCatalog.test.tsx` | unit |
| `docs/adr/0021-catalog-yaml-curado-templates-perfis.md` | Nygard PT-BR |

### Files to modify

| Path | What |
|---|---|
| `orchestrator/api/_deps.py` | add `resolve_catalog` |
| `orchestrator/main.py` | load catalog in lifespan; wire `app.state.catalog`; include `catalog_router` |
| `orchestrator/core/tasks.py` | `create_task` aceita `template` + `catalog`; resolve prefix + permission_profile |
| `orchestrator/api/tasks.py` | `TaskCreatePayload.template` field; `post_task` injeta `catalog`; `post_task_session` injeta `catalog` |
| `orchestrator/core/sessions.py` | `start_session` aceita `catalog`, passa adiante |
| `orchestrator/api/bootstrap.py` | passa `permission_profile=None, catalog=catalog` ao spawnar bootstrap session |
| `orchestrator/sandbox/runtime.py` | `SessionRuntime.spawn` Protocol ganha `permission_profile` + `catalog` (required kwargs) |
| `orchestrator/sandbox/aijail.py` | `write_aijail_config` + `AiJailRuntime.spawn` consomem catalog |
| `orchestrator/sandbox/null.py` | `NullSessionRuntime.spawn` aceita novos kwargs (ignora) |
| `ui/src/lib/api.ts` | tipos Catalog + `getCatalog()` + `TaskCreatePayload.template` |
| `ui/src/lib/query-keys.ts` | `catalog: ['catalog']` |
| `ui/src/components/NewTaskForm.tsx` | dropdown de template + hint dinâmico |
| `ui/src/components/NewTaskForm.test.tsx` | testes do dropdown |
| `ui/src/components/TaskCard.tsx` | badges quando template/permission_profile não-NULL |
| `ui/src/components/TaskCard.test.tsx` | assert badges |
| `ui/src/components/TaskDetailModal.tsx` | seção Configuração |
| `ui/src/components/TaskDetailModal.test.tsx` | assert seção |
| `ARCHITECTURE.md` | §11 F7 ✅; §13 ADR-0021 |
| `docs/adr/README.md` | entry pra ADR-0021 |

---

## Task F7.a — Catálogo + Pydantic + load_catalog

**Files:**
- Create: `orchestrator/config/__init__.py`
- Create: `orchestrator/config/catalog.yml`
- Create: `orchestrator/core/catalog.py`
- Create: `tests/unit/test_catalog.py`

- [ ] **Step 1: Criar namespace de config**

```bash
mkdir -p orchestrator/config
```

Write `orchestrator/config/__init__.py` com 1 linha:

```python
"""Configuração curada do daemon (catálogo de templates/perfis)."""
```

- [ ] **Step 2: Escrever catalog.yml**

Write `orchestrator/config/catalog.yml`:

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

- [ ] **Step 3: Escrever testes do Catalog (TDD)**

Write `tests/unit/test_catalog.py`:

```python
"""F7.a: Pydantic Catalog + load_catalog."""
from pathlib import Path

import pytest

from orchestrator.core.catalog import (
    Catalog,
    CatalogValidationError,
    load_catalog,
)


_VALID_YAML = """
version: "1"
fallback_permission_profile: yolo
permission_profiles:
  yolo: {description: "Y", claude_args: ["--dangerously-skip-permissions"]}
  default: {description: "D", claude_args: []}
templates:
  frontend:
    description: "F"
    default_permission_profile: yolo
    branch_prefix: "feat-ui/"
"""


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "catalog.yml"
    p.write_text(body)
    return p


def test_load_valid_catalog(tmp_path: Path) -> None:
    cat = load_catalog(_write(tmp_path, _VALID_YAML))
    assert isinstance(cat, Catalog)
    assert cat.fallback_permission_profile == "yolo"
    assert "yolo" in cat.permission_profiles
    assert cat.templates["frontend"].branch_prefix == "feat-ui/"


def test_fallback_dangling_raises(tmp_path: Path) -> None:
    bad = _VALID_YAML.replace("fallback_permission_profile: yolo",
                              "fallback_permission_profile: ghost")
    with pytest.raises(CatalogValidationError, match="fallback"):
        load_catalog(_write(tmp_path, bad))


def test_template_default_profile_dangling_raises(tmp_path: Path) -> None:
    bad = _VALID_YAML.replace("default_permission_profile: yolo",
                              "default_permission_profile: ghost")
    with pytest.raises(CatalogValidationError, match="ghost"):
        load_catalog(_write(tmp_path, bad))


def test_extra_field_forbidden(tmp_path: Path) -> None:
    bad = _VALID_YAML.replace("templates:", "extra_field: 42\ntemplates:")
    with pytest.raises(Exception, match="extra"):  # ValidationError
        load_catalog(_write(tmp_path, bad))


def test_branch_prefix_without_slash_rejected(tmp_path: Path) -> None:
    bad = _VALID_YAML.replace('branch_prefix: "feat-ui/"',
                              'branch_prefix: "feat-ui"')
    with pytest.raises(Exception, match="branch_prefix|pattern"):
        load_catalog(_write(tmp_path, bad))


def test_branch_prefix_multi_segment_rejected(tmp_path: Path) -> None:
    bad = _VALID_YAML.replace('branch_prefix: "feat-ui/"',
                              'branch_prefix: "feat/ui/"')
    with pytest.raises(Exception, match="branch_prefix|pattern"):
        load_catalog(_write(tmp_path, bad))


def test_version_must_be_1(tmp_path: Path) -> None:
    bad = _VALID_YAML.replace('version: "1"', 'version: "2"')
    with pytest.raises(Exception, match="version"):
        load_catalog(_write(tmp_path, bad))


def test_profile_name_must_match_regex(tmp_path: Path) -> None:
    # "Yolo" capitalized — regex demands ^[a-z][a-z0-9-]*$
    bad = _VALID_YAML.replace("yolo:", "Yolo:")
    with pytest.raises(CatalogValidationError, match="name"):
        load_catalog(_write(tmp_path, bad))


def test_template_name_must_match_regex(tmp_path: Path) -> None:
    bad = _VALID_YAML.replace("frontend:", "FrontEnd:")
    with pytest.raises(CatalogValidationError, match="name"):
        load_catalog(_write(tmp_path, bad))


def test_load_nonexistent_path_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_catalog(tmp_path / "nope.yml")


def test_real_catalog_yml_is_valid() -> None:
    """A fonte curada em orchestrator/config/catalog.yml deve carregar
    sem erros. Caso contrário daemon não sobe."""
    repo_root = Path(__file__).resolve().parents[2]
    cat = load_catalog(repo_root / "orchestrator" / "config" / "catalog.yml")
    assert set(cat.templates.keys()) == {"frontend", "backend", "refactor", "bugfix"}
    assert set(cat.permission_profiles.keys()) == {"yolo", "default", "read-only"}
    assert cat.fallback_permission_profile == "yolo"
```

- [ ] **Step 4: Rodar testes — devem falhar (módulo não existe)**

Run:

```bash
uv run pytest tests/unit/test_catalog.py -v
```

Expected: FAIL com `ModuleNotFoundError: No module named 'orchestrator.core.catalog'`

- [ ] **Step 5: Implementar Catalog + load_catalog**

Write `orchestrator/core/catalog.py`:

```python
"""F7: catálogo curado de templates + perfis de permissão."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class CatalogValidationError(Exception):
    """Catálogo malformado em load-time. Daemon recusa subir."""


_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")


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
    def _validate(self) -> Self:
        for name in self.permission_profiles:
            if not _NAME_RE.match(name):
                raise CatalogValidationError(
                    f"permission_profile name {name!r} must match {_NAME_RE.pattern}"
                )
        for name in self.templates:
            if not _NAME_RE.match(name):
                raise CatalogValidationError(
                    f"template name {name!r} must match {_NAME_RE.pattern}"
                )
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
    """Lê YAML, valida via Pydantic + cross-field refs. Raise
    `FileNotFoundError` se ausente, `CatalogValidationError` se inválido."""
    raw = yaml.safe_load(path.read_text())
    try:
        return Catalog.model_validate(raw)
    except ValidationError as exc:
        raise CatalogValidationError(str(exc)) from exc
```

- [ ] **Step 6: Rodar testes — devem passar**

Run:

```bash
uv run pytest tests/unit/test_catalog.py -v
```

Expected: PASS (11 testes verdes)

- [ ] **Step 7: Coverage gate**

Run:

```bash
uv run pytest tests/unit/test_catalog.py --cov=orchestrator/core/catalog --cov-report=term-missing
```

Expected: 100% coverage em `orchestrator/core/catalog.py`.

- [ ] **Step 8: Definir `_TEST_CATALOG` em conftest.py (fixture compartilhada)**

Edit `tests/conftest.py` (raiz dos testes — pode ser que não exista; se não, crie). Adicionar:

```python
"""Test-wide fixtures."""
from pathlib import Path

import pytest

from orchestrator.core.catalog import Catalog, load_catalog


_REPO_ROOT = Path(__file__).resolve().parents[1]
_TEST_CATALOG: Catalog | None = None


def _get_test_catalog() -> Catalog:
    global _TEST_CATALOG
    if _TEST_CATALOG is None:
        _TEST_CATALOG = load_catalog(_REPO_ROOT / "orchestrator" / "config" / "catalog.yml")
    return _TEST_CATALOG


@pytest.fixture
def catalog() -> Catalog:
    """Pytest fixture exposing the real catalog.yml for tests that call
    `create_task` or `start_session` directly (bypassing the API DI)."""
    return _get_test_catalog()
```

Se `tests/conftest.py` já existe (verificar antes), adicione só as imports e definições novas; preserve o existente.

Run a quick smoke:

```bash
uv run pytest tests/unit/test_catalog.py -v
```

Should still pass.

- [ ] **Step 9: Commit**

```bash
git add orchestrator/config/__init__.py orchestrator/config/catalog.yml \
        orchestrator/core/catalog.py tests/unit/test_catalog.py tests/conftest.py
git commit -m "feat(F7.a): Catalog Pydantic + load_catalog + catalog.yml curado"
```

---

## Task F7.b — GET /api/catalog + DI + lifespan wiring

**Files:**
- Create: `orchestrator/api/catalog.py`
- Modify: `orchestrator/api/_deps.py` (add `resolve_catalog`)
- Modify: `orchestrator/main.py` (load + wire + include router)
- Create: `tests/integration/test_api_catalog.py`

- [ ] **Step 1: Escrever teste de integração (TDD)**

Write `tests/integration/test_api_catalog.py`:

```python
"""F7.b: GET /api/catalog."""
from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.main import create_app
from orchestrator.store.database import Database
from tests.integration.conftest import FakeSessionRuntime


@pytest.mark.integration
async def test_get_catalog_returns_full_structure(
    db: Database, runtime: FakeSessionRuntime,
) -> None:
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/catalog")
    assert r.status_code == 200
    body: dict[str, Any] = r.json()
    assert body["version"] == "1"
    assert body["fallback_permission_profile"] == "yolo"
    # Shape: dicts viraram listas com `name` adicionado
    assert isinstance(body["permission_profiles"], list)
    assert isinstance(body["templates"], list)
    profile_names = [p["name"] for p in body["permission_profiles"]]
    assert profile_names == sorted(profile_names)  # ordem alfabética
    assert set(profile_names) == {"yolo", "default", "read-only"}
    template_names = [t["name"] for t in body["templates"]]
    assert set(template_names) == {"frontend", "backend", "refactor", "bugfix"}
    # Pin do shape: cada profile tem description + claude_args
    yolo = next(p for p in body["permission_profiles"] if p["name"] == "yolo")
    assert yolo["claude_args"] == ["--dangerously-skip-permissions"]
    assert isinstance(yolo["description"], str)
    # Pin do shape: cada template tem description + default_permission_profile + branch_prefix
    fe = next(t for t in body["templates"] if t["name"] == "frontend")
    assert fe["default_permission_profile"] == "yolo"
    assert fe["branch_prefix"] == "feat-ui/"


@pytest.mark.integration
async def test_get_catalog_no_auth_required(
    db: Database, runtime: FakeSessionRuntime,
) -> None:
    """Catálogo é leitura pública (read-only, sem dados sensíveis)."""
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/catalog")
    assert r.status_code == 200
```

- [ ] **Step 2: Rodar teste — deve falhar (rota não existe)**

Run:

```bash
uv run pytest tests/integration/test_api_catalog.py -v
```

Expected: FAIL com 404 no GET /api/catalog.

- [ ] **Step 3: Adicionar `resolve_catalog` em _deps.py**

Edit `orchestrator/api/_deps.py` — add at the end:

```python
from orchestrator.core.catalog import Catalog


def resolve_catalog(request: Request) -> "Catalog":
    cat: Catalog | None = request.app.state.catalog
    if cat is None:  # pragma: no cover
        raise RuntimeError("catalog not configured in app.state")
    return cat
```

Also add `from orchestrator.core.catalog import Catalog` to the imports list at the top (it's fine if duplicated — consolidate as you prefer).

- [ ] **Step 4: Criar a rota**

Write `orchestrator/api/catalog.py`:

```python
"""F7.b: GET /api/catalog — read-only public listing."""
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from orchestrator.api._deps import resolve_catalog
from orchestrator.core.catalog import Catalog


router = APIRouter(tags=["catalog"])


def _serialize(catalog: Catalog) -> dict[str, Any]:
    """Transforma dicts em listas ordenadas por name. UI espera arrays."""
    profiles = [
        {"name": name, "description": spec.description, "claude_args": spec.claude_args}
        for name, spec in sorted(catalog.permission_profiles.items())
    ]
    templates = [
        {
            "name": name,
            "description": spec.description,
            "default_permission_profile": spec.default_permission_profile,
            "branch_prefix": spec.branch_prefix,
        }
        for name, spec in sorted(catalog.templates.items())
    ]
    return {
        "version": catalog.version,
        "fallback_permission_profile": catalog.fallback_permission_profile,
        "permission_profiles": profiles,
        "templates": templates,
    }


@router.get("/catalog")
async def get_catalog(
    catalog: Annotated[Catalog, Depends(resolve_catalog)],
) -> dict[str, Any]:
    return _serialize(catalog)
```

- [ ] **Step 5: Carregar catálogo no lifespan + incluir router**

Edit `orchestrator/main.py`:

1. Add imports at the top (near the other `orchestrator.*` imports):

```python
from orchestrator.api.catalog import router as catalog_router
from orchestrator.core.catalog import Catalog, load_catalog
```

2. Inside `create_app`, **AFTER** `app = FastAPI(...)` line AND **AFTER** the other `app.state.*` assignments (same pattern as `app.state.docker_ops`). Find the block in `main.py:60-70` and append:

```python
    # F7: catálogo curado (templates + perfis). Carregado 1x no startup;
    # daemon recusa subir se inválido.
    catalog_path = Path(__file__).parent / "config" / "catalog.yml"
    app.state.catalog = (
        getattr(app.state, "catalog", None) or load_catalog(catalog_path)
    )
```

Tests can pre-set `app.state.catalog` BEFORE `create_app` is called to inject a fake — the `getattr(...) or ...` guard preserves a pre-set value.

3. Include the catalog router in the `if database is not None:` block, next to other `app.include_router(...)` calls:

```python
        app.include_router(catalog_router, prefix="/api")
```

- [ ] **Step 6: Confirmar conftest expõe catalog via create_app default**

Read `tests/integration/conftest.py` and check whether the `create_app` call in fixtures pre-sets `app.state.catalog`. If not, the default `load_catalog(orchestrator/config/catalog.yml)` runs — that's what the test depends on. No change needed if no fixture stubs `app.state.catalog` before `create_app`.

If you find an existing fixture that monkeypatches `app.state.*`, you may need to set `app.state.catalog = load_catalog(...)` explicitly. Run the test in Step 7 — if it fails with `catalog not configured`, add the explicit wiring.

- [ ] **Step 7: Rodar teste — deve passar**

Run:

```bash
uv run pytest tests/integration/test_api_catalog.py -v
```

Expected: PASS (2 testes verdes)

- [ ] **Step 8: Coverage check**

Run:

```bash
uv run pytest tests/integration/test_api_catalog.py \
    --cov=orchestrator/api/catalog --cov=orchestrator/api/_deps \
    --cov-report=term-missing
```

Expected: 100% novo código (lines em `api/catalog.py` e a nova função em `_deps.py`). `resolve_catalog`'s `# pragma: no cover` cobre o defensive branch.

- [ ] **Step 9: Commit**

```bash
git add orchestrator/api/catalog.py orchestrator/api/_deps.py \
        orchestrator/main.py tests/integration/test_api_catalog.py
git commit -m "feat(F7.b): GET /api/catalog + resolve_catalog DI + lifespan wiring"
```

---

## Task F7.c — create_task aceita template; resolve prefix + permission_profile

**Files:**
- Modify: `orchestrator/core/tasks.py`
- Modify: `orchestrator/api/tasks.py`
- Create: `tests/unit/test_tasks_create_with_template.py`
- Create: `tests/integration/test_api_tasks_template.py`

- [ ] **Step 1: Escrever testes unit (TDD)**

Write `tests/unit/test_tasks_create_with_template.py`:

```python
"""F7.c: create_task com template resolve prefix + permission_profile."""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.core.catalog import Catalog, load_catalog
from orchestrator.core.slug import InvalidBranchSlugError
from orchestrator.core.tasks import (
    InvalidTemplateError,
    ProjectNotFoundForTaskError,
    create_task,
)
from orchestrator.store.models import Project


_CATALOG: Catalog | None = None


def _catalog() -> Catalog:
    global _CATALOG
    if _CATALOG is None:
        from pathlib import Path
        repo_root = Path(__file__).resolve().parents[2]
        _CATALOG = load_catalog(repo_root / "orchestrator" / "config" / "catalog.yml")
    return _CATALOG


@pytest.mark.unit
async def test_create_task_without_template_stays_null(
    db_session: AsyncSession,
) -> None:
    proj = Project(id="p1", name="p", path="/tmp/p")
    db_session.add(proj)
    await db_session.commit()
    task = await create_task(
        db_session,
        project_id="p1", title="hello world",
        description="", branch=None,
        template=None, catalog=_catalog(),
    )
    assert task.template is None
    assert task.permission_profile is None
    assert task.branch is None  # branch deferred to first session start (F1 behavior)


@pytest.mark.unit
async def test_create_task_with_template_resolves_prefix_and_profile(
    db_session: AsyncSession,
) -> None:
    proj = Project(id="p1", name="p", path="/tmp/p")
    db_session.add(proj)
    await db_session.commit()
    task = await create_task(
        db_session,
        project_id="p1", title="Fix logout race",
        description="", branch=None,
        template="bugfix", catalog=_catalog(),
    )
    assert task.template == "bugfix"
    assert task.permission_profile == "yolo"  # bugfix.default_permission_profile
    assert task.branch == "fix/fix-logout-race"


@pytest.mark.unit
async def test_create_task_with_template_and_branch_override(
    db_session: AsyncSession,
) -> None:
    """Branch explícito sempre literal, nunca aplica prefix."""
    proj = Project(id="p1", name="p", path="/tmp/p")
    db_session.add(proj)
    await db_session.commit()
    task = await create_task(
        db_session,
        project_id="p1", title="anything",
        description="", branch="my-custom-branch",
        template="frontend", catalog=_catalog(),
    )
    assert task.template == "frontend"
    assert task.permission_profile == "yolo"
    assert task.branch == "my-custom-branch"  # NO prefix applied


@pytest.mark.unit
async def test_create_task_with_template_and_branch_starting_with_prefix(
    db_session: AsyncSession,
) -> None:
    """Even if branch happens to start with prefix, it's literal."""
    proj = Project(id="p1", name="p", path="/tmp/p")
    db_session.add(proj)
    await db_session.commit()
    task = await create_task(
        db_session,
        project_id="p1", title="anything",
        description="", branch="feat-ui/already-prefixed",
        template="frontend", catalog=_catalog(),
    )
    assert task.branch == "feat-ui/already-prefixed"  # no double-prefix


@pytest.mark.unit
async def test_create_task_invalid_template_raises(
    db_session: AsyncSession,
) -> None:
    proj = Project(id="p1", name="p", path="/tmp/p")
    db_session.add(proj)
    await db_session.commit()
    with pytest.raises(InvalidTemplateError) as exc:
        await create_task(
            db_session,
            project_id="p1", title="t",
            description="", branch=None,
            template="ghost", catalog=_catalog(),
        )
    assert "ghost" in str(exc.value)
    assert set(exc.value.valid_templates) == {"frontend", "backend", "refactor", "bugfix"}


@pytest.mark.unit
async def test_create_task_degenerate_title_with_template_raises(
    db_session: AsyncSession,
) -> None:
    """Título que slugify falha → InvalidBranchSlugError (mesmo path F1+)."""
    proj = Project(id="p1", name="p", path="/tmp/p")
    db_session.add(proj)
    await db_session.commit()
    with pytest.raises(InvalidBranchSlugError):
        await create_task(
            db_session,
            project_id="p1", title="!!!",
            description="", branch=None,
            template="frontend", catalog=_catalog(),
        )


@pytest.mark.unit
async def test_create_task_template_without_project_raises_first(
    db_session: AsyncSession,
) -> None:
    """Order check: project validation primeiro, template depois."""
    with pytest.raises(ProjectNotFoundForTaskError):
        await create_task(
            db_session,
            project_id="ghost-p", title="t",
            description="", branch=None,
            template="frontend", catalog=_catalog(),
        )
```

- [ ] **Step 2: Rodar testes — devem falhar**

Run:

```bash
uv run pytest tests/unit/test_tasks_create_with_template.py -v
```

Expected: FAIL — `InvalidTemplateError` não existe; `create_task` não aceita `template`/`catalog` kwargs.

- [ ] **Step 3: Adicionar InvalidTemplateError + atualizar create_task**

Edit `orchestrator/core/tasks.py`:

1. Adicionar nova exception class (perto das outras `*Error` no topo):

```python
class InvalidTemplateError(Exception):
    """`template` passed to create_task is not in catalog."""
    def __init__(self, template: str, valid_templates: list[str]) -> None:
        super().__init__(
            f"template {template!r} not in catalog; valid: {sorted(valid_templates)}"
        )
        self.template = template
        self.valid_templates = sorted(valid_templates)
```

2. Atualizar assinatura e corpo de `create_task`. Adicionar import no topo:

```python
from orchestrator.core.catalog import Catalog
from orchestrator.core.slug import slugify_for_branch
```

3. Mudar a função. **Ordem explícita das validações** (preservar EXATAMENTE):

```
1. Title validation (InvalidTaskTitleError)
2. Branch override validation se branch is not None (InvalidBranchOverrideError)
3. [F7 NEW] Template resolution se template is not None
   → InvalidTemplateError (template não existe no catalog)
   → InvalidBranchSlugError (slugify_for_branch falha em title degenerado)
4. Project lookup (ProjectNotFoundForTaskError)
5. Task(...) construct com template + permission_profile populados
6. db.add + commit + refresh + return
```

Read `orchestrator/core/tasks.py:74-104` (atual `create_task`) end-to-end. Aplique os 3 deltas exatos:

**Delta A** — assinatura (adicionar 2 kwargs após `branch`):

```python
async def create_task(
    db: AsyncSession,
    *,
    project_id: str,
    title: str,
    description: str = "",
    branch: str | None = None,
    template: str | None = None,        # NEW
    catalog: Catalog,                   # NEW (required, no default)
) -> Task:
```

**Delta B** — inserir bloco F7 ENTRE branch override validation E project lookup (entre os passos 2 e 4 da ordem acima):

```python
    # F7: resolver template (se fornecido). Roda APÓS validação de branch
    # override e ANTES do project lookup pra falhar barato em template inválido.
    permission_profile: str | None = None
    if template is not None:
        if template not in catalog.templates:
            raise InvalidTemplateError(template, list(catalog.templates.keys()))
        tspec = catalog.templates[template]
        permission_profile = tspec.default_permission_profile
        if branch is None:
            # slugify_for_branch raises InvalidBranchSlugError para títulos degenerados
            branch = f"{tspec.branch_prefix}{slugify_for_branch(title)}"
```

**Delta C** — no `Task(...)` constructor adicionar os 2 campos novos. Substituir:

```python
    task = Task(
        id=uuid4().hex,
        project_id=project_id,
        title=title,
        description=description,
        state="idea",
        branch=branch,
    )
```

por:

```python
    task = Task(
        id=uuid4().hex,
        project_id=project_id,
        title=title,
        description=description,
        state="idea",
        branch=branch,
        template=template,                       # NEW
        permission_profile=permission_profile,   # NEW
    )
```

Nada mais muda (db.add, commit, refresh, return permanecem). Validação ordering pin: F7.c test 7 (`test_create_task_template_without_project_raises_first`) **vai falhar** se template resolution rodar antes de project lookup pra `title="t" + template="frontend" + project=ghost`. Na ordem correta acima, slugify de "t" sucede ("t"), template resolution sucede (branch="feat-ui/t"), mas project lookup falha → `ProjectNotFoundForTaskError` raised. Test passa.

- [ ] **Step 4: Atualizar callers em api/tasks.py**

Edit `orchestrator/api/tasks.py`:

1. Adicionar import:

```python
from orchestrator.api._deps import resolve_catalog
from orchestrator.core.catalog import Catalog
from orchestrator.core.tasks import (
    # ... outros imports ...
    InvalidTemplateError,
)
```

2. Estender `TaskCreatePayload`:

```python
class TaskCreatePayload(BaseModel):
    project_id: str
    title: str
    description: str = ""
    branch: str | None = None
    template: str | None = None  # NEW
```

3. Atualizar `post_task` pra receber catalog e capturar novas exceções. **Ordem dos except blocks importa** (mais específico primeiro):

```python
@router.post("", status_code=201, response_model=TaskRead)
async def post_task(
    payload: TaskCreatePayload,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    catalog: Annotated[Catalog, Depends(resolve_catalog)],  # NEW
) -> TaskRead:
    try:
        task = await create_task(
            db,
            project_id=payload.project_id,
            title=payload.title,
            description=payload.description,
            branch=payload.branch,
            template=payload.template,     # NEW
            catalog=catalog,               # NEW
        )
    except (InvalidTaskTitleError, InvalidBranchOverrideError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InvalidTemplateError as exc:  # NEW — específico, structured detail
        raise HTTPException(
            status_code=422,
            detail={"error": "template_not_in_catalog",
                    "message": str(exc),
                    "valid_templates": exc.valid_templates},
        ) from exc
    except InvalidBranchSlugError as exc:  # NEW — pode disparar em template+title degenerado
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ProjectNotFoundForTaskError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    # ... resto idêntico (broadcaster.publish etc) ...
```

Imports necessários (adicionar se não existe):

```python
from orchestrator.core.slug import InvalidBranchSlugError
```

- [ ] **Step 5: Rodar testes unit — devem passar**

Run:

```bash
uv run pytest tests/unit/test_tasks_create_with_template.py -v
```

Expected: PASS (7 testes verdes)

- [ ] **Step 6: Escrever teste integration**

Write `tests/integration/test_api_tasks_template.py`:

```python
"""F7.c: POST /api/tasks com template."""
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.main import create_app
from orchestrator.store.database import Database
from tests.integration.conftest import FakeSessionRuntime, _make_repo


@pytest.mark.integration
async def test_post_task_with_template_frontend(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        proj = (await c.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        r = await c.post("/api/tasks", json={
            "project_id": proj["id"],
            "title": "Add dark mode toggle",
            "template": "frontend",
        })
    assert r.status_code == 201
    body = r.json()
    assert body["template"] == "frontend"
    assert body["permission_profile"] == "yolo"
    assert body["branch"] == "feat-ui/add-dark-mode-toggle"


@pytest.mark.integration
async def test_post_task_without_template_back_compat(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        proj = (await c.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        r = await c.post("/api/tasks", json={"project_id": proj["id"], "title": "t"})
    assert r.status_code == 201
    body = r.json()
    assert body["template"] is None
    assert body["permission_profile"] is None
    assert body["branch"] is None


@pytest.mark.integration
async def test_post_task_invalid_template_422(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        proj = (await c.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        r = await c.post("/api/tasks", json={
            "project_id": proj["id"], "title": "t", "template": "ghost",
        })
    assert r.status_code == 422
    body = r.json()
    assert body["detail"]["error"] == "template_not_in_catalog"
    assert set(body["detail"]["valid_templates"]) == {"frontend", "backend", "refactor", "bugfix"}


@pytest.mark.integration
async def test_post_task_template_with_branch_override(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        proj = (await c.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        r = await c.post("/api/tasks", json={
            "project_id": proj["id"], "title": "anything",
            "template": "frontend", "branch": "custom-branch",
        })
    assert r.status_code == 201
    body = r.json()
    assert body["template"] == "frontend"
    assert body["permission_profile"] == "yolo"
    assert body["branch"] == "custom-branch"  # literal, prefix ignored


@pytest.mark.integration
async def test_post_task_template_with_degenerate_title_422(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        proj = (await c.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        r = await c.post("/api/tasks", json={
            "project_id": proj["id"], "title": "!!!", "template": "frontend",
        })
    assert r.status_code == 422
    assert "slugify" in r.text.lower() or "slug" in r.text.lower()


@pytest.mark.integration
async def test_post_task_template_duplicate_branch_accepted(
    db: Database, runtime: FakeSessionRuntime, tmp_path: Path,
) -> None:
    """POST aceita branches que slugificam pro mesmo prefix+slug. Collision
    é detectada só em start_session (CwdAlreadyExistsError de F5)."""
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        proj = (await c.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        r1 = await c.post("/api/tasks", json={
            "project_id": proj["id"], "title": "Fix logout", "template": "bugfix",
        })
        r2 = await c.post("/api/tasks", json={
            "project_id": proj["id"], "title": "Fix logout", "template": "bugfix",
        })
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["branch"] == r2.json()["branch"] == "fix/fix-logout"
```

- [ ] **Step 7: Rodar integration tests — devem passar**

Run:

```bash
uv run pytest tests/integration/test_api_tasks_template.py -v
```

Expected: PASS (6 testes verdes)

- [ ] **Step 8: Atualizar callers de `create_task` nos testes existentes**

Tests que chamam `create_task` direto precisam do novo `catalog=` kwarg. Use a fixture `catalog` adicionada em F7.a step 8 (ou import `_get_test_catalog` se em local que não tem acesso à fixture).

**Arquivos a editar** (cada um precisa `catalog=catalog` ou `catalog=_get_test_catalog()` em cada chamada de `create_task`):

- `tests/unit/test_task_crud.py`
- `tests/unit/test_task_title_validation.py`
- `tests/unit/test_task_branch_validation.py`
- `tests/unit/test_project_delete_blocked.py`
- `tests/unit/test_task_auto_transition.py`
- `tests/unit/test_session_per_task_lock.py`
- `tests/unit/test_session_token_lifecycle.py`
- `tests/unit/test_session_start_atomic.py`
- `tests/unit/test_session_start_re_iniciar.py`
- `tests/unit/test_session_start_branch_clash.py`
- `tests/unit/test_session_start_no_worktree_id.py`
- `tests/unit/test_bootstrap_watcher.py`
- `tests/integration/test_branch_override_field.py`

Padrão de fix em cada um (assumindo que test function já recebe `db_session`/`db`):

```python
async def test_xyz(db_session: AsyncSession, catalog: Catalog) -> None:
    ...
    task = await create_task(
        db_session,
        project_id="p1", title="t",
        description="", branch=None,
        template=None,
        catalog=catalog,    # NEW
    )
```

Import (se ainda não tiver): `from orchestrator.core.catalog import Catalog`.

Run após cada arquivo editado:

```bash
uv run pytest <arquivo> -v
```

- [ ] **Step 9: Rodar todo o suite backend pra confirmar back-compat**

Run:

```bash
uv run pytest tests/unit tests/integration -v --no-header
```

Expected: todos os ~440 testes anteriores + os 13 novos verdes. Se algum falhar com "missing keyword argument 'catalog'", é caller esquecido — adicione `catalog=catalog`.

- [ ] **Step 10: Commit**

```bash
git add orchestrator/core/tasks.py orchestrator/api/tasks.py \
        tests/unit/test_tasks_create_with_template.py \
        tests/integration/test_api_tasks_template.py \
        tests/unit/test_task_crud.py \
        tests/unit/test_task_title_validation.py \
        tests/unit/test_task_branch_validation.py \
        tests/unit/test_project_delete_blocked.py \
        tests/unit/test_task_auto_transition.py \
        tests/unit/test_session_per_task_lock.py \
        tests/unit/test_session_token_lifecycle.py \
        tests/unit/test_session_start_atomic.py \
        tests/unit/test_session_start_re_iniciar.py \
        tests/unit/test_session_start_branch_clash.py \
        tests/unit/test_session_start_no_worktree_id.py \
        tests/unit/test_bootstrap_watcher.py \
        tests/integration/test_branch_override_field.py
git commit -m "feat(F7.c): create_task aceita template; resolve prefix + permission_profile

Update 13 test files to pass catalog= kwarg per new required signature."
```

---

## Task F7.d — write_aijail_config + AiJailRuntime.spawn consomem catalog

**Files:**
- Modify: `orchestrator/sandbox/runtime.py` (Protocol signature)
- Modify: `orchestrator/sandbox/aijail.py` (write_aijail_config + spawn)
- Modify: `orchestrator/sandbox/null.py` (NullSessionRuntime accepts new kwargs)
- Modify: `orchestrator/core/sessions.py` (start_session passa catalog)
- Modify: `orchestrator/api/tasks.py` (post_task_session injeta catalog)
- Modify: `orchestrator/api/bootstrap.py` (bootstrap passa permission_profile=None + catalog)
- Create: `tests/unit/test_aijail_spawn_args.py`
- Create: `tests/integration/test_sessions_uses_profile.py`

- [ ] **Step 1: Atualizar SessionRuntime Protocol**

Edit `orchestrator/sandbox/runtime.py`. Find the `SessionRuntime` Protocol and add new required kwargs:

```python
from orchestrator.core.catalog import Catalog


class SessionRuntime(Protocol):
    async def spawn(
        self,
        worktree: Path,
        *,
        permission_profile: str | None,  # NEW required
        catalog: Catalog,                # NEW required
        token: str | None = None,
        base_url: str | None = None,
    ) -> JailHandle: ...

    async def kill(self, handle: JailHandle, *, worktree: Path | None = None) -> None: ...
```

If `runtime.py` doesn't define a Protocol explicitly but uses a base class or duck typing, update wherever the `spawn` signature is documented and continue to step 2.

- [ ] **Step 2: Atualizar NullSessionRuntime**

Edit `orchestrator/sandbox/null.py`. Update `spawn` signature to accept and ignore new kwargs:

```python
async def spawn(
    self,
    worktree: Path,
    *,
    permission_profile: str | None = None,  # accept + ignore
    catalog: "Catalog | None" = None,        # accept + ignore
    token: str | None = None,
    base_url: str | None = None,
) -> JailHandle:
    # ... existing impl ...
```

NullSessionRuntime can use defaults (None) — it's a no-op runtime. Real `AiJailRuntime` does NOT default — see step 3.

- [ ] **Step 3: Atualizar write_aijail_config + AiJailRuntime.spawn**

Edit `orchestrator/sandbox/aijail.py`.

1. Add JSON import at top:

```python
import json
```

2. Substituir `write_aijail_config`:

```python
def write_aijail_config(cwd: Path, *, claude_args: list[str]) -> None:
    """Write `<cwd>/.ai-jail` so `ai-jail` (no args) reads it on spawn.

    `claude_args` vem resolvido do perfil de permissão da task (caller
    responsibility). `claude_args=[]` produz `command = ["claude"]`
    (perfil `default`, Claude pergunta a cada tool).
    """
    git_dirs = _discover_git_dirs(cwd)
    rw_lines = ",\n".join(f'    "{p}"' for p in git_dirs)
    rw_block = f"[\n{rw_lines},\n]" if git_dirs else "[]"
    full_argv = ["claude", *claude_args]
    args_json = json.dumps(full_argv)
    (cwd / ".ai-jail").write_text(
        f"command = {args_json}\n"
        f"rw_maps = {rw_block}\n"
        "ro_maps = []\n"
        "hide_dotdirs = []\n"
        "mask = []\n"
        "allow_tcp_ports = []\n"
    )
```

3. Adicionar nova exception perto do topo do módulo (após `NoTerminalFoundError`):

```python
class PermissionProfileNotInCatalogError(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(
            f"permission_profile {name!r} was removed from catalog.yml — "
            f"edite a task ou restaure o perfil"
        )
        self.name = name
```

4. Atualizar `AiJailRuntime.spawn`:

```python
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
    terminal = self._terminal_resolver()
    inner = ["ai-jail"]
    cmd = build_terminal_command(terminal, inner)
    pid = self._process_ops.spawn(cmd, str(worktree))
    return JailHandle(id=uuid4().hex, pid=pid, started_at=datetime.now(UTC))
```

5. Add catalog import at top:

```python
from orchestrator.core.catalog import Catalog
```

- [ ] **Step 4: Escrever testes unit de aijail (TDD)**

Write `tests/unit/test_aijail_spawn_args.py`:

```python
"""F7.d: write_aijail_config consume claude_args + AiJailRuntime resolve catalog."""
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from orchestrator.core.catalog import Catalog, load_catalog
from orchestrator.sandbox.aijail import (
    AiJailRuntime,
    PermissionProfileNotInCatalogError,
    write_aijail_config,
)


def _catalog() -> Catalog:
    repo_root = Path(__file__).resolve().parents[2]
    return load_catalog(repo_root / "orchestrator" / "config" / "catalog.yml")


class _FakeProcessOps:
    def __init__(self) -> None:
        self.spawns: list[tuple[list[str], str]] = []
        self.killed: list[int] = []

    def spawn(self, cmd: list[str], cwd: str) -> int:
        self.spawns.append((cmd, cwd))
        return 12345

    def kill(self, pid: int) -> None:
        self.killed.append(pid)


@pytest.mark.unit
def test_write_aijail_config_yolo_args(tmp_path: Path) -> None:
    write_aijail_config(tmp_path, claude_args=["--dangerously-skip-permissions"])
    text = (tmp_path / ".ai-jail").read_text()
    assert 'command = ["claude", "--dangerously-skip-permissions"]' in text


@pytest.mark.unit
def test_write_aijail_config_empty_args(tmp_path: Path) -> None:
    """Perfil `default` → command = ["claude"]."""
    write_aijail_config(tmp_path, claude_args=[])
    text = (tmp_path / ".ai-jail").read_text()
    assert 'command = ["claude"]' in text


@pytest.mark.unit
def test_write_aijail_config_readonly_args(tmp_path: Path) -> None:
    write_aijail_config(
        tmp_path,
        claude_args=["--permission-mode", "plan", "--allowed-tools", "Read,Grep,Glob,LS"],
    )
    text = (tmp_path / ".ai-jail").read_text()
    assert ('command = ["claude", "--permission-mode", "plan", '
            '"--allowed-tools", "Read,Grep,Glob,LS"]') in text


@pytest.mark.unit
def test_write_aijail_config_preserves_other_keys(tmp_path: Path) -> None:
    write_aijail_config(tmp_path, claude_args=[])
    text = (tmp_path / ".ai-jail").read_text()
    assert "rw_maps = " in text
    assert "ro_maps = []" in text
    assert "hide_dotdirs = []" in text
    assert "mask = []" in text
    assert "allow_tcp_ports = []" in text


@pytest.mark.unit
async def test_aijail_runtime_spawn_resolves_profile(tmp_path: Path) -> None:
    ops = _FakeProcessOps()
    runtime = AiJailRuntime(lambda: "xterm", ops)
    handle = await runtime.spawn(
        tmp_path,
        permission_profile="read-only",
        catalog=_catalog(),
    )
    assert handle.pid == 12345
    text = (tmp_path / ".ai-jail").read_text()
    assert '"--permission-mode", "plan"' in text


@pytest.mark.unit
async def test_aijail_runtime_spawn_none_uses_fallback(tmp_path: Path) -> None:
    """permission_profile=None → fallback do catalog (yolo no nosso catalog.yml)."""
    ops = _FakeProcessOps()
    runtime = AiJailRuntime(lambda: "xterm", ops)
    await runtime.spawn(
        tmp_path,
        permission_profile=None,
        catalog=_catalog(),
    )
    text = (tmp_path / ".ai-jail").read_text()
    assert '"--dangerously-skip-permissions"' in text


@pytest.mark.unit
async def test_aijail_runtime_spawn_stale_profile_raises(tmp_path: Path) -> None:
    """Perfil removido do catalog → PermissionProfileNotInCatalogError."""
    ops = _FakeProcessOps()
    runtime = AiJailRuntime(lambda: "xterm", ops)
    with pytest.raises(PermissionProfileNotInCatalogError, match="ghost"):
        await runtime.spawn(
            tmp_path,
            permission_profile="ghost",
            catalog=_catalog(),
        )
    # No file written, no process spawned
    assert not (tmp_path / ".ai-jail").exists()
    assert ops.spawns == []
```

- [ ] **Step 5: Rodar unit tests — devem passar**

Run:

```bash
uv run pytest tests/unit/test_aijail_spawn_args.py -v
```

Expected: PASS (7 testes verdes)

- [ ] **Step 6: Atualizar start_session pra propagar catalog**

Edit `orchestrator/core/sessions.py`. Adicionar `catalog` param e usar no `runtime.spawn`:

1. Import:

```python
from orchestrator.core.catalog import Catalog
```

2. Atualizar assinatura de `start_session`:

```python
async def start_session(
    db: AsyncSession,
    runtime: SessionRuntime,
    git: GitWorktreeOps,
    *,
    task_id: str,
    token_registry: TokenRegistry,
    base_url: str | None,
    broadcaster: WsBroadcaster | None,
    catalog: Catalog,  # NEW required
) -> ClaudeSession:
    # ... preserve all existing logic ...
```

3. Find the `runtime.spawn(cwd, token=token, base_url=base_url)` line (currently aijail.py:196) and change to:

```python
    handle = await runtime.spawn(
        cwd,
        permission_profile=task.permission_profile,
        catalog=catalog,
        token=token,
        base_url=base_url,
    )
```

- [ ] **Step 7: Atualizar callers em api/tasks.py + api/bootstrap.py**

Edit `orchestrator/api/tasks.py`:

1. Adicionar `catalog: Annotated[Catalog, Depends(resolve_catalog)]` aos params do `post_task_session`:

```python
@router.post("/{task_id}/sessions", status_code=201, response_model=SessionRead)
async def post_task_session(
    task_id: str,
    payload: SessionCreatePayload,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    runtime: Annotated[SessionRuntime, Depends(resolve_runtime)],
    git: Annotated[GitWorktreeOps, Depends(resolve_git_ops)],
    catalog: Annotated[Catalog, Depends(resolve_catalog)],  # NEW
) -> SessionRead:
    # ...
    try:
        row = await start_session(
            db, runtime, git,
            task_id=task_id,
            token_registry=registry,
            base_url=base_url,
            broadcaster=broadcaster,
            catalog=catalog,  # NEW
        )
    except PermissionProfileNotInCatalogError as exc:  # NEW
        raise HTTPException(
            status_code=422,
            detail={"error": "permission_profile_not_in_catalog",
                    "message": str(exc),
                    "profile": exc.name},
        ) from exc
    # ... rest unchanged ...
```

Add import:

```python
from orchestrator.sandbox.aijail import PermissionProfileNotInCatalogError
```

Edit `orchestrator/api/bootstrap.py`. Diff completo:

**Imports** (adicionar):

```python
from orchestrator.api._deps import resolve_catalog
from orchestrator.core.catalog import Catalog
```

**Função `bootstrap_manifest`** (linha ~42-81): adicionar `catalog` kwarg na signature:

```python
@router.post("/tasks/{task_id}/bootstrap-manifest", status_code=202)
async def bootstrap_manifest(
    task_id: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    runtime: Annotated[SessionRuntime, Depends(resolve_runtime)],
    catalog: Annotated[Catalog, Depends(resolve_catalog)],  # NEW
) -> dict[str, str]:
    # ... rest preserved ...
```

**Substituir** a linha 60 (`await runtime.spawn(project_path)`) por:

```python
    await runtime.spawn(
        project_path,
        permission_profile=None,  # bootstrap usa fallback do catálogo
        catalog=catalog,
    )
```

- [ ] **Step 8: Escrever integration tests (sessions usam profile)**

Write `tests/integration/test_sessions_uses_profile.py`:

```python
"""F7.d: sessions consomem permission_profile via catalog no spawn."""
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.core.catalog import Catalog, load_catalog
from orchestrator.main import create_app
from orchestrator.sandbox.aijail import AiJailRuntime
from orchestrator.sandbox.runtime import JailHandle
from orchestrator.store.database import Database
from tests.integration.conftest import _make_repo


class _CapturingProcessOps:
    """Captura argv sem spawnar processo de verdade."""
    def __init__(self) -> None:
        self.spawns: list[tuple[list[str], str]] = []

    def spawn(self, cmd: list[str], cwd: str) -> int:
        self.spawns.append((cmd, cwd))
        return 9999

    def kill(self, pid: int) -> None: pass


def _read_jail_command(cwd: Path) -> str:
    return (cwd / ".ai-jail").read_text().splitlines()[0]


@pytest.mark.integration
async def test_session_with_default_profile_writes_empty_claude_args(
    db: Database, tmp_path: Path,
) -> None:
    """Template refactor → permission_profile=default → claude_args=[]."""
    ops = _CapturingProcessOps()
    runtime = AiJailRuntime(lambda: "xterm", ops)
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        proj = (await c.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        task = (await c.post("/api/tasks", json={
            "project_id": proj["id"], "title": "Explore", "template": "refactor",
        })).json()
        await c.patch(f"/api/tasks/{task['id']}", json={"state": "ready"})
        await c.post(f"/api/tasks/{task['id']}/sessions", json={})

    spawned_cwd = Path(ops.spawns[0][1])
    line = _read_jail_command(spawned_cwd)
    assert line == 'command = ["claude"]'


@pytest.mark.integration
async def test_session_with_read_only_profile_writes_plan_mode(
    db: Database, tmp_path: Path,
) -> None:
    """Cobre o perfil `read-only` explicitamente (spec §9 requer).

    Nenhum template aponta pra read-only no catálogo atual; testamos via
    SQL direto pra setar permission_profile='read-only' na task (admin
    setup ou DB manipulation cenário)."""
    from sqlalchemy import update

    from orchestrator.store.models import Task

    ops = _CapturingProcessOps()
    runtime = AiJailRuntime(lambda: "xterm", ops)
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        proj = (await c.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        task = (await c.post("/api/tasks", json={
            "project_id": proj["id"], "title": "Review pr",
        })).json()
        # Set permission_profile=read-only via DB direto
        async with db.session() as s:
            await s.execute(
                update(Task)
                .where(Task.id == task["id"])
                .values(permission_profile="read-only")
            )
            await s.commit()
        await c.patch(f"/api/tasks/{task['id']}", json={"state": "ready"})
        await c.post(f"/api/tasks/{task['id']}/sessions", json={})

    spawned_cwd = Path(ops.spawns[0][1])
    line = _read_jail_command(spawned_cwd)
    assert '"--permission-mode", "plan"' in line
    assert '"--allowed-tools", "Read,Grep,Glob,LS"' in line


@pytest.mark.integration
async def test_session_back_compat_null_profile_uses_yolo_fallback(
    db: Database, tmp_path: Path,
) -> None:
    """Task sem template (template=NULL, permission_profile=NULL) →
    fallback do catalog = yolo = --dangerously-skip-permissions.
    Idêntico ao comportamento F1-F6."""
    ops = _CapturingProcessOps()
    runtime = AiJailRuntime(lambda: "xterm", ops)
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        proj = (await c.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        task = (await c.post("/api/tasks", json={
            "project_id": proj["id"], "title": "Old style",  # no template
        })).json()
        await c.patch(f"/api/tasks/{task['id']}", json={"state": "ready"})
        await c.post(f"/api/tasks/{task['id']}/sessions", json={})

    spawned_cwd = Path(ops.spawns[0][1])
    line = _read_jail_command(spawned_cwd)
    assert '"--dangerously-skip-permissions"' in line


@pytest.mark.integration
async def test_session_stale_profile_returns_422(
    db: Database, tmp_path: Path,
) -> None:
    """Task com permission_profile='X' onde X foi removido do catálogo
    em runtime — start_session → 422."""
    ops = _CapturingProcessOps()
    runtime = AiJailRuntime(lambda: "xterm", ops)
    repo = _make_repo(tmp_path)

    # Custom catalog SEM 'yolo' (simula admin removendo)
    minimal_catalog_yaml = """
version: "1"
fallback_permission_profile: default
permission_profiles:
  default: {description: "D", claude_args: []}
templates: {}
"""
    cat_path = tmp_path / "stale-catalog.yml"
    cat_path.write_text(minimal_catalog_yaml)
    stale_catalog = load_catalog(cat_path)

    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        # Cria task com catalog REAL (tem yolo)
        proj = (await c.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        task = (await c.post("/api/tasks", json={
            "project_id": proj["id"], "title": "Fix", "template": "bugfix",
        })).json()  # permission_profile=yolo gravado
        await c.patch(f"/api/tasks/{task['id']}", json={"state": "ready"})

        # Substitui catalog em runtime
        app.state.catalog = stale_catalog

        # Tenta start_session → 422 porque 'yolo' não está no catalog atual
        r = await c.post(f"/api/tasks/{task['id']}/sessions", json={})

    assert r.status_code == 422
    body = r.json()
    assert body["detail"]["error"] == "permission_profile_not_in_catalog"
    assert body["detail"]["profile"] == "yolo"
```

- [ ] **Step 9: Atualizar `FakeSessionRuntime` em conftest + start_session callers**

**Parte A:** Edit `tests/integration/conftest.py`. Encontrar `class FakeSessionRuntime` e atualizar `spawn`:

```python
async def spawn(
    self,
    worktree: Path,
    *,
    permission_profile: str | None = None,
    catalog: Any = None,
    token: str | None = None,
    base_url: str | None = None,
) -> JailHandle:
    self.spawned.append((worktree, token, permission_profile))
    return JailHandle(id=uuid4().hex, pid=12345, started_at=datetime.now(UTC))
```

**Parte B:** Tests que chamam `start_session` direto (não via API). Lista enumerada:

- `tests/unit/test_session_per_task_lock.py`
- `tests/unit/test_session_token_lifecycle.py`
- `tests/unit/test_session_start_atomic.py`
- `tests/unit/test_session_start_re_iniciar.py`
- `tests/unit/test_session_start_branch_clash.py`
- `tests/unit/test_session_start_no_worktree_id.py`
- `tests/unit/test_task_auto_transition.py`

Padrão de fix em cada um — adicionar `catalog=catalog` à chamada de `start_session`:

```python
async def test_xyz(db_session, ..., catalog: Catalog) -> None:
    ...
    row = await start_session(
        db, runtime, git,
        task_id=task.id,
        token_registry=registry,
        base_url=None,
        broadcaster=None,
        catalog=catalog,    # NEW
    )
```

Import: `from orchestrator.core.catalog import Catalog` (módulo de teste). A fixture `catalog` veio de `tests/conftest.py` (F7.a step 8).

Run após edits:

```bash
uv run pytest tests/unit tests/integration -v --no-header
```

Expected: todos verdes. Se algum falhar com `TypeError: spawn() got ...` ou `missing keyword 'catalog'`, é caller esquecido — adicione kwarg correspondente.

- [ ] **Step 10: Rodar suite completa**

Run:

```bash
uv run pytest tests/unit tests/integration -v --no-header
```

Expected: todos verdes (incluindo os 3 novos de test_sessions_uses_profile.py + os 7 de test_aijail_spawn_args.py).

- [ ] **Step 11: Coverage check geral**

```bash
uv run pytest tests/unit tests/integration --cov=orchestrator \
    --cov-report=term-missing | tail -40
```

Expected: 100% nos arquivos modificados/criados em F7.a-d.

- [ ] **Step 12: Commit**

```bash
git add orchestrator/sandbox/runtime.py orchestrator/sandbox/aijail.py \
        orchestrator/sandbox/null.py orchestrator/core/sessions.py \
        orchestrator/api/tasks.py orchestrator/api/bootstrap.py \
        tests/unit/test_aijail_spawn_args.py \
        tests/integration/test_sessions_uses_profile.py \
        tests/integration/conftest.py tests/unit/conftest.py
git commit -m "feat(F7.d): write_aijail_config + spawn consomem catalog; PermissionProfileNotInCatalogError → 422"
```

Note: include any conftest files you touched in the commit.

---

## Task F7.e — useCatalog hook + NewTaskForm dropdown

**Files:**
- Create: `ui/src/hooks/useCatalog.ts`
- Create: `ui/src/hooks/useCatalog.test.tsx`
- Modify: `ui/src/lib/api.ts` (types + `getCatalog` + `TaskCreatePayload.template`)
- Modify: `ui/src/lib/query-keys.ts` (`catalog`)
- Modify: `ui/src/components/NewTaskForm.tsx` (dropdown + hint)
- Modify: `ui/src/components/NewTaskForm.test.tsx`

- [ ] **Step 1: Adicionar tipos + endpoint em api.ts**

Edit `ui/src/lib/api.ts`:

```typescript
export type PermissionProfile = {
  name: string;
  description: string;
  claude_args: string[];
};

export type Template = {
  name: string;
  description: string;
  default_permission_profile: string;
  branch_prefix: string;
};

export type Catalog = {
  version: '1';
  fallback_permission_profile: string;
  permission_profiles: PermissionProfile[];
  templates: Template[];
};

export async function getCatalog(): Promise<Catalog> {
  const r = await fetch('/api/catalog');
  if (!r.ok) throw new Error(`GET /api/catalog → ${r.status}`);
  return r.json();
}
```

Atualizar `TaskCreatePayload` (provavelmente já tem `branch?: string`):

```typescript
export type TaskCreatePayload = {
  project_id: string;
  title: string;
  description?: string;
  branch?: string;
  template?: string;  // NEW
};
```

- [ ] **Step 2: Adicionar `catalog` em query-keys.ts**

Edit `ui/src/lib/query-keys.ts`:

```typescript
export const queryKeys = {
  projects: ['projects'] as const,
  worktrees: (projectId: string) => ['worktrees', projectId] as const,
  sessions: ['sessions'] as const,
  tasks: ['tasks'] as const,
  tasksForProject: (projectId: string) => ['tasks', { projectId }] as const,
  task: (taskId: string) => ['tasks', { id: taskId }] as const,
  run: (taskId: string) => ['runs', { taskId }] as const,
  catalog: ['catalog'] as const,  // NEW
};
```

- [ ] **Step 3: Escrever teste do hook (TDD)**

Write `ui/src/hooks/useCatalog.test.tsxx` (extensão `.tsx` porque o wrapper usa JSX):

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useCatalog } from './useCatalog';
import * as api from '../lib/api';
import type { ReactNode } from 'react';

describe('useCatalog', () => {
  let qc: QueryClient;

  beforeEach(() => {
    qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    vi.restoreAllMocks();
  });

  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );

  it('fetches catalog and caches it', async () => {
    const fake: api.Catalog = {
      version: '1',
      fallback_permission_profile: 'yolo',
      permission_profiles: [
        { name: 'yolo', description: 'Y', claude_args: ['--dangerously-skip-permissions'] },
      ],
      templates: [
        { name: 'frontend', description: 'F', default_permission_profile: 'yolo', branch_prefix: 'feat-ui/' },
      ],
    };
    const spy = vi.spyOn(api, 'getCatalog').mockResolvedValue(fake);

    const { result } = renderHook(() => useCatalog(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(fake);

    // staleTime: Infinity → second mount uses cache, no second fetch
    const { result: r2 } = renderHook(() => useCatalog(), { wrapper });
    await waitFor(() => expect(r2.current.isSuccess).toBe(true));
    expect(spy).toHaveBeenCalledTimes(1);
  });
});
```


- [ ] **Step 4: Implementar useCatalog**

Write `ui/src/hooks/useCatalog.ts`:

```typescript
import { useQuery } from '@tanstack/react-query';
import { getCatalog } from '../lib/api';
import { queryKeys } from '../lib/query-keys';

export function useCatalog() {
  return useQuery({
    queryKey: queryKeys.catalog,
    queryFn: getCatalog,
    staleTime: Infinity,  // catálogo só muda com restart do daemon
  });
}
```

- [ ] **Step 5: Rodar teste do hook**

Run:

```bash
cd ui && npx vitest run src/hooks/useCatalog.test.tsx
```

Expected: PASS

- [ ] **Step 6: Atualizar NewTaskForm com dropdown + hint**

Edit `ui/src/components/NewTaskForm.tsx`. Adicionar imports:

```typescript
import { useCatalog } from '../hooks/useCatalog';
// `slugifyForBranch` e `InvalidBranchSlugError` já estão importados pra hint do branch override (linha 4)
// — reutilizar. Se não existirem, adicionar:
// import { slugifyForBranch, InvalidBranchSlugError } from '../lib/slug';

export function NewTaskForm({ projects }: Props) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [branch, setBranch] = useState('');
  const [projectId, setProjectId] = useState(projects[0]?.id ?? '');
  const [template, setTemplate] = useState<string>('');  // NEW
  const create = useCreateTask();
  const catalogQ = useCatalog();
  // ... existing logic ...

  const selectedTemplate = catalogQ.data?.templates.find((t) => t.name === template);

  const templateHint = (() => {
    if (!selectedTemplate) return '';
    if (branch.trim() !== '') return 'Branch override — prefix do template ignorado';
    try {
      return `Branch será: ${selectedTemplate.branch_prefix}${slugifyForBranch(title)}`;
    } catch (e) {
      if (e instanceof InvalidBranchSlugError) return `Branch será: ${selectedTemplate.branch_prefix}<slug-do-título>`;
      throw e;
    }
  })();

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const trimmedBranch = branch.trim();
    create.mutate(
      {
        project_id: projectId,
        title,
        description,
        ...(trimmedBranch && { branch: trimmedBranch }),
        ...(template && { template }),  // NEW
      },
      {
        onSuccess: () => {
          setTitle('');
          setDescription('');
          setBranch('');
          setTemplate('');  // NEW reset
        },
      },
    );
  }

  return (
    <form onSubmit={onSubmit} aria-label="new-task" className="new-task-form">
      {/* ... existing projeto select ... */}
      {/* ... existing título input ... */}

      {/* NEW: template dropdown */}
      <label>
        Template:
        <select
          aria-label="template"
          value={template}
          onChange={(e) => setTemplate(e.target.value)}
        >
          <option value="">(nenhum)</option>
          {catalogQ.data?.templates.map((t) => (
            <option key={t.name} value={t.name} data-template-name={t.name}>
              {t.name} — {t.description}
            </option>
          ))}
        </select>
      </label>
      {templateHint && <p className="hint" aria-label="template-hint">{templateHint}</p>}

      {/* ... existing descrição textarea ... */}
      {/* ... existing details/branch ... */}
      {/* ... submit button ... */}
    </form>
  );
}
```

- [ ] **Step 7: Atualizar testes de NewTaskForm**

Edit `ui/src/components/NewTaskForm.test.tsx`. Confira o `wrap` helper já provê QueryClient (provavelmente sim — useCreateTask já o usa). Adicionar mock do `getCatalog`:

```typescript
import * as api from '../lib/api';
// ... existing imports ...

beforeEach(() => {
  vi.spyOn(api, 'getCatalog').mockResolvedValue({
    version: '1',
    fallback_permission_profile: 'yolo',
    permission_profiles: [
      { name: 'yolo', description: 'Y', claude_args: ['--dangerously-skip-permissions'] },
      { name: 'default', description: 'D', claude_args: [] },
    ],
    templates: [
      { name: 'frontend', description: 'UI', default_permission_profile: 'yolo', branch_prefix: 'feat-ui/' },
      { name: 'bugfix', description: 'Bug', default_permission_profile: 'yolo', branch_prefix: 'fix/' },
    ],
  });
});

it('renders template dropdown with options from catalog', async () => {
  wrap(<NewTaskForm projects={projects} />);
  await waitFor(() => screen.getByText(/frontend/));
  const select = screen.getByLabelText('template') as HTMLSelectElement;
  expect([...select.options].map((o) => o.value)).toEqual(['', 'frontend', 'bugfix']);
});

it('shows branch hint when template + title provided + no branch override', async () => {
  wrap(<NewTaskForm projects={projects} />);
  await waitFor(() => screen.getByText(/frontend/));
  await userEvent.type(screen.getByLabelText('título'), 'Add dark mode');
  await userEvent.selectOptions(screen.getByLabelText('template'), 'frontend');
  expect(screen.getByLabelText('template-hint')).toHaveTextContent('feat-ui/add-dark-mode');
});

it('shows override hint when template + branch typed', async () => {
  wrap(<NewTaskForm projects={projects} />);
  await waitFor(() => screen.getByText(/frontend/));
  await userEvent.selectOptions(screen.getByLabelText('template'), 'frontend');
  // Open <details> if branch field is inside
  const branchInput = screen.getByLabelText('task-branch');
  await userEvent.type(branchInput, 'my-custom');
  expect(screen.getByLabelText('template-hint')).toHaveTextContent('override');
});

it('submit includes template in payload when selected', async () => {
  const createSpy = vi.fn();
  // ... mock useCreateTask similar to existing tests ...
  wrap(<NewTaskForm projects={projects} />);
  await waitFor(() => screen.getByText(/frontend/));
  await userEvent.type(screen.getByLabelText('título'), 'T');
  await userEvent.selectOptions(screen.getByLabelText('template'), 'frontend');
  await userEvent.click(screen.getByRole('button', { name: /criar/i }));
  expect(createSpy).toHaveBeenCalledWith(
    expect.objectContaining({ template: 'frontend' }),
    expect.anything(),
  );
});

it('submit omits template when not selected', async () => {
  // ... similar but no selectOptions, expect template not in payload ...
});
```

Match the existing test structure of `NewTaskForm.test.tsx` (how `useCreateTask` is mocked — copy that pattern for the assertion in test 4 above).

- [ ] **Step 8: Rodar UI tests**

Run:

```bash
cd ui && npx vitest run src/hooks/useCatalog.test.tsx src/components/NewTaskForm.test.tsx
```

Expected: PASS (todos verdes)

- [ ] **Step 9: Coverage UI gate**

```bash
cd ui && npx vitest run --coverage
```

Expected: 100% novos arquivos (`useCatalog.ts`); NewTaskForm.tsx coverage mantido.

- [ ] **Step 10: Commit**

```bash
git add ui/src/hooks/useCatalog.ts ui/src/hooks/useCatalog.test.tsx \
        ui/src/lib/api.ts ui/src/lib/query-keys.ts \
        ui/src/components/NewTaskForm.tsx ui/src/components/NewTaskForm.test.tsx
git commit -m "feat(F7.e): useCatalog hook + NewTaskForm dropdown de template"
```

---

## Task F7.f — TaskCard badges + TaskDetailModal Configuração section

**Files:**
- Modify: `ui/src/components/TaskCard.tsx`
- Modify: `ui/src/components/TaskCard.test.tsx`
- Modify: `ui/src/components/TaskDetailModal.tsx`
- Modify: `ui/src/components/TaskDetailModal.test.tsx`

- [ ] **Step 1: Escrever testes do TaskCard (TDD)**

Edit `ui/src/components/TaskCard.test.tsx`. Add tests:

```typescript
it('renders template and permission_profile badges when set', () => {
  const t = { ...baseTask, template: 'bugfix', permission_profile: 'yolo' };
  wrap(<TaskCard task={t} />);
  const templateBadge = screen.getByText('bugfix');
  expect(templateBadge).toHaveAttribute('data-template-name', 'bugfix');
  const profileBadge = screen.getByText('yolo');
  expect(profileBadge).toHaveAttribute('data-permission-profile', 'yolo');
});

it('omits badges when template/permission_profile are null', () => {
  const t = { ...baseTask, template: null, permission_profile: null };
  wrap(<TaskCard task={t} />);
  expect(screen.queryByTestId('template-badge')).toBeNull();
});

it.each([
  ['yolo', 'yellow'],
  ['default', 'gray'],
  ['read-only', 'green'],
])('applies known color for profile %s → %s', (profile, color) => {
  const t = { ...baseTask, template: 'frontend', permission_profile: profile };
  wrap(<TaskCard task={t} />);
  const badge = screen.getByText(profile);
  expect(badge.getAttribute('data-profile-color')).toBe(color);
});

it('applies gray color fallback for unknown profiles', () => {
  const t = { ...baseTask, template: 'custom', permission_profile: 'paranoid' };
  wrap(<TaskCard task={t} />);
  const badge = screen.getByText('paranoid');
  expect(badge.getAttribute('data-profile-color')).toBe('gray');
});
```

- [ ] **Step 2: Implementar badges em TaskCard**

Edit `ui/src/components/TaskCard.tsx`. Adicionar (próximo ao header do card):

```typescript
const PROFILE_COLORS: Record<string, string> = {
  yolo: 'yellow',
  default: 'gray',
  'read-only': 'green',
};

function profileColor(name: string): string {
  return PROFILE_COLORS[name] ?? 'gray';
}

// Inside the TaskCard JSX, somewhere near the title:
{task.template && (
  <span
    data-template-name={task.template}
    data-testid="template-badge"
    className="template-badge"
  >
    {task.template}
  </span>
)}
{task.permission_profile && (
  <span
    data-permission-profile={task.permission_profile}
    data-profile-color={profileColor(task.permission_profile)}
    data-testid="profile-badge"
    className={`profile-badge profile-${profileColor(task.permission_profile)}`}
    title={`Perfil: ${task.permission_profile}`}
  >
    {task.permission_profile}
  </span>
)}
```

Add minimal CSS in `ui/src/index.css` (único stylesheet do projeto):

```css
.template-badge, .profile-badge {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.75rem;
  margin-right: 4px;
}
.template-badge { background: #e5e7eb; color: #1f2937; }
.profile-yellow { background: #fef3c7; color: #92400e; }
.profile-gray { background: #e5e7eb; color: #1f2937; }
.profile-green { background: #d1fae5; color: #065f46; }
```

- [ ] **Step 3: Rodar TaskCard tests**

Run:

```bash
cd ui && npx vitest run src/components/TaskCard.test.tsx
```

Expected: PASS (incluindo testes pré-existentes intactos + 3 novos)

- [ ] **Step 4: Adicionar seção Configuração no TaskDetailModal**

Edit `ui/src/components/TaskDetailModal.tsx`. Add a small read-only section:

```typescript
<section aria-label="task-config">
  <h3>Configuração</h3>
  <dl>
    <dt>Template</dt>
    <dd>{task.template ?? '(nenhum)'}</dd>
    <dt>Perfil de permissão</dt>
    <dd>{task.permission_profile ?? '(fallback)'}</dd>
    <dt>Branch</dt>
    <dd>{task.branch ?? '(será derivado no spawn)'}</dd>
  </dl>
</section>
```

Position it near the existing task metadata (state/timestamps). No edit affordance.

- [ ] **Step 5: Atualizar TaskDetailModal tests**

Edit `ui/src/components/TaskDetailModal.test.tsx`. Add:

```typescript
it('shows task config section with template + profile + branch', () => {
  const t = { ...baseTask, template: 'frontend', permission_profile: 'yolo', branch: 'feat-ui/foo' };
  wrap(<TaskDetailModal task={t} onClose={() => {}} />);
  const section = screen.getByLabelText('task-config');
  expect(section).toHaveTextContent('frontend');
  expect(section).toHaveTextContent('yolo');
  expect(section).toHaveTextContent('feat-ui/foo');
});

it('shows fallback labels when template/profile/branch are null', () => {
  const t = { ...baseTask, template: null, permission_profile: null, branch: null };
  wrap(<TaskDetailModal task={t} onClose={() => {}} />);
  const section = screen.getByLabelText('task-config');
  expect(section).toHaveTextContent('(nenhum)');
  expect(section).toHaveTextContent('(fallback)');
});
```

- [ ] **Step 6: Rodar testes**

Run:

```bash
cd ui && npx vitest run src/components/TaskCard.test.tsx src/components/TaskDetailModal.test.tsx
```

Expected: PASS

- [ ] **Step 7: Coverage UI**

```bash
cd ui && npx vitest run --coverage
```

Expected: 100% coverage UI mantida.

- [ ] **Step 8: Smoke test manual no browser (opcional, host-only)**

Se você tem o dev server rodando, abra `http://localhost:5173`, crie uma task com template=frontend, confirme:
1. Branch é auto-populado com `feat-ui/...` no hint
2. Card mostra dois badges (frontend amarelo claro + yolo amarelo forte)
3. Modal de detalhes tem seção Configuração

Se sandbox: skip — você não pode subir o dev server. Anote no commit message.

- [ ] **Step 9: Commit**

```bash
git add ui/src/components/TaskCard.tsx ui/src/components/TaskCard.test.tsx \
        ui/src/components/TaskDetailModal.tsx ui/src/components/TaskDetailModal.test.tsx
# add any .css touched
git commit -m "feat(F7.f): TaskCard badges + TaskDetailModal Configuração section"
```

---

## Task F7.g — ADR-0021 + ARCHITECTURE update + E2E skeletons + closure

**Files:**
- Create: `docs/adr/0021-catalog-yaml-curado-templates-perfis.md`
- Create: `tests/e2e/test_f7_create_task_with_template.py`
- Modify: `docs/adr/README.md`
- Modify: `ARCHITECTURE.md`

- [ ] **Step 1: Escrever ADR-0021 (Nygard PT-BR)**

Write `docs/adr/0021-catalog-yaml-curado-templates-perfis.md`:

```markdown
# ADR-0021: Catálogo curado (YAML) de templates + perfis de permissão

**Status:** Aceito — 2026-05-11
**Decisores:** marcosdid + Claude
**Contexto:** F7 (último fase do MVP)

## Contexto

`Task.template` e `Task.permission_profile` (colunas String(64) nullable) existem
desde F4 mas nunca foram populadas. ARCHITECTURE.md §11 promete na F7:
"Templates frontend/backend/refactor/bugfix com perfil pré-aprovado. Catálogo,
perfil aplicado no spawn." Spawn atualmente usa `--dangerously-skip-permissions`
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
- 3 perfis no catálogo inicial: `yolo` (--dangerously-skip-permissions),
  `default` ([]), `read-only` (--permission-mode plan + tools de leitura).
- 4 templates: `frontend` (yolo + feat-ui/), `backend` (default + feat-be/),
  `refactor` (default + refactor/), `bugfix` (yolo + fix/).
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
- Sem migração, sem coupling adicional ao schema do banco
- Catálogo auditável via git log + diff YAML legível
- Editar perfil = commit + restart, fluxo familiar pra equipe
- F4-F6 tasks NULL spawnam com yolo (idêntico ao hardcoded) — zero regressão

**Negativas:**
- Editar `claude_args` de um perfil **após** snapshot-at-create afeta tasks
  existentes na próxima sessão (após restart). Admin precisa saber disso.
- Sem UI de admin: alguém precisa entender YAML pra adicionar perfis. Aceitável
  no MVP (1 dev).
- Catalog reload requer restart do daemon. Restart de daemon é raro mas
  observável.

## Referências

- Spec: `docs/superpowers/specs/2026-05-11-f7-templates-perfis-design.md`
- Plan: `docs/superpowers/plans/2026-05-11-f7-templates-perfis.md`
- ARCHITECTURE.md §11 (roadmap), §13 (decisões)
- Código: `orchestrator/core/catalog.py`, `orchestrator/config/catalog.yml`,
  `orchestrator/sandbox/aijail.py:write_aijail_config`
```

- [ ] **Step 2: Atualizar docs/adr/README.md**

Edit `docs/adr/README.md`. Add row (ordem cronológica):

```markdown
| [0021](0021-catalog-yaml-curado-templates-perfis.md) | Catálogo YAML curado pra templates + perfis (F7) | Aceito | 2026-05-11 |
```

- [ ] **Step 3: Atualizar ARCHITECTURE.md**

Edit `ARCHITECTURE.md`:

1. **§11 (roadmap):** marcar F7 como ✅. Substituir a linha atual de F7:

```markdown
| **F7 — Templates + perfis** ✅ | Templates frontend/backend/refactor/bugfix com perfil pré-aprovado aplicado no spawn; catálogo curado em `orchestrator/config/catalog.yml`; dropdown único no form de criar task | `Catalog` Pydantic + `load_catalog`, `GET /api/catalog`, `Task.template`/`permission_profile` populados; `AiJailRuntime.spawn` consome `claude_args` do catálogo; fallback yolo p/ tasks F4-F6 com NULL |
```

2. **§13 (decisões registradas):** adicionar row:

```markdown
| F7 catálogo | [0021](docs/adr/0021-catalog-yaml-curado-templates-perfis.md) | YAML curado + Pydantic + load 1x lifespan | Sem migração, auditável via git diff, editar = commit |
```

3. **§3 (modelo de dados):** confirmar que comentário em `Task.template`/`permission_profile` (linha ~53) reflete F7 ativo. Mudar (se necessário):

```markdown
- `template`/`permission_profile` populados em F7 quando user escolhe template no form de criar task. Tasks F4-F6 ficam NULL e usam fallback do catálogo no spawn.
```

- [ ] **Step 4: Escrever E2E skeleton (host-only)**

Write `tests/e2e/test_f7_create_task_with_template.py`:

```python
"""F7 E2E: criar task com template aplica prefix + grava profile + badges visíveis.

⚠️ Cannot run from inside ai-jail (gotcha #15). Host-only:
    uv run --group test-e2e pytest tests/e2e/test_f7_create_task_with_template.py -v
"""
import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
def test_f7_create_task_with_template_frontend(
    page: Page,
    orchestrator_with_repo: tuple[str, str],
) -> None:
    url, repo_path = orchestrator_with_repo
    page.goto(url)

    # Cria projeto via drawer
    page.get_by_role("button", name="Projetos ▾").click()
    page.get_by_label("project-name").fill("p")
    page.get_by_label("project-path").fill(repo_path)
    page.get_by_role("button", name="Adicionar projeto").click()
    page.get_by_label("close-drawer").click()

    # Preenche título + escolhe template frontend
    page.fill('[aria-label="título"]', "Add dark mode toggle")
    page.select_option('[aria-label="template"]', "frontend")

    # Hint mostra branch derivado do prefix
    expect(page.locator('[aria-label="template-hint"]')).to_contain_text(
        "feat-ui/add-dark-mode-toggle"
    )

    page.get_by_role("button", name="Criar").click()

    # Card aparece com badges
    card = page.locator(".task-card").filter(has_text="Add dark mode toggle").first
    expect(card.locator('[data-template-name="frontend"]')).to_be_visible()
    expect(card.locator('[data-permission-profile="yolo"]')).to_be_visible()
```

- [ ] **Step 5: Rodar suite completa**

Run:

```bash
uv run pytest tests/unit tests/integration -v --no-header
cd ui && npx vitest run
```

Expected: tudo verde. E2E skipped no sandbox (sem playwright server).

- [ ] **Step 6: Coverage final geral**

```bash
uv run pytest tests/unit tests/integration --cov=orchestrator --cov-report=term-missing | tail -30
cd ui && npx vitest run --coverage
```

Expected: 100% backend mantido + 100% UI mantida.

- [ ] **Step 7: Commit closure**

```bash
git add docs/adr/0021-catalog-yaml-curado-templates-perfis.md \
        docs/adr/README.md ARCHITECTURE.md \
        tests/e2e/test_f7_create_task_with_template.py
git commit -m "feat(F7.g): ADR-0021 + ARCHITECTURE F7 ✅ + E2E skeleton

Fecha F7 (último MVP). Templates frontend/backend/refactor/bugfix com
perfil pré-aprovado aplicado no spawn. Catálogo curado YAML em
orchestrator/config/catalog.yml carregado 1x no lifespan. Sem migração:
colunas Task.template/permission_profile (existentes desde F4) finalmente
populadas.

MVP F0 → F7 ✅."
```

---

## Pós-implementação: verificação final

- [ ] **Suite full backend**: `uv run pytest tests/unit tests/integration -v --no-header` — verde
- [ ] **Suite full UI**: `cd ui && npx vitest run` — verde
- [ ] **Coverage backend**: 100% nos arquivos F7 + sem regressão geral
- [ ] **Coverage UI**: 100% mantido
- [ ] **Lint backend**: `uv run ruff check orchestrator tests` — clean
- [ ] **Type-check UI**: `cd ui && npx tsc -b --noEmit` — clean
- [ ] **Build UI** (catch type errors): `cd ui && npm run build` — sucesso
- [ ] **Manual smoke (host)**: criar task com template, ver badge, iniciar sessão, confirmar `.ai-jail` tem command correto

## Notas pra implementador

- **TDD obrigatório**: cada step "Write test" antes do step "Implement". Não invertam.
- **Commits granulares por sub-task**: 7 commits no total (F7.a através F7.g). Não squash.
- **Reviewer antes de cada commit**: dispatch `code-reviewer` ou `superpowers:code-reviewer` no diff staged (CLAUDE.md `Pre-commit code review`). Conserta findings antes do commit final.
- **Não amenda commits**: se hook falha, conserta + novo commit.
- **Fallback yolo é load-bearing**: se você acidentalmente mudar para `default` em qualquer lugar, tasks F4-F6 mudam comportamento silenciosamente. Cuidado.
- **Catalog re-load é proibido**: se você se vir tentado a adicionar file-watcher pro catalog.yml, pare e confirme com o usuário. ARCHITECTURE diz "restart-only".
