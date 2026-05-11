# ADR-0019: Manifesto F6 é `services:` dict com `depends_on`

- **Status:** Accepted
- **Data:** 2026-05-11
- **Decisores:** Marcos

## Contexto

F6 lê `.orchestrator/run.yml` (manifesto commitado, ADR-0005) pra subir
a stack dev. A pergunta de design: qual o schema? Três opções foram
consideradas no brainstorm:

1. `services:` dict genérico + `depends_on` (estilo docker-compose).
2. Roles fixas — 3 blocos top-level (`db:`, `backend:`, `frontend:`)
   refletindo o caso 80%.
3. 1 serviço só (full-stack na mesma image; usuário responsável por
   meter tudo num Dockerfile).

## Decisão

**`services:` dict + `depends_on` por serviço.**

```yaml
version: "1"
services:
  db:
    image: postgres:16
    port: 5432
  cache:
    image: redis:7
  backend:
    build: ./backend
    depends_on: [db, cache]
    healthcheck:
      command: ["curl", "-f", "http://localhost:8000/health"]
  frontend:
    build: ./frontend
    depends_on: [backend]
    port: 5173
```

**Validações no parser** (`core/manifest.py`, Pydantic v2 `extra="forbid"`):

- `image` XOR `build` por serviço.
- `port` ∈ [1, 65535]; único entre serviços.
- `depends_on` referencia só serviços declarados; sem ciclos
  (Kahn's algo); sem self-ref.
- Service name: regex `^[a-z0-9][a-z0-9-]*$` (Docker-naming-safe).
- Top-level: `version: "1"` literal; `services` dict não-vazio.

**Substituições em `env` values** (não em `command`/`image`/`build` —
escopo controlado, evita injection):

- `$PORT_<svc>` → host port alocado pelo PortAllocator (31000-31999)
- `$URL_<svc>` → `http://localhost:<host_port>`
- `$RUN_ID` → primeiros 8 chars do uuid hex da run
- `$CWD` → cwd absoluto da task

Sort por `len(svc_name) DESC` evita prefix-collision (`$PORT_db` vs
`$PORT_db2`). Variáveis com prefixos desconhecidos (`$HOME`) ficam
intactas — container resolve.

## Alternativas

1. **Roles fixas (`db:`, `backend:`, `frontend:`)** (rejeitada): força
   cardinalidade 3 fixa; quebra pra projetos com cache, worker, ML
   service, etc. Schema mais simples mas YAGNI invertido — engessa o
   feature.
2. **Full-stack monolítico (1 image)** (rejeitada): empurra complexidade
   pro Dockerfile do usuário; perde isolation de recursos (CPU/mem
   per-service); inviável pra apps que dependem de Postgres official
   image.
3. **`services:` dict sem `depends_on`** (rejeitada): força "ordem
   manual" no manifest. Tooling moderno (docker-compose, k8s) assume
   declarative ordering.

## Consequências

**Positivas**

- Familiar pra quem usa docker-compose; curva de aprendizado próxima de
  zero pra dev backend.
- Pydantic + `extra="forbid"` = erros tipados com path JSON quando
  validação falha (e.g., `services.backend.port: must be int`).
- Topological sort pra build order é determinístico e testável (Kahn).
- Substituição via env é segura (só em values; não em image/command).

**Negativas**

- `version: "1"` literal força bump explícito quando schema mudar.
  Aceitável: sinal claro de breaking change.
- Substituição naive `str.replace` exigiu sort por len-DESC (descoberto
  via reviewer pré-commit). Bug sutil mas covered.
- `mount_source` default = True pra serviços com `build:` pode causar
  surprise no PG/Redis se usuário esquecer de declarar
  `mount_source: false` — mitigado: default só ativa quando `build`
  presente; `image:` puro tem default `false`.

## Referências

- Spec F6 §3 (decisão #5), §6 (schema completo)
- ADR-0005 (manifesto explícito), ADR-0006 (Docker engine)
- `orchestrator/core/manifest.py`
