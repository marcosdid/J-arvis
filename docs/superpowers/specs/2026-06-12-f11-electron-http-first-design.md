# F11 — Migração de shell: Wails → Electron com backend Go HTTP-first (design)

> **Status:** design (brainstorm 2026-06-10→12). Substitui o packaging NFPM
> planejado em F10.8 spec #2 pelo pipeline electron-builder (F11.3). O
> backend Go (`internal/`) é preservado integralmente; muda apenas o
> transporte UI↔backend (bindings Wails → HTTP+SSE local) e a casca
> (Wails → Electron).

## Problema

O J-arvis hoje é um app Wails v2: um binário Go que desenha a janela
(webview webkit2gtk com a UI React embutida) e roda toda a lógica. Três
dores acumuladas, confirmadas no brainstorm:

1. **Testes e2e com atrito estrutural.** O Playwright não dirige a webview
   do Wails. O workaround (`cmd/jarvis-e2e-http` + `ui/src/lib/e2e-shim.ts`)
   funciona (31 specs verdes), mas tem gaps documentados em
   `TEST-COVERAGE.md` e `gotchas.md`: o shim não faz push de eventos em
   tempo real (workaround `page.reload()` em `sessions-flow.spec.ts:73`),
   dialog nativo intestável (PRJ-12/13 bloqueados), tray/single-instance
   manual-only. 45 casos da matriz estão "harness-blocked".
2. **Dev loop pior que web puro.** `wails dev` + webkit2gtk vs Chrome
   devtools + hot reload do Vite.
3. **Multi-SO bloqueado pela casca.** Toda a integração OS (`internal/
   osintegration/`: tray fyne/systray, single-instance via D-Bus, hotkey
   golang.design) é implementação Linux-specific feita à mão. PRODUCT.md
   declara Linux-only no MVP, mas a direção agora inclui outros SOs — a
   casca não pode ser o bloqueio.

O brainstorm também fixou dois pontos que delimitam a solução:

- **Go fica.** O backend (12 pacotes em `internal/`, 207 testes unit) não é
  dor — reescrita em Node está descartada.
- **Recursos desktop nativos são inegociáveis**: tray, close-to-tray,
  hotkey global Super+J, single-instance, dialog nativo de pasta.

### Por que a migração é barata (mapeamento de acoplamento, 2026-06-10)

Workflow de exploração com 4 agentes mediu o acoplamento real ao Wails:

- **Backend:** só 2 arquivos importam Wails — `app.go` (1 método,
  `OpenDirectoryDialog`) e `internal/events/wails_runtime.go` (22 linhas,
  `EventsEmit` atrás da interface `events.Emitter`). Nenhum pacote de
  `internal/` depende de Wails. `osintegration/` usa fyne/systray + D-Bus
  (independente de Wails; será deletado de qualquer forma em favor das
  APIs Electron).
- **Frontend:** só 4 arquivos importam bindings gerados (`lib/api.ts`,
  `lib/ws.ts`, `hooks/useSandboxHealth.ts`, `components/MasterSidebar.tsx`).
  A camada `api.*` (singleton em `lib/api.ts`, com mapeamento de tipos
  `toTask`/`toProject`/...) isola os ~30 componentes consumidores.
- **O shim e2e já prova a arquitetura alvo:** com `?e2e=1&e2ePort=N` o
  React fala HTTP com o Go sem perceber. O `E2EServer`
  (`internal/api/http_e2e.go`) já expõe ~24 das 27 APIs via
  `POST /e2e/*`.
- **Já existe servidor HTTP local em produção:** `internal/localhttp`
  sobe em `127.0.0.1` (porta efêmera) servindo `/api/hooks/`, `/api/mcp`
  e `/api/runs/` — hooks do ai-jail e MCP do master já dependem dele
  (ADR-0009: bind local + token por sessão).

## Não-objetivos

- Reescrever qualquer lógica de `internal/` em Node/TS.
- Suporte macOS/Windows do **produto** (ai-jail, Docker, PTY continuam
  Linux-centric). F11 destrava a casca multi-SO; portar o produto é
  decisão futura separada.
- Mudanças de feature/UX na UI React — os ~30 componentes não são tocados
  (apenas `lib/api.ts`, `lib/ws.ts`, `useSandboxHealth.ts` e
  `MasterSidebar.tsx`).
- Auto-update do Electron — fora do MVP.
- Multi-cliente/acesso remoto — o servidor segue `127.0.0.1`-only com
  token; um único cliente (a janela) por instância.

## Decisões de design (do brainstorm)

