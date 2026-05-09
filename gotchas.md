# Gotchas

Aprendizados convertidos em regras. Reler no início de cada sessão.

## 1. `uv sync` precisa do pacote já existindo

**Regra:** crie a estrutura de diretórios do pacote (`orchestrator/__init__.py`)
**antes** do primeiro `uv sync`. Se rodar antes, o `dist-info` é gerado mas
sem `.pth`, e o pacote não fica importável.

**Como detectar:** `uv pip list` mostra o pacote como instalado, mas
`pytest` falha com `ModuleNotFoundError: No module named '<pkg>'`.

**Como aplicar:** se você esquecer e cair nesse buraco, rode
`uv sync --reinstall-package <pkg>` para regenerar o editable. Aparece um
arquivo `_editable_impl_<pkg>.pth` em `.venv/lib/.../site-packages/`.

## 2. pnpm 11 guarda aprovação de build em `pnpm-workspace.yaml`

**Regra:** ao precisar de build script (caso típico: `esbuild`), rode
`pnpm approve-builds <pkg>` e **commite** o `pnpm-workspace.yaml`
gerado. Em Dockerfile, o `COPY ui/` precisa incluir esse arquivo.

**Como detectar:** `[ERR_PNPM_IGNORED_BUILDS] Ignored build scripts:
esbuild@x.y.z` durante `pnpm install`. Configurações em
`package.json#pnpm.allowBuilds` ou `package.json#pnpm.onlyBuiltDependencies`
**não são suficientes** sozinhas.

**Como aplicar:** Dockerfile multi-stage com UI usar `ENV CI=true` no
stage de build (evita prompt de purge de `node_modules`) e copiar
`ui/pnpm-workspace.yaml` junto com `package.json` e `pnpm-lock.yaml`.

## 3. Stub TDD-mínimo pode mascarar testes não-escritos

**Regra:** quando o stub mínimo aceita um parâmetro mas devolve valor
fixo (ex: `formatStatus(_status) → "Em execução"`), **o próximo ciclo
TDD precisa começar por um teste para um input diferente** que force a
ramificação. Senão, futuras chamadas com strings diferentes passarão
silenciosamente devolvendo o valor errado.

**Como detectar:** se `_status` ainda tem underscore após F0,
qualquer chamada nova precisa de teste novo antes de remover o
underscore.

**Como aplicar:** ao estender uma função stub, antes de tocar a
implementação, escreva o teste para o NOVO input e confirme RED. Só
depois adicione a ramificação.

## 4. coverage.py precisa de `concurrency=["thread", "greenlet"]` com SQLAlchemy async

**Regra:** quando o código testado usa SQLAlchemy 2 async (que roda
I/O dentro de greenlets), o `pyproject.toml` precisa de:

```toml
[tool.coverage.run]
concurrency = ["thread", "greenlet"]
```

Sem isso, qualquer linha async que toque o DB fica reportada como
**não coberta** mesmo quando o teste passa — a cobertura cai e o gate
de 100% reprova falsamente.

**Como detectar:** integration test passa, mas linhas claramente
exercitadas (returns, assignments) aparecem na lista "Missing" do
coverage report. Especialmente comum em `await session.commit()` /
`await session.refresh()` / `await session.execute()`.

**Como aplicar:** já está configurado. Se aparecer regressão,
checar este parâmetro antes de caçar bugs no código.

## 5. Vitest 2 e Vite 6 têm conflito de tipos

**Regra:** se o `vite.config.ts` exporta config com chave `test:`, use
Vitest 3 com Vite 6. Vitest 2 traz tipos de Vite 5 e quebra em
`defineConfig({ plugins: [...], test: {...} })`.

**Como detectar:** erro TS `Object literal may only specify known
properties, and 'test' does not exist in type 'UserConfigExport'`,
ou conflitos de tipo entre `Plugin<any>` de versões diferentes.

**Como aplicar:** ao montar UI nova com Vite ≥6, fixar
`@vitest/coverage-v8` e `vitest` em `^3` no `package.json`. Importar
`defineConfig` de `'vitest/config'`, não de `'vite'`.

## 6. UID host vs container quebra bind-mounts em E2E

