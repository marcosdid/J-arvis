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

## 11. Tests sem marker viram invisíveis sob `-m "unit or integration"`

**Regra:** `pyproject.toml` declara markers `unit`, `integration`, `e2e`
e roda o gate de cobertura com `-m "unit or integration"`. Tests que não
declaram marker (`pytestmark = pytest.mark.X` no topo do módulo, ou
`@pytest.mark.X` na função) são **silenciosamente desselecionados** —
o output de pytest mostra `N collected / M deselected` mas o número de
deselected não chama atenção. Resultado: arquivos novos sem marker não
rodam no gate, e a cobertura efetiva cai sem que isso quebre o gate
(porque os arquivos faltam, não falham).

**Como detectar:** rodar com e sem `-m`:
```bash
uv run pytest tests/unit tests/integration -m "unit or integration" --cov=orchestrator
uv run pytest tests/unit tests/integration --cov=orchestrator
```
Se a contagem de testes diverge (ex: 91 vs 207) e cobertura sobe quando
o filtro sai, é esse problema. Outra pista: cobertura reporta linhas
faltando em arquivos que claramente têm `tests/unit/test_*.py`
correspondente passando.

**Como aplicar:** já corrigido por auto-marker em `tests/conftest.py`:
`pytest_collection_modifyitems` aplica `unit`/`integration`/`e2e`
baseado no diretório-pai do teste (`tests/unit/...` → `pytest.mark.unit`,
etc). Novos arquivos não precisam declarar marker. Decorators e
`pytestmark` legados continuam funcionando (markers acumulam).

## 12. dnd-kit sem `activationConstraint` engole o `onClick` do React

**Regra:** elementos com `useSortable`/`useDraggable` que também têm
`onClick` no mesmo div precisam de `activationConstraint: { distance: N }`
no sensor — caso contrário o `click` nunca dispara.