| Pergunta | Resposta |
|---|---|
| Reescrever backend em Node? | **Não.** Go fica como processo separado (`jarvis-server`) |
| Transporte UI↔backend | **HTTP + SSE em 127.0.0.1**, generalizando `internal/localhttp` + template do E2EServer. Bearer token (padrão `mcpToken`) em todas as rotas `/api/*` |
| Estratégia de migração | **Dois passos**: F11.1 backend HTTP-first com Wails ainda de janela (app nunca quebra) → F11.2 casca Electron. Cada passo entrega valor sozinho |
| De onde a janela carrega a UI | **Do servidor Go** (`http://127.0.0.1:<porta>`), que já embute `ui/dist`. UI e API na mesma origem: zero CORS, e produção/dev/teste usam o mesmo caminho de código |
| Recursos nativos | **APIs Electron** (Tray, globalShortcut, requestSingleInstanceLock, dialog.showOpenDialog, close-to-tray) substituem `internal/osintegration/` inteiro |
| Eventos | **SSE** (`/api/events`): `SSEEmitter` implementa `events.Emitter` (mesmo contrato do `WailsEmitter`). WebSocket só se o terminal do master provar que SSE não basta (validar cedo em F11.1) |
| Packaging | **electron-builder** (.deb + .AppImage; binário Go como extraResource). Substitui o plano NFPM de F10.8 spec #2 |
| Registro da mudança de direção | **ADR novo** ("casca Electron + backend Go local; multi-SO da casca") — PRODUCT.md declara Linux-only e a decisão muda direção registrada |

## Arquitetura final

```
┌────────── Electron ──────────┐      ┌────── jarvis-server (Go) ──────┐
│ main process (TS):           │      │ internal/* intacto:            │
│  • spawna jarvis-server,     │      │  store, core, git, sandbox,    │
│    lê porta+token do stdout  │      │  master, mcp, hooks, events    │
│  • Tray, Super+J, single-    │      │                                │
│    instance, dialog, close-  │      │ HTTP em 127.0.0.1 (efêmera):   │
│    to-tray                   │ ───▶ │  • GET /        → UI (dist)    │
│  • BrowserWindow → carrega   │ HTTP │  • /api/*       → 25+ rotas    │
│    http://127.0.0.1:<porta>  │ +SSE │  • /api/events  → SSE push     │
│ preload: window.native.*     │      │  • /api/hooks, /api/mcp (já    │
│ React: fetch() + EventSource │      │    existem hoje)               │
└──────────────────────────────┘      └────────────────────────────────┘
```

## F11.1 — Backend HTTP-first (Wails continua de janela)

**Go:**

- Novo pacote `internal/httpapi`: handlers HTTP para as APIs hoje
  Wails-bound (Tasks, Projects, Worktrees, Sessions, Runs, Catalog,
  Bootstrap, Master, Health), montados em `internal/localhttp` sob
  `/api/*`. Os handlers do `E2EServer` (`internal/api/http_e2e.go`;
  `cmd/jarvis-e2e-http/` é só o entrypoint) são promovidos/movidos pra
  cá — produção e e2e passam a usar o mesmo código. Completar a
  cobertura de `MasterAPI` (hoje 1/5 no shim).
- `internal/events`: novo `SSEEmitter` (broadcast com mutex + canal por
  cliente conectado, endpoint `/api/events`). `WailsEmitter` permanece
  durante F11.1 — os dois emitem em paralelo (UI escolhe o canal), e o
  Wails só é desligado em F11.2.
- Token: gerar bearer token de app no boot (reuso do padrão
  `mcp.NewBearerToken`), exigido nas rotas `/api/*` novas. `/api/hooks/`
  (token próprio por sessão) e `/api/mcp` (token próprio, ADR-0009)
  mantêm seus tokens distintos — não migram pro token de app.
- Servir `ui/dist` (o `embed.FS` que hoje o Wails consome) como rota `GET /`
  do localhttp — preparação pra F11.2 e base do dev/test flow.

**React:**

- `lib/api.ts`: trocar bindings por `fetch()` nas mesmas funções públicas
  (`api.listTasks()` etc. não mudam de assinatura; mapeamentos
  `toTask`/`toProject` permanecem). Porta+token: em F11.1 a página ainda
  é servida pelo asset server do Wails (sem query params), então um
  binding temporário `GetServerConfig()` em `app.go` entrega
  `{port, token}` no boot — mesmo padrão do `ChooseDirectory` retido,
  deletado junto com ele em F11.2 (no Electron, a config chega via
  query param/preload).
- `lib/ws.ts`: trocar `EventsOn/EventsOff` por `EventSource` em
  `/api/events`.
- `MasterSidebar.tsx` e `useSandboxHealth.ts`: refatorar pra passar pela
  camada central (eliminar os imports diretos de bindings).
- `ChooseDirectory`: continua via binding Wails **somente neste passo**
  (único binding remanescente; vira `window.native.chooseDirectory()` em
  F11.2).