**Regra:** ao precisar de um repo git acessível pelo daemon dentro do
container, **crie via `container.exec()` em vez de bind-mount do
`tmp_path`**. O usuário do host (`marcoslima` uid=1001) não bate com o
`jarvis` do container (uid=1000), e o `tmp_path` do pytest é
`drwx------`, então o daemon não consegue ler nada via volume.

**Como detectar:** API responde 422 "not a git repository" mesmo com
`.git` existindo no caminho mountado, OU `git worktree list` falha por
permissão.

**Como aplicar:** o E2E flow test em `tests/e2e/conftest.py` usa
`container.exec(["sh", "-c", _INIT_REPO_SCRIPT])` para criar o repo
dentro do container já como o user `jarvis`. O Dockerfile precisa
ter `git` instalado (faz parte do daemon também — `git worktree list`).

## 7. `.dockerignore` evita corrupção de tar com node_modules locais

**Regra:** `ui/node_modules/` (e qualquer cache pesado) precisa estar
no `.dockerignore`. pnpm cria muitos symlinks em `node_modules/.pnpm/`
e o buildkit às vezes vê o arquivo ser movido durante o tar streaming
→ erro `failed to create diff tar stream: lstat ...: no such file or
directory`.

**Como detectar:** `docker build` falha aleatoriamente em `lstat` em
arquivos dentro de `ui/node_modules/.pnpm/...` durante COPY ou tar do
contexto.

**Como aplicar:** o Dockerfile já roda `pnpm install --frozen-lockfile`
dentro do container, então `ui/node_modules` local nunca precisa ser
copiado. `.dockerignore` reforça isso e acelera o build.

## 8. Use `HealthcheckWaitStrategy` em vez de `LogMessageWaitStrategy` quando há `HEALTHCHECK` no Dockerfile

**Regra:** com `HEALTHCHECK` declarado no Dockerfile, prefira
`testcontainers.core.wait_strategies.HealthcheckWaitStrategy()`. É mais
robusto que esperar uma string específica nos logs (uvicorn 0.46
buffera ou redireciona "Application startup complete" de forma que
o stderr capturado pelo testcontainers às vezes não inclui).

**Como detectar:** `LogMessageWaitStrategy` dá `TimeoutError` mesmo com
`Container status: running, health: healthy` no relatório.

**Como aplicar:** `HealthcheckWaitStrategy().with_startup_timeout(120)`
em vez do log strategy.

## 9. E2E não roda de dentro de uma sessão Claude já em ai-jail

**Regra:** se a sessão Claude está rodando dentro de uma jaula `ai-jail`
(network namespace isolado), os testes E2E **não conseguem alcançar o
docker daemon do host** mesmo que ele esteja no ar. O `/var/run/docker.sock`
aparece dentro da jaula como tmpfs vazio (sem daemon escutando).

**Como detectar:** `docker info` retorna `Cannot connect to /var/run/docker.sock`
mesmo quando o host tem Docker rodando. Sintomas: `CapBnd: 0000000000000000`
em `/proc/self/status`, namespaces `net/pid/mnt/ipc/cgroup` listados em
`/proc/self/ns/`, socket file presente mas em tmpfs.

**Como aplicar:** rodar `uv run pytest tests/e2e/...` **fora** da jaula
(no terminal nativo do host, não dentro de uma sessão Claude já jailed).
Equivalente ao item "Demo B" da DoD da F2 — validação manual a partir
do host. F0/F1 do roadmap são todos não-E2E e cabem dentro da jaula.

## 10. `fileConfig` do alembic silencia uvicorn no startup

**Regra:** ao rodar migrations alembic dentro do lifespan do FastAPI,
o `alembic/env.py` chama `fileConfig(config.config_file_name)` que por
default usa `disable_existing_loggers=True`. Isso desliga o logger
"uvicorn" e a mensagem `Application startup complete` + `Uvicorn running
on http://...:port` somem do stderr.

**Como detectar:** após rodar `uv run uvicorn orchestrator.main:app
--port 8765`, o terminal mostra os logs de migration (`Running upgrade
0001 -> 0002, hook columns`) e fica em silêncio. Usuário acha que o
daemon não subiu, mas `curl http://localhost:8765/health` retorna 200
normalmente — o server tá rodando, só os logs sumiram.

**Como aplicar:** já corrigido em `alembic/env.py`:
`fileConfig(config.config_file_name, disable_existing_loggers=False)`.