**Por quê:** `PointerSensor` default ativa drag no primeiro `pointerdown`
e chama `event.preventDefault()` pra bloquear seleção de texto.
[MDN](https://developer.mozilla.org/en-US/docs/Web/API/Element/pointerdown_event):
*"If preventDefault() is called on pointerdown, the click event for
that pointer sequence is not fired."* React anexa `onClick` ao evento
sintético `click`; sem o `click` original, nada dispara.

**Sintoma:** clicar num card de kanban (ou qualquer item drag-and-drop)
não faz nada. Em vitest passa (não usa pointer real); em Playwright
falha com `expected modal to be visible` (modal nunca abre).

**Fix:**
```tsx
const sensors = useSensors(
  useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
);
<DndContext sensors={sensors} ...>
```
Com `distance: 8`, drag só ativa após 8 px de movimento; click puro
(0 px) flui sem `preventDefault`.

**Descoberto:** F5.l E2E. Pré-existia desde F4 mas só apareceu quando
o E2E rodou de fato.

## 13. React Query keys com prefixo divergente não invalidam em cascata

**Regra:** `invalidateQueries({ queryKey: ['tasks'] })` derruba
**qualquer** key começando com `['tasks', ...]`. Mas não derruba
`['task', taskId]` (prefixo `'task'` ≠ `'tasks'`). Singular vs plural
quebra silenciosamente.

**Sintoma:** componente que usa `useQuery({ queryKey: ['task', id] })`
nunca atualiza, mesmo quando o mutation chama
`invalidateQueries({ queryKey: queryKeys.tasks })`. O usuário "muda"
algo, vê a lista atualizar, mas o detalhe do mesmo registro continua
mostrando o estado antigo.

**Convenção:** sempre key plural + objeto descritor pra registros
individuais — `['tasks', { id }]` em vez de `['task', id]`:
```ts
export const queryKeys = {
  tasks: ['tasks'] as const,
  tasksForProject: (pid) => ['tasks', { projectId: pid }] as const,
  task: (id) => ['tasks', { id }] as const,
};
```
Assim `invalidateQueries({ queryKey: queryKeys.tasks })` cobre lista +
filtro-por-projeto + detalhe-individual em 1 chamada.

**Descoberto:** F5.l E2E. `TaskDetailModal` usava `['task', taskId]`;
após mudar state via `Move to`, o dropdown não recalculava as transitions
disponíveis até o modal ser fechado+reaberto.

## 14. `lib/format.ts::formatStatus` é código morto pós-F4

**Sintoma:** grep encontra "Em execução"/"Aguardando resposta"/"Ocioso"
no codebase, dando a impressão de que o UI exibe status de sessão.
Não exibe — `formatStatus` não é importado por nenhum componente desde
F4 (kanban virou task-centric; status de sessão não é renderizado em
lugar visível).

**Implicação prática:** F2 hook plumbing (`Notification` →
`awaiting_response`, `Stop` → `idle`) **ainda funciona server-side**,
mas o usuário não vê. E2E que afirmava `expect(text("Aguardando
resposta"))` ficou enganado — não há esse texto na DOM.

**Como detectar:** se vai assertar texto na UI, primeiro
`grep -rn 'TEXTO' ui/src/components/` — se não tiver match (só em
`lib/format.ts`), é orfão. Valide via API (`/api/sessions`) no E2E.

**Fix pendente** (fora de escopo F5): ou re-incluir o status num
`TaskCard` quando `task.active_session_id`, ou remover `format.ts`
completo. Decisão de produto.

## 15. `ai-jail run` não roda aninhado dentro de outra jaula

**Regra:** uma sessão Claude já rodando em `ai-jail` (ou qualquer
sandbox que zere `CapEff` e bloqueie `unshare --user`) **não consegue
spawnar uma jaula filha**. `bwrap`, que `ai-jail` invoca por baixo,
falha com `Failed to make / slave: Operation not permitted`.

**Como detectar:**
```bash
grep '^CapEff' /proc/self/status     # 0000000000000000 = sandboxed
unshare --user true                  # "Operation not permitted" = sandboxed
bwrap --dev-bind / / true            # "Failed to make / slave" = sandboxed
```

**Diferença vs gotcha #9:** #9 é sobre docker daemon socket
(testcontainers/E2E) — pode passar via socket bind-mount mesmo dentro
da jaula. #15 é sobre `CAP_SYS_ADMIN` + user namespaces que `bwrap`
exige pra montar o overlay — esses não são "passáveis" via socket;
exigem privilégio real do kernel.

**Como aplicar:** F5.0 spike (validação de multi-repo dentro de
ai-jail), Demo manual completa de F5, ou qualquer cenário onde
o agente Claude precise iniciar **outra** sessão Claude jailed, **só
funciona do host nativo** — não da jaula corrente. O daemon
J-arvis em produção roda no host como user `jarvis`, então spawn de
jaulas filhas é OK lá; só o agente-de-desenvolvimento (esta sessão)
é que tem limitação.

## 16. `ai-jail` v0.10+ não tem subcomando `run`; comando vem do `.ai-jail`

**Regra:** invocar `ai-jail run -- claude` em v0.10+ falha com
`✗ Failed to exec run: No such file or directory`. O `run` é
interpretado como o comando a executar dentro da jaula (não como
subcomando do `ai-jail`). A CLI correta é:

```bash
ai-jail               # lê `.ai-jail` do cwd; usa `command` de lá
ai-jail --            # idem (separador antes de args opcionais)
ai-jail claude        # usa preset embutido (sem ler `.ai-jail`)
ai-jail status        # imprime config sem executar
```

**Sintoma:** sessão spawnada via terminal mostra:
```
▸ Jail Active: <cwd>
▸ Landlock: fully enforced
✗ Failed to exec run: No such file or directory (os error 2)
```
e a janela fecha. Pré-0.10 tinha um subcomando `run` explícito;
v0.10 removeu silenciosamente.

**Como aplicar:** `orchestrator/sandbox/aijail.py:AiJailRuntime.spawn`
foi corrigido pra usar `inner = ["ai-jail"]` e **escrever
`<cwd>/.ai-jail`** dinâmico no spawn via `write_aijail_config`:

- `command = ["claude", "--dangerously-skip-permissions"]`
- `rw_maps` populado por `_discover_git_dirs(cwd)` — discovery resolve
  `.git` pointer files (`gitdir: <project>/.git/worktrees/<X>`) pros
  paths dos `.git` originais; sem isso, `git status` dentro da jaula
  retorna `fatal: not a git repository` (o pointer aponta pra fora do
  cwd, e bwrap não monta o externo por default). Aplica tanto a
  worktrees mono quanto multi-repo F5.

**Descoberto:** F5.0 spike no host (esta gotcha + #15 explicam por
que o spike só roda de fora da jaula).

## 17. `ai-jail` v0.10 deixa localhost passar mesmo com `allow_tcp_ports = []`

**Regra:** ao contrário do que o nome sugere, `allow_tcp_ports` em
`.ai-jail` v0.10 **não** restringe acesso a `127.0.0.1` / `localhost`
do host. Loopback continua acessível por default; o campo serve só
pra permitir conexões a IPs externos (ou non-loopback).

**Como detectar:** spike F6.0 — config com `allow_tcp_ports = []` e
`bash -c "curl http://localhost:31100"` retornou HTML normalmente,
mesmo com `Landlock: fully enforced`.

**Implicação prática:** ao implementar F6, **não é necessário**
estender `write_aijail_config()` com `extra_tcp_ports` pra deixar
a sessão Claude acessar containers Docker expostos em
`localhost:31xxx`. O default já funciona. Reduz superfície (1 PFC
do plano F6 vira no-op).

Se um dia o campo for usado pra liberar IPs não-loopback (e.g.,
DB remoto), aí sim entra no jogo. Pro caso "Docker no host expondo
em localhost", default é OK.
