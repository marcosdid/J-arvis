# ADR-0002: Stack do daemon — Python 3.13 + FastAPI + SQLAlchemy 2 async + Alembic

- **Status:** Accepted
- **Data:** 2026-05-08
- **Decisores:** Marcos

## Contexto

O daemon precisa expor REST + WebSocket, gerenciar processos filhos
(sessões em jaula), persistir estado (~6 tabelas, single-user),
integrar com `ai-jail` e Docker via subprocess, e ser fácil de evoluir
em sessões futuras com Claude Code.

Stacks consideradas: Python (FastAPI), Node/TS (Fastify), Rust (Axum),
Go.

## Decisão

- **Linguagem:** Python 3.13.
- **Framework web:** FastAPI + uvicorn (async nativo, OpenAPI grátis).
- **ORM:** SQLAlchemy 2.x async — stack ortodoxa e madura, dominante há
  ~15 anos.
- **Migrações:** Alembic — canônico no ecossistema SQLAlchemy.
- **Persistência:** SQLite local em arquivo.
- **Settings:** Pydantic Settings.
- **Gerenciador de pacotes:** `uv` (Python interpreter management
  + resolver + lockfile).

## Alternativas consideradas

1. **Node/TS + Fastify.** Atrai por compartilhar tipos com a UI, mas o
   ecossistema de "controlar processos do SO + integrar com tooling
   AI/ML" é mais rico em Python.
2. **Rust + Axum.** Performance e bin único, mas curva e ecossistema
   menor; overkill para single-user local.
3. **Go.** Concorrência boa, bin único, mas menos rico que Python pra
   IA e introspecção de processos.
4. **SQLModel em vez de SQLAlchemy 2 puro.** Reduz boilerplate (modelo
   serve API e DB), mas tem rough edges em async/relacionamentos
   complexos e comunidade menor. Rejeitada pela aposta em maturidade.
5. **aiosqlite raw.** Sem ORM. Máximo controle, mas voce escreve query,
   mapping e paginação tudo a mão. Vale apenas pra schemas mínimos.

## Consequências

**Positivas**
- Ecossistema maduro: testcontainers-python, httpx, pytest-asyncio
  cobrem todas as três camadas de teste sem hack.
- SQLAlchemy 2 + Alembic dão migrations geradas automaticamente do
  diff dos modelos.
- `uv` instala Python 3.13 gerenciado sem mexer no sistema.

**Negativas**
- Mais boilerplate que SQLModel: modelos ORM separados de schemas
  Pydantic da API.
- Distribuição: precisa empacotar Python + venv (ou via Docker, que
  já é o caso para E2E).

**Neutras**
- Single-user local: ausência de fleet remove a pressão por migrations
  com rollback e estratégias de blue-green.

## Referências

- `ARCHITECTURE.md` §13 (Decisões registradas)
- `pyproject.toml`