**E2E:** specs passam a rodar contra o servidor real (rotas `/api/*` em
vez de `/e2e/*`); eventos em tempo real viram testáveis (remover os
`page.reload()`); validar streaming do master via SSE (gate do risco #1).

**Critério de saída de F11.1:** app Wails funcionando normal para o
usuário; suíte e2e verde contra `/api/*` com push de eventos real;
`pnpm dev` no Chrome contra o servidor Go funcional.

## F11.2 — Casca Electron substitui o Wails

- Novo diretório `desktop/` (workspace pnpm): `main.ts` (~200-300 linhas),
  `preload.ts` (contextBridge expõe `window.native.chooseDirectory()`),
  `electron-builder.yml`.
- Main process: spawna `jarvis-server`, lê `JARVIS_PORT=`/`JARVIS_TOKEN=`
  do stdout (mesmo padrão `E2E_HTTP_PORT=` do harness), health-check,
  abre `BrowserWindow` em `http://127.0.0.1:<porta>`; implementa Tray,
  globalShortcut (Super+J), requestSingleInstanceLock (foca janela
  existente), close-to-tray, dialog de pasta via `ipcMain.handle`.
- Lifecycle: ao sair, SIGTERM no filho; o Go preserva o shutdown ordenado
  de hoje (master → localhttp), movido de `OnShutdown` do Wails para
  handler de sinal. Se o filho morrer: dialog com causa + opção de
  reiniciar (melhor que hoje, onde um panic do Go fecha o app sem aviso).
- **Código deletado:** `internal/osintegration/` inteiro, `app.go`,
  `WailsEmitter`, deps Wails do `go.mod`, `wails.json`,
  `cmd/jarvis-e2e-http` + `e2e_server*.go` + `lib/e2e-shim.ts` (a
  arquitetura de produção já é testável diretamente), bindings gerados
  `ui/src/wailsjs/`.
- `main.go` → `cmd/jarvis-server/main.go` (sem nenhum import Wails).

**Critério de saída de F11.2:** paridade funcional com o app Wails
(janela, tray, hotkey, single-instance, dialog, close-to-tray) validada
por checklist manual + smoke `_electron`; suíte e2e verde; zero
referências a Wails no repo.

## F11.3 — Packaging

- electron-builder gerando `.deb` e `.AppImage` (targets mac/win ficam
  configuráveis, desativados). Binário `jarvis-server` como
  `extraResources`; Makefile orquestra `go build` → `vite build` →
  `electron-builder`.
- Assets desktop (ícone, .desktop file) migram do plano F10.8 spec #2.
- ADR registrando a mudança de direção (casca Electron, multi-SO da casca
  destravado, supersede o "Linux-only" da casca em PRODUCT.md §2) +
  atualização de ARCHITECTURE.md/PRODUCT.md.

**Critério de saída de F11.3:** `.deb` e `.AppImage` instaláveis num
Ubuntu 22.04+ limpo, app funcional end-to-end; docs vivos atualizados.

## Tratamento de erros

- **`jarvis-server` morre:** Electron detecta exit do filho → dialog com
  stderr capturado + botão reiniciar.
- **Porta:** efêmera (`:0`), zero conflito; cliente descobre via stdout.
- **Token inválido/ausente:** `/api/*` responde 401; UI mostra erro de
  conexão (reusa `ErrorBanner` de WS-down).
- **SSE cai:** `EventSource` reconecta automático (nativo); React Query
  re-sincroniza no reconnect (padrão atual de invalidação por evento).
- **Segunda instância:** `requestSingleInstanceLock` foca a janela
  existente (paridade com D-Bus de hoje).

## Estratégia de testes

- **Unit Go:** handlers de `internal/httpapi` com `httptest`;
  `SSEEmitter` com clientes fake. `FakeEmitter` e os 207 testes atuais
  permanecem. TDD (ADR-0004) vale pra todo código novo.
- **Unit React (vitest):** `lib/api.ts` HTTP com MSW (já é dep);
  `lib/ws.ts` com EventSource fake.
- **E2E (suíte principal):** Playwright + Chromium contra `jarvis-server`
  real — os 31 specs migram (já falam HTTP); casos "harness-blocked" por
  eventos saem da lista; dialog vira testável via stub no main process.
- **Smoke Electron:** 3-5 testes `_electron.launch` (janela abre, tray
  existe, dialog stubado, single-instance) — hoje 100% manual.

## Riscos

1. **Streaming do master (xterm) via SSE** — `master.output` em alta
   frequência. Mitigação: validar no início de F11.1 com sessão real;
   fallback WebSocket no mesmo servidor se SSE engasgar. Localhost torna
   o risco baixo.
2. **Tamanho/RAM:** binário ~25MB → ~120MB+ (Chromium embutido). Preço
   aceito conscientemente no brainstorm em troca de teste/dev/multi-SO.
3. **Dois processos pra orquestrar** (casca + servidor) — mitigado pelo
   lifecycle explícito (spawn/health-check/SIGTERM) e pelo dialog de
   crash, ambos testáveis via `_electron`.
4. **Período de transição F11.1** (dois emitters em paralelo) — curto e
   com o Wails ainda como caminho primário do usuário; e2e cobre o
   caminho novo desde o primeiro dia.
