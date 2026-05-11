# ADR-0020: Bootstrap de manifesto via sessão Claude efêmera + file watcher

- **Status:** Accepted
- **Data:** 2026-05-11
- **Decisores:** Marcos

## Contexto

ADR-0005 estabeleceu manifesto explícito (`.orchestrator/run.yml`). F6
expõe `▶ Run` no kanban — quando o projeto não tem manifesto, qual UX?
Três opções foram consideradas:

1. Modal in-app com template pré-preenchido (auto-detect via Dockerfile/
   package.json/pyproject.toml).
2. Daemon spawna sessão Claude efêmera com prompt "propor manifesto".
3. Erro toast linkado pra doc — usuário cria manual.

## Decisão

**Spawna sessão Claude efêmera no `project.path`**. Não vinculada a task
(sem `task_id`, sem `ClaudeSession` row, sem hook plumbing). Daemon
detecta o arquivo salvo via polling file watcher e broadcasta
`bootstrap.proposed` quando aparece.

**Flow:**

1. UI clica `▶ Run` → 422 `manifest_missing` (com `bootstrap_url` hint).
2. UI abre `BootstrapModal` → user clica "Iniciar bootstrap".
3. UI chama `POST /api/tasks/{task_id}/bootstrap-manifest`.
4. Daemon:
   - Valida task existe (ignora estado da task — bootstrap é
     project-scoped, não task-scoped).
   - Cria `<project.path>/.orchestrator/` se não existe.
   - `runtime.spawn(project_path)` — terminal nativo abre Claude no
     project root, sem token/base_url, sem `.claude/settings.json`,
     sem rastreio de PID.
   - `asyncio.create_task(watch_for_manifest(project_path, broadcaster))`
     — task background polla `<project_path>/.orchestrator/run.yml`
     a cada 2s, timeout 30min (900 iterations).
5. User interage com Claude no terminal: "leia o repo e proponha
   `.orchestrator/run.yml` seguindo o schema F6". Claude lê, propõe,
   user revisa, salva arquivo, idealmente commita.
6. Watcher detecta → `WsEvent.bootstrap_proposed(manifest_text=...)`
   broadcasted.
7. UI recebe via `useSessionEvents` → toast "Manifesto pronto. Tente
   Run de novo."
8. User clica `▶ Run` de novo → 201 happy path.

**Implementação:**

- `orchestrator/api/bootstrap.py::POST /tasks/{task_id}/bootstrap-manifest`
- `orchestrator/core/bootstrap.py::watch_for_manifest(project_path, broadcaster, *, interval=2.0, max_attempts=900)`
- Ref do `asyncio.Task` guardada em `app.state._bootstrap_watchers: set[Task]`
  (com `add_done_callback(discard)`) pra evitar GC prematuro (RUF006).

## Alternativas

1. **Template modal pré-preenchido** (rejeitada): template auto-detect via
   Dockerfile/package.json é heurística frágil e fica obsoleta. Claude
   propõe melhor manifesto pra cada projeto único.
2. **Erro toast + doc** (rejeitada): UX morta — usuário precisa sair do
   J-arvis, ler doc, criar arquivo, voltar. Bootstrap-by-AI é literalmente
   o motivo do J-arvis existir.
3. **Spawn como ClaudeSession (com `task_id`)** (rejeitada): polui o
   modelo task-first; bootstrap é project-scoped (manifesto serve a TODAS
   tasks do projeto). Sem `task_id` evita confusão.
4. **`watchdog` (inotify-based) em vez de polling** (rejeitada): polling
   simples basta pra arquivo singular; `watchdog` adiciona dep + complica
   shutdown clean. 2s × 900 attempts = 30min é generoso pro caso uso real
   (Claude propõe em 1-2min normalmente).

## Consequências

**Positivas**

- 0 manutenção de templates — Claude se adapta a estilos de projeto
  (Python/JS/Go/etc.).
- Manifesto fica commitado no repo — futuras tasks do mesmo projeto não
  precisam re-bootstrap.
- Bootstrap session é dispensável (efêmera): user pode mata-la no terminal
  sem efeito colateral no daemon.

**Negativas**

- Sessão efêmera não rastreia PID — se Claude trava ou usuario fecha
  sem salvar, daemon não sabe. Watcher 30min timeout cobre o caso
  "esqueceu e fechou".
- Manifesto inválido (Pydantic falha) não é detectado pelo watcher; só
  no próximo `▶ Run`. Aceitável: UX cíclica é o caminho natural.
- `asyncio.create_task` sem await: ref precisa ser guardada em
  `app.state` (RUF006). Implementado com set + discard callback.

## Referências

- Spec F6 §3 (decisão #4), §9 (Bootstrap UX flow)
- ADR-0005 (manifesto explícito), ADR-0008 (sessão em terminal nativo)
- `orchestrator/api/bootstrap.py`, `orchestrator/core/bootstrap.py`,
  `ui/src/components/BootstrapModal.tsx`
