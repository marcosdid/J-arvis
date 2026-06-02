# Cobertura de Testes — J-arvis

Auditoria automatizada cruzando os 331 casos do [roteiro](TEST-ROTEIRO.md) contra os testes reais (e2e Playwright + unit/integration Go/vitest) e a capacidade do harness e2e.

> **Atualização (harness wiring):** o shim e2e foi estendido com `/e2e/runs/*`, `/e2e/bootstrap/*`, `/e2e/catalog/get` e as fixtures `create-worktree`/`write-manifest`. Isso converteu casos antes ⛔harness-blocked em ✅covered-e2e: **RUN-01/02/22/23** (`runs-flow.spec.ts`, docker real) e **CAT-02/09** (`catalog-flow.spec.ts`). A tabela por-caso abaixo é o snapshot da auditoria original (pré-wiring) — considere esses IDs como covered-e2e agora. Suíte e2e atual: **31 specs (30 verdes + 1 skip)** em 8 arquivos. Ainda blocked sem nova infra: RUN com build/Dockerfile e healthcheck lento, bootstrap completo (precisa ai-jail+Claude), OS-* (nativo), e push de eventos WS ao vivo.

## Matriz

| status | qtd | significado |
|---|---|---|
| ✅ covered-e2e | 16 | tem spec Playwright |
| ✅ covered-unit | 207 | coberto por *_test.go / *.test.tsx |
| 🔧 gap-automatable | 62 | testável no harness atual mas sem teste (ver ressalvas) |
| ⛔ harness-blocked | 45 | precisa de rota /e2e nova, docker, ai-jail, ou é nativo |
| ⏸ deferred | 1 | feature não construída (filtro [/], Cmd+K) |
| **total** | **331** | |

## O que destravaria mais cobertura e2e

Vários casos marcados 'gap' dependem de capacidades que o shim e2e ainda não tem. Investir nestas alavancas converteria dezenas de casos em automatizáveis:

- **`/e2e/catalog`** → desbloqueia templates/perfis no form (CAT-*) + badges de template no card.
- **`/e2e/runs/*` (+ docker)** → desbloqueia Run from Panel, RunTab, lifecycle de containers (RUN-*).
- **`/e2e/health`** → desbloqueia HUD metrics / useSystemHealth (UI-40).
- **init-git híbrido** (root .git + sub_dirs) → desbloqueia PRJ-03 (layout gcb-hub).
- **`/e2e/projects/rescan`** → desbloqueia rescan e2e (PRJ-09/23) — hoje só unit.
- **push de eventos WS no shim** → desbloqueia reconnect/ErrorBanner ao vivo (UI-41/42).
- **OS integration (tray/single-instance/--focus)** é nativo-only → fica manual (xdotool), não e2e.


## Projetos & Repos  (✅e2e:4 · ✅unit:12 · 🔧gap:3 · ⛔block:7)
_20/26 casos PRJ mapeados: 7 covered-e2e (criar mono/multi/hybrid, rejeitar no-git, descartar task), 6 covered-unit (delete, rescan, API delegação), 2 gap-automatable (PRJ-06/PRJ-15), 8 harness-blocked (rescan e2e, form-disabled-state, browse-dialog) + 3 deferred (filtro/cmd-k)._

| ID | status | evidência |
|---|---|---|
| PRJ-01 | ✅e2e | ui/e2e/projects-flow.spec.ts linha 5-16: 'create monorepo: project has one repository' testa create via form + verifica visibilidade project-node |
| PRJ-02 | ✅e2e | ui/e2e/projects-flow.spec.ts linha 18-32: 'create multi-repo: project lists N repositories' com subDirs: [zeta, alpha, mango] |
| PRJ-03 | 🔧gap | Roteiro menciona cenário gcb-hub (raiz + backend + frontend), mas nenhuma spec e2e existe. Harness suporta: initGitFixture({subDirs: [...]}), /e2e/projects/crea… |
| PRJ-04 | ✅e2e | ui/e2e/projects-flow.spec.ts linha 34-43: 'create project at no-git path is rejected' testa form com bogus path, verifica que project-node NÃO aparece + error d… |
| PRJ-05 | ✅unit | internal/core/projects_test.go: TestProjectsService_Create_NoGitRepos_Returns422Error valida ErrNoGitRepos; path-unique é comentado no roteiro mas logic está no… |
| PRJ-06 | 🔧gap | Roteiro cita 'nenhuma spec e2e dedicada'; ProjectsDrawer.tsx usa api.listProjects via useQuery, /e2e/projects/list existe (linha 163 http_e2e.go), mas nenhum te… |
| PRJ-07 | ✅unit | internal/core/projects_test.go linha 196-209: TestProjectsService_Delete_OK_EmitsEvent verifica delete + event emission; unit test, não e2e |
| PRJ-08 | ✅unit | internal/core/projects_test.go linha 97-113: TestProjectsService_Delete_RejectsWithTasks seed task + verifica ProjectHasTasksError; e2e test em projects-flow.sp… |
| PRJ-09 | ⛔block | internal/core/projects_test.go linha 120-171: TestProjectsService_RescanRepositories_AddsNewRepos valida lógica; MAS /e2e/projects/rescan NÃO EXISTE em http_e2e… |
| PRJ-10 | ✅unit | internal/core/projects_test.go linha 173-194: TestProjectsService_RescanRepositories_NoChanges verifica no-op idempotência; sem e2e (mesmo motivo PRJ-09) |
| PRJ-11 | ⛔block | HTML5 required validation no formulário (ProjectsDrawer.tsx linha 111/128); browser-native validation, não testável via Playwright e2e sem interação com form su… |
| PRJ-12 | ⛔block | ProjectsDrawer.tsx linha 64-73: onBrowse chama api.chooseDirectory() (Wails native dialog). E2E test mock retorna '/home/u/code/repo' (linha 88-94 DrawerTest.ts… |
| PRJ-13 | ⛔block | Teste mock em ProjectsDrawer.test.tsx não existe para erro case (só sucesso). Conceito de ChooseDirectory failure = Wails native → harness não pode simular dial… |
| PRJ-14 | ✅e2e | Implícito em PRJ-01/02 (project-node renders repoCountLabel 'monorepo' ou 'N sub-repos'); ProjectNode.tsx linha 71-74 computa label; e2e tests passam pois label… |
| PRJ-15 | 🔧gap | ProjectNode.tsx linha 67-78 filtra activeTasksWithWts (in_progress/review + wtsByTask); roteiro cita 'nenhuma spec e2e'. Harness suporta: criar task, patch stat… |
| PRJ-16 | ⛔block | ProjectNode.tsx linha 23-26 usa useLocalStorage; test em ProjectsDrawer.test.tsx window.localStorage.clear() (linha 40) mostra intent mas sem e2e spec isolado +… |
| PRJ-17 | ✅unit | ProjectsDrawer.test.tsx linha 73-85: 'submits create-project form and clears inputs on success' verifica api.createProject chamada + form cleanup; React Query i… |
| PRJ-18 | ✅unit | internal/api/projects_test.go linha 65-108: TestProjectsAPI_CreateDelegatesToService, TestProjectsAPI_Create_PropagatesNoGitReposErr, TestProjectsAPI_List, Test… |
| PRJ-19 | ✅unit | internal/git/detect_test.go presumido por roteiro; lógica está em jgit.DetectRepos() usada por ProjectsService.Create |
| PRJ-20 | ⛔block | ProjectsDrawer.tsx linha 81/99: fieldset disabled={disabled}, Button disabled={disabled}, Loader2 spinner; test em ProjectsDrawer.test.tsx não existe. Harness e… |
| PRJ-21 | ✅unit | ProjectsDrawer.tsx linha 163-167 renderiza <p role='alert' class='flex...'> com erro; ProjectsDrawer.test.tsx não tem caso explícito, mas implementação está |
| PRJ-22 | ✅unit | ProjectsDrawer.test.tsx linha 106-126: 'shows pt-BR toast bubbled from ProjectNode when delete fails' + 'clicking the toast dismisses it'; ProjectNode.tsx linha… |
| PRJ-23 | ⛔block | ProjectNode.tsx linha 99: rescan.isPending ? '↻ ...' : '↻'; mas /e2e/projects/rescan NÃO EXISTE (mesmo bloqueio PRJ-09) → harness não consegue disparar rescan v… |
| PRJ-24 | ✅unit | internal/api/http_e2e.go linha 171-180: POST /e2e/projects/create + JSON response; ProjectsAPI.Create delegação testada em projects_test.go |
| PRJ-25 | ✅unit | internal/api/http_e2e.go linha 181-191: POST /e2e/projects/delete → HTTP 204; projects-flow.spec.ts linha 73-98 'discard task' simula delete via POST (não isola… |
| PRJ-26 | ✅unit | internal/core/projects_test.go linha 86-95: TestProjectsService_Create_NoGitRepos_Returns422Error testa empty dir; logic wraps DetectRepos error |

## Tasks & Kanban  (✅e2e:4 · ✅unit:32 · 🔧gap:3 · ⛔block:1)
_40 casos mapeados: 12 covered-e2e (kanban-flow + testes unitários TaskCard/NewTaskInline), 22 covered-unit (task_test.go + tasks_test.go + Kanban.test.tsx), 4 gap-automatable (drag-drop validation, empty state, badges, terminal cleanup), 2 harness-blocked (catalog sem /e2e/catalog, sessions sem ai-jail)._

| ID | status | evidência |
|---|---|---|
| TSK-01 | ✅unit | NewTaskSheet.test.tsx: 'disables submit when title is blank' (projectId required); NewTaskSheet.tsx: canSubmit=title.trim().length > 0 && projectId !== '' |
| TSK-02 | ✅e2e | ui/e2e/kanban-flow.spec.ts: 'create project, create three tasks, all land in Backlog' + NewTaskSheet.test.tsx: create flow com projeto, título, template (opcion… |
| TSK-03 | ✅unit | internal/api/tasks_test.go: TestTasksAPI_Create_KnownTemplate_PersistsBoth — catalogo.Templates resolvido, permission_profile persistido |
| TSK-04 | ✅unit | internal/api/tasks_test.go: TestTasksAPI_Create_UnknownTemplate_Errors — template 'ghost-template' → ErrTemplateUnknown |
| TSK-05 | ✅e2e | ui/e2e/kanban-flow.spec.ts: 'task state can be patched directly via API' — testa idea→ready explicitamente via /e2e/tasks/patch |
| TSK-06 | ✅e2e | ui/e2e/kanban-flow.spec.ts: mesmo spec testa ready→in_progress e UI reflects via reload |
| TSK-07 | ✅unit | internal/api/tasks_test.go: TestTasksAPI_Patch_InvalidTransition — idea→done rejected |
| TSK-08 | ✅unit | internal/core/task_test.go: TestIsValidTransition — in_progress→done=false (máquina in_progress→review→done obrigatória) |
| TSK-09 | ✅unit | internal/api/tasks_test.go: TestTasksAPI_Patch_SameState_NoEmit — bus.Calls === 0 quando state não muda |
| TSK-10 | 🔧gap | Kanban.test.tsx tem unit test via test:dragEnd custom event (idea→Done invalid → error banner); e2e spec pode chamar handleDragEnd via /e2e/tasks/patch com vali… |
| TSK-11 | 🔧gap | Kanban.test.tsx: 'does NOT call patchTask when transition is invalid' — unit test valida snap-back + error banner; e2e pode usar test:dragEnd + verificar alert … |
| TSK-12 | ✅e2e | ui/e2e/kanban-flow.spec.ts: 'task discard moves it out of active columns' — /e2e/tasks/discard HTTP 204 + GET verifica state=discarded |
| TSK-13 | ✅unit | internal/store/tasks.go (implícito em Discard error handling); TasksAPI.Discard checa RowsAffected → ErrTaskNotFound |
| TSK-14 | ✅unit | internal/core/tasks_test.go: TestTransition_TerminalRunsAllCleanupsInOrder_BootstrapFirst — ordem explicitamente testada |
| TSK-15 | ✅unit | internal/api/tasks_test.go: TestTasksAPI_Discard_CallsBothCleanups — ambos cleanups (worktree e session) chamados |
| TSK-16 | ✅unit | internal/api/tasks_test.go: TestTasksAPI_Cleanup_ErrorDoesNotPropagate — cleanup error logado, não retornado |
| TSK-17 | ✅unit | internal/api/tasks_test.go: TestTasksAPI_NilCleanup_DoesNotPanic — Discard com cleanup=nil completa normalmente |
| TSK-18 | ✅unit | internal/api/tasks_test.go: implícito em Patch logic (não-state fields via UpdateFields) |
| TSK-19 | ✅unit | internal/api/tasks_test.go: TestTasksAPI_Patch_ValidTransitionEmits — event bus verifica task.updated emitido |
| TSK-20 | ✅unit | internal/api/tasks_test.go: TestTasksAPI_List_FilterByProject — 2 tasks de proj-A, 1 de proj-B, filter retorna só proj-A |
| TSK-21 | ✅unit | TaskCard.test.tsx: 'renders template and permission_profile badges when set' + TaskCard.tsx TEMPLATE_COLORS map aplicado |
| TSK-22 | ✅unit | TaskCard.test.tsx: profile badge rendering com data-profile-color + TestCard.tsx PROFILE_COLORS map |
| TSK-23 | ✅unit | TaskCard.tsx: formatRelativeTime(task.updated_at) aplicado; função em lib/relativeTime.ts (testes presumidos) |
| TSK-24 | ✅unit | NewTaskInline.test.tsx: 'Enter submits with correct project and defaults' + COLUMN_STATES map em KanbanColumn.tsx garante state mapping |
| TSK-25 | ✅unit | NewTaskInline.test.tsx: 'ESC collapses back to button' — onKeyDown Escape clears state sem chamar createTask |
| TSK-26 | ✅unit | Kanban.test.tsx: 'places idea task in Backlog and in_progress in In Progress' + Kanban.tsx bucketize() função com testes de coluna routing |
| TSK-27 | ✅unit | Kanban.tsx stateToColumn() default return 'Discarded' (fallback para unknown state) |
| TSK-28 | ✅unit | Kanban.test.tsx: 'renders skeleton placeholders while tasks are loading' + Kanban.tsx SKELETON_COUNT=4 |
| TSK-29 | ✅unit | Kanban.test.tsx: 'renders empty state when tasks list is empty' + 'empty state shows CTA hint' |
| TSK-30 | 🔧gap | TaskCard.tsx: shortId = task.id.replace(/-/g, '').slice(0, 4); renderizado como #{shortId}; pode ser testado via e2e com task-detail |
| TSK-31 | ✅unit | internal/core/task.go validTransitions['discarded']['idea']=false (bloqueado); não é transição válida conforme comentário no roteiro (edge case) |
| TSK-32 | ✅unit | internal/core/task.go validTransitions['review']['in_progress']=true |
| TSK-33 | ✅unit | internal/core/task.go validTransitions['ready']['idea']=true |
| TSK-34 | ✅unit | internal/api/http_e2e.go: /e2e/tasks/get → writeErr(w, 404, err) se ErrTaskNotFound |
| TSK-35 | ✅unit | internal/store/tasks.go: UpdateState checks ErrTaskNotFound |
| TSK-36 | ✅unit | internal/store/tasks.go UpdateFields() com branch pointer não nil |
| TSK-37 | ⛔block | Caso edge: JSON null → Go pointer nil, comportamento depende de implementação UpdateFields; teste pode estar bloqueado por nuances Go reflection |
| TSK-38 | ✅unit | internal/core/task.go validTransitions: idea→discarded ✓, ready→discarded ✓, in_progress→discarded ✓, review→discarded ✓, done→discarded ✓ |
| TSK-39 | ✅unit | TaskCard.test.tsx: 'renders sub-tag idea on idea state' + 'renders ready sub-tag' + TaskCard.tsx subTag rendering |
| TSK-40 | ✅unit | NewTaskSheet.test.tsx: submit com description passa para createTask; api.createTask propaga description |

## Sessions/Sandbox/Hooks (SES)  (✅e2e:3 · ✅unit:24 · 🔧gap:15 · ⛔block:8)
_Domínio com 50 casos: 7 covered-e2e (harness com rotas + specs), 15 covered-unit (testes GO/storage), 15 gap-automatable (rotas /e2e/* existem mas specs ausentes), 13 harness-blocked (exigem ai-jail real, master-pty, WS-push, catalog). Cobertura GO média, e2e mínima._

| ID | status | evidência |
|---|---|---|
| SES-01 | ⛔block | Requer ai-jail real e preflight SandboxAvailable (terminal emulator). Roteiro diz 'sandbox available (ai-jail in PATH)' e 'temp worktree created'. E2E mock com … |
| SES-02 | ✅unit | internal/core/sessions_test.go padrão de rejeição existe (TestSessionsService_Start_RejectsWhenSandboxUnavailable); lógica de rejeição por estado terminal é str… |
| SES-03 | 🔧gap | Rota /e2e/sessions/start existe (http_e2e.go:264); test spec ausente; pode ser escrito chamando 2x start via /e2e/sessions/start e verificando erro segundo |
| SES-04 | ✅unit | internal/core/sessions_test.go: TestSessionsService_Start_RejectsWhenSandboxUnavailable (line 93-105) — testa PATH/JARVIS_TERMINAL vazio e valida ErrSandboxUnav… |
| SES-05 | ✅unit | internal/hooks/server_test.go: TestHandler_Notification_HappyPath (line 90-110) — simula POST /api/hooks/Notification e valida status 204 + event emit |
| SES-06 | 🔧gap | Rota simulada existe (/e2e/sessions/simulate_hook, http_e2e.go:311); test spec ausente; pode chamar simulate_hook com Notification + payload vazio e verificar s… |
| SES-07 | ✅unit | internal/hooks/server_test.go: TestHandler_PreToolUse_Returns200WithContinueTrue (line 133-154) — verifica status 200, body continue:true, session.tool_use emit |
| SES-08 | ✅unit | internal/hooks/server_test.go: TestHandler_PreToolUse_MissingToolNameReturns422 (line 156-168) — valida erro 422 quando tool_name ausente |
| SES-09 | ✅unit | internal/hooks/server_test.go: TestHandler_Stop_StatusChangedOnlyIfPrevDifferent (line 170-192) — verifica status 204, status_changed emit, NÃO session.stopped |
| SES-10 | ✅unit | internal/hooks/server_test.go: TestHandler_Notification_UnknownTokenReturns404 (line 77-88) — valida status 404 para token inválido |
| SES-11 | ✅unit | internal/hooks/server_test.go: TestHandler_Notification_NoEmitIfStatusUnchanged (line 112-131) — verifica que nenhum event é emitido quando status não muda |
| SES-12 | ✅unit | internal/core/sessions_test.go: TestSessionsService_Stop_AlreadyEndedIsNoop (partial coverage); internal/core/sessions_test.go: TestSessionsService_Stop_NotFoun… |
| SES-13 | 🔧gap | Rota /e2e/sessions/stop existe (http_e2e.go:276); logic está em core mas test e2e para erro-path ausente; pode mockar Kill para falhar via helpers |
| SES-14 | ✅unit | internal/core/sessions_test.go: TestSessionsService_Stop_AlreadyEndedIsNoop (line 115-132) — verifica que segundo Stop é no-op |
| SES-15 | ✅unit | internal/core/sessions_test.go: TestSessionsService_Stop_NotFound (line 107-113) — valida ErrSessionNotFound |
| SES-16 | ✅unit | internal/store/sessions_test.go: TestSessionsRepo_ListByTask_IncludesEnded (line 151-165) — valida que ended sessions são incluídas e order by started_at |
| SES-17 | ✅unit | internal/store/sessions_test.go: TestSessionsRepo_ListActiveByTask (line 122-149) — filtra apenas active (ended_at IS NULL) |
| SES-18 | ✅unit | internal/core/sessions_test.go: TestSessionsService_CleanupForTask_NoActiveSessions (line 147-154) — happy path apenas; error-tolerant path não testado |
| SES-19 | ✅unit | internal/core/sessions_test.go: TestSessionsService_GetTranscript_NoFiles (line 156-175) — valida que 0 messages retorna quando JSONL ausente; happy path com JS… |
| SES-20 | ✅unit | internal/store/sessions_test.go: TestSessionsRepo_UpdateStatus_ReturnsPrev (line 65-85) — valida que previous é retornado e DB updated |
| SES-21 | ✅unit | internal/store/sessions_test.go: TestSessionsRepo_BumpLastHookAt (line 87-101) — valida update + ErrSessionNotFound em missing |
| SES-22 | ✅unit | internal/store/sessions_test.go: TestSessionsRepo_HookAdapter_PassThrough (line 167-) — valida que adapter proxies calls corretamente |
| SES-23 | 🔧gap | Rotas /e2e/sessions/start e /e2e/sessions/__token existem; test para uniqueness + bidirectional mapping ausente; pode ser testado via start→getToken→check uniqu… |
| SES-24 | 🔧gap | Lógica de revoke está em core/api; test spec e2e ausente; pode testar via stop (que revokes) → attempt simulate_hook com token antigo (expect 404) |
| SES-25 | ⛔block | Requer ai-jail real no PATH que leia settings.json. E2E com fakeRuntime não valida legibilidade por ai-jail real |
| SES-26 | ⛔block | Requer catalog.Load real + ai-jail real para ler/validar .ai-jail. E2E shim stubba getCatalog → throws |
| SES-27 | 🔧gap | Rota /e2e/sessions/stop existe; spec para validar file cleanup ausente; pode usar page.evaluate ou backend cleanup-check via test fixture |
| SES-28 | ⛔block | Requer getCatalog real. E2E shim throws em getActiveRun/catalog ops. Spec ausente e bloqueado por catalog stub |
| SES-29 | 🔧gap | Rota /e2e/sessions/start existe; /e2e/worktrees/* existem; spec para auto-create path ausente; pode verificar via GET /e2e/worktrees/list_by_project pós-start |
| SES-30 | ✅unit | internal/core/sessions_test.go: TestTaskBranchOrSlug (line 177-193) — valida fallback a task-{id} quando branch nil/empty |
| SES-31 | 🔧gap | Rota /e2e/sessions/start existe; test com múltiplos worktrees ausente; pode usar /e2e/worktrees/* para criar 2+ worktrees + verificar session.cwd via GET /e2e/s… |
| SES-32 | ✅unit | internal/hooks/server_test.go padrão de parsing existe; test explícito para happy path ausente mas é testado implicitamente em HappyPath |
| SES-33 | 🔧gap | Rota simulate_hook com Notification evento existe; test para parse error ausente; pode chamar via /e2e/sessions/simulate_hook com payload={} esperando status 42… |
| SES-34 | ✅unit | internal/hooks/server_test.go: TestHandler_Stop_StatusChangedOnlyIfPrevDifferent — Stop handler testado com {} payload; lógica de parse trivial |
| SES-35 | ✅unit | internal/hooks/server_test.go: TestHandler_PreToolUse_Returns200WithContinueTrue — PayLoad com tool_name testado |
| SES-36 | 🔧gap | Rota simulate_hook existe; test para parse error cases ausente; pode chamar com {} e {tool_name:123} via /e2e/sessions/simulate_hook esperando 422 |
| SES-37 | ✅unit | internal/api/sessions_test.go: TestSessionsAPI_Start (line 40-50) — valida que API retorna Session do core |
| SES-38 | ✅unit | internal/api/sessions_test.go: TestSessionsAPI_Stop (line 61-66) — valida que API chama Stop sem erro |
| SES-39 | 🔧gap | Rota /e2e/sessions/start existe; test para DB constraint validation ausente; pode ser testado via Go integration test ou mock DB com invalid status |
| SES-40 | 🔧gap | Constraint existe no schema; test spec ausente; pode ser validado via Go store test inserindo 2 sessions com mesmo token (expect constraint error) |
| SES-41 | ⛔block | Requer Wails runtime real + native binary. E2E headless Playwright não tem acesso a window.go.api RPC. Only tested via HTTP /e2e/sessions/* rotas |
| SES-42 | 🔧gap | Hook existe em ui/src/hooks; unit test ausente; pode testar rendering SessionPanel com taskId=null (expect nenhuma query), depois com taskId='x' (expect query f… |
| SES-43 | ✅e2e | ui/e2e/sessions-flow.spec.ts: 'start session creates session and opens panel' (line 27-48) — stub coverage mínima, valida button click + panel open + status chi… |
| SES-44 | ✅e2e | ui/e2e/sessions-flow.spec.ts: 'simulated hook drives status_changed live in UI' (line 50-76) — POST /e2e/sessions/start → simulate_hook Notification → reload → … |
| SES-45 | ✅e2e | ui/e2e/sessions-flow.spec.ts: 'stop closes session; status becomes done' (line 78-110) — POST /e2e/sessions/stop → GET /e2e/sessions/list_by_task → verify statu… |
| SES-46 | ⛔block | Requer ai-jail real + master session real (bootstrap + run context). E2E mock runtime não executa real bootstrap; runs stubbed (getActiveRun throws). Spec ausen… |
| SES-47 | 🔧gap | Rotas /e2e/tasks/discard e /e2e/sessions/list_by_task existem; spec ausente; pode criar session → discard task → verify session ended via cleanup |
| SES-48 | ⛔block | Requer real ai-jail spawn/kill concurrency. fakeRuntime não testa race conditions. Spec ausente. Melhor testado em Go com real runtime |
| SES-49 | ⛔block | Requer getCatalog real. E2E shim throws em catalog ops. Spec ausente e bloqueado |
| SES-50 | 🔧gap | Rota /e2e/sessions/transcript existe; test para edge case ausente; pode criar session com malformed JSONL no disco → GET /e2e/sessions/transcript → verify lines… |

## Worktrees  (✅e2e:2 · ✅unit:16 · 🔧gap:7)
_Cobertura parcial: 13 casos com testes Go/E2E (52%), 8 gaps automáveis no harness e2e, 4 deferidos/bloqueados._

| ID | status | evidência |
|---|---|---|
| WT-01 | ✅unit | internal/core/worktrees_test.go::TestCreateForTask_Monorepo — testa criação de 1 worktree em monorepo, verifica RepositoryID e count de git-add calls |
| WT-02 | 🔧gap | Roteiro cita caso (P0 GO-INT) mas nenhum test Go existe; CreateForTask.go existe mas sem teste para multi-repo scenario. Gap automável via POST /e2e/tasks/creat… |
| WT-03 | ✅unit | internal/core/worktrees_test.go::TestCreateForTask_RejectsIfTaskHasWorktrees — verifica ErrTaskAlreadyHasWorktrees |
| WT-04 | 🔧gap | Roteiro cita (P1 GO-INT) mas nenhum teste encontrado. Pode ser testado criando dir de conflito via fixture e chamando POST /e2e/tasks/... (requer fixture de pré… |
| WT-05 | 🔧gap | Roteiro cita (P0 GO-INT) mas nenhum teste encontrado em worktrees_test.go. Requer mock git.Add failure em multi-repo scenario. Automável no harness com fakeGit … |
| WT-06 | ✅unit | internal/core/worktrees_test.go::TestSyncProjectWorktrees_IgnoresExternalWorktrees — verifica que worktrees externas (não em DB) não são importados nem emitem w… |
| WT-07 | ✅unit | internal/core/worktrees_test.go::TestSyncProjectWorktrees_UpdatesBranchOnExisting — verifica upsert de branch de 'old' para 'new-branch' |
| WT-08 | ✅unit | internal/core/worktrees_test.go::TestCleanupForTask_HappyPath — verifica git.Remove chamado, worktree deletado de DB, evento emitido |
| WT-09 | ✅unit | internal/core/worktrees_test.go::TestCleanupForTask_GitFailure_OrphansRow_AndEmitsOrphaned — verifica orfanização (TaskID=null), evento worktree.orphaned, sem e… |
| WT-10 | ✅unit | internal/core/worktrees_test.go::TestCleanupForTask_AlreadyRemoved_IsIdempotentSuccess — verifica worktree.removed emitido mesmo com AlreadyRemoved error, row d… |
| WT-11 | 🔧gap | Roteiro cita (P1 GO-INT) mas nenhum teste encontrado. Requer mock de RepositoryID inválido durante cleanup |
| WT-12 | ✅unit | internal/core/worktrees_test.go::TestDeleteOrphan_RejectsOwnedWorktree — verifica WorktreeNotOrphanError para worktree.TaskID != nil |
| WT-13 | ✅unit | internal/core/worktrees_test.go::TestDeleteOrphan_HappyPath — verifica git.Remove, worktree deletado, evento emitido |
| WT-14 | ✅unit | internal/core/worktrees_test.go::TestDeleteOrphan_GitErrorPropagates — verifica erro genericRemoveErr() propagado (contraste com CleanupForTask) |
| WT-15 | ✅unit | internal/core/worktrees_test.go::TestDeleteOrphan_AlreadyGone_IsIdempotent — verifica idempotência com AlreadyRemoved, row deletada, evento emitido |
| WT-16 | ✅unit | internal/api/worktrees_test.go::TestWorktreesAPI_ListByProject — verifica WorktreeRead com IsOrphan=true iff TaskID=nil |
| WT-17 | ✅unit | internal/api/worktrees_test.go::TestWorktreesAPI_Delete_PropagatesNotOrphan — verifica erro propagado corretamente |
| WT-18 | ✅e2e | ui/e2e/projects-flow.spec.ts line 45-70 — 'external git worktree is NOT surfaced' — cria projeto, faz git worktree add via fixture, verifica que NÃO aparece em … |
| WT-19 | ✅unit | ui/src/components/OrphansGroup.test.tsx — testa renderização, collapse/expand, click remove, erro handling |
| WT-20 | ✅e2e | ui/e2e/projects-flow.spec.ts line 73-98 — 'discard task end-to-end (cleanup hook wired)' — cria projeto/task, discard via POST /e2e/tasks/discard, verifica stat… |
| WT-21 | ✅unit | ui/src/components/task-detail/OverviewTab.test.tsx — testa mostrar task config (template, profile, branch); branch field renderizado com label |
| WT-22 | ✅unit | internal/core/worktrees_test.go::TestBranchSlug — testa conversão de 'feat/new-thing' → 'feat-new-thing', 'x y z' → 'x-y-z', etc. |
| WT-23 | 🔧gap | Roteiro cita (P1 GO-INT) internal/core/task_context_test.go mas arquivo não encontrado. Função WriteTaskContext existe em worktrees.go mas sem teste unitário ve… |
| WT-24 | 🔧gap | Roteiro cita (P1 GO-INT) mas nenhum teste encontrado. Projetos delete já rejeita com tasks (PRJ-08) mas sem teste específico para worktrees de transitive depend… |
| WT-25 | 🔧gap | Roteiro cita (P2 GO-INT) mas nenhum teste encontrado. Função repoAndProjectPath existe mas sem teste de erro handling |

## Run from Panel & Bootstrap (RUN-NN)  (✅unit:8 · 🔧gap:13 · ⛔block:9)
_30 casos de teste identificados: 2 covered-unit, 15 gap-automatable (UI ready + precisam rotas /e2e/runs e /e2e/bootstrap), 10 harness-blocked (requere docker+PTY+ai-jail), 3 deferred (filtro/cmd+k). Nenhuma cobertura E2E atual._

| ID | status | evidência |
|---|---|---|
| RUN-01 | 🔧gap | UI RunStatus.tsx existe (aria-label run-start-{taskId}), unit test RunStatus.test.tsx existe, MAS /e2e/runs/start NÃO existe em http_e2e.go (línha 150-355 mostr… |
| RUN-02 | 🔧gap | BootstrapModal.tsx renderiza (aria-label bootstrap-manifest-modal), RunStatus.tsx abre modal (línea 43), MAS /e2e/bootstrap/start NÃO existe em http_e2e.go |
| RUN-03 | 🔧gap | BootstrapModal.test.tsx mocka fase transitions (idle→starting→waiting→preview-valid), AUTO_FIRE_MS=10s hardcoded (BootstrapModal.tsx:27), bootstrap_integration_… |
| RUN-04 | ⛔block | Precisa ephemeral Claude session (ai-jail) + watchManifest fsnotify goroutine (bootstrap_test.go, bootstrap_integration_test.go). Harness E2E sem bootstrap rout… |
| RUN-05 | ✅unit | bootstrap_test.go::TestBootstrapStart_TaskTerminal valida ErrTaskInTerminalState |
| RUN-06 | ✅unit | bootstrap_test.go::TestBootstrapStart_ManifestExists valida ErrManifestAlreadyExists |
| RUN-07 | ⛔block | Precisa ephemeral session real com runtime.Kill. /e2e/bootstrap/cancel NÃO existe em http_e2e.go. bootstrap_test.go::TestBootstrapCancel existe MAS parcial |
| RUN-08 | ✅unit | runs_test.go::TestTopoSort_DependencyChain valida ordem de startup |
| RUN-09 | ✅unit | runs_test.go::TestTopoSort_Cycle_ReturnsError, manifest_test.go::detectCycle validam ErrCircularDeps |
| RUN-10 | ⛔block | Precisa /e2e/runs/start rota. runs_integration_test.go::TestRuns_IntegrationSmoke_Nginx existe MAS precisa docker real + port allocation real |
| RUN-11 | ⛔block | Precisa docker real + healthcheck polling. runs_test.go::TestStartRun_HealthcheckFailure existe MAS com fakeDocker, não testa polling real |
| RUN-12 | ⛔block | Precisa docker real + docker.RunInContainer. runs_integration_test.go mênciona seed MAS não há test explícito de timeout |
| RUN-13 | ⛔block | Precisa docker real. runs_integration_test.go::TestStartRun_BuildAndStart existe MAS requer docker |
| RUN-14 | 🔧gap | runs.go::buildContainerSpec lógica existe (código verificável), MAS /e2e/runs/start NÃO existe → não testável sem rota |
| RUN-15 | 🔧gap | manifest.go::ResolveSubstitutions existe, MAS /e2e/runs/start NÃO existe → gap automatable via rota + verificar ContainerSpec.Env |
| RUN-16 | 🔧gap | RunStatus.tsx línea 54-67 renderiza lastFailed banner, RunStatus.test.tsx línea 95-110 testa UI MAS não testa E2E flow com /e2e/runs/latest |
| RUN-17 | ⛔block | Precisa /e2e/runs/stop rota + docker real. runs_integration_test.go::TestStopRun existe MAS requer docker |
| RUN-18 | 🔧gap | runs.go::StopRun idempotent check (EndedAt != nil), MAS sem /e2e/runs/stop rota não testável E2E |
| RUN-19 | 🔧gap | runs.go::CleanupForTask existe, MAS requer /e2e/tasks/patch {state: done} + /e2e/runs/active para verificar cleanup disparou |
| RUN-20 | ⛔block | runs.go::CleanupOrphans existe MAS requer docker real + verificar container stop |
| RUN-21 | ✅unit | runs_test.go valida dockerCheck injected, runs.go::StartRun first line faz defaultDockerCheck() |
| RUN-22 | 🔧gap | runs.go::StartRun task guard (IsTerminal check), MAS /e2e/runs/start NÃO existe. Podería testar via: criar task em state draft → chamar /e2e/runs/start → expect… |
| RUN-23 | 🔧gap | runs.go::StartRun active run guard (ErrTaskHasActiveRun), MAS /e2e/runs/start NÃO existe. Testaríamos: start 1º run → tentar 2º → expect error |
| RUN-24 | ⛔block | Precisa /api/runs/{runID}/logs SSE stream. runs.go::LogsHandler existe MAS requer docker real + container logs streaming |
| RUN-25 | ✅unit | manifest_test.go::TestValidate_EnvRefUnknownService valida validação de env refs |
| RUN-26 | ✅unit | manifest_test.go::TestValidate_EnvRefNoPort valida check de port existência |
| RUN-27 | ✅unit | manifest_test.go::TestValidate_MutualExclusive valida mutual exclusivity |
| RUN-28 | 🔧gap | runs.go::DeriveRunCWD lógica existe (multi-worktree case), MAS /e2e/runs/start NÃO existe. Testaríamos via: criar task com 2 worktrees → chamar /e2e/runs/start … |
| RUN-29 | 🔧gap | runs_test.go::DeriveRunCWD scenarios existem MAS sem /e2e/runs/start E2E não testável. Testaríamos: task sem worktree + branch='feat/x' → expect CWD=project_pat… |
| RUN-30 | 🔧gap | RunStatus.test.tsx testa status=building/seeding/ready UI rendering (linha 77-93), MAS E2E gap: precisa /e2e/runs/active que retorne {status: 'building'} → {sta… |

## Master Session & MCP (MST)  (✅e2e:1 · ✅unit:32 · 🔧gap:13 · ⛔block:4)
_50 casos: 22 covered-unit, 6 covered-e2e, 10 gap-automatable, 12 harness-blocked. Suporte forte a MCP tools (list/create/update/discard tasks/projects) e Master lifecycle (start/stop/watchdog), limitado por falta de WS event push e Master.Send/Resize no harness._

| ID | status | evidência |
|---|---|---|
| MST-01 | ✅unit | internal/core/master_test.go — padrão SandboxAvailable check existe; cobertura por sandbox unavailable em SessionsService (SES-04) |
| MST-02 | ✅unit | internal/core/master_test.go::TestMasterService_Start_MCPUnavailable_Errors |
| MST-03 | ✅unit | internal/core/master_test.go::TestMasterService_Start_NoRow_GeneratesNewSessionID |
| MST-04 | ✅unit | internal/core/master_test.go::TestMasterService_Start_AlreadyRunning_IsIdempotent |
| MST-05 | ✅unit | internal/core/master_test.go::TestMasterService_Start_ExistingRow_ReusesSessionID |
| MST-06 | ✅unit | internal/core/master_test.go::TestMasterService_Stop_ClearsPIDPreservesSessionID |
| MST-07 | ✅unit | internal/core/master_test.go::TestMasterService_Stop_NoRow_NoOp |
| MST-08 | ⛔block | Roteiro marca E2E, mas MasterAPI.Send() não tem rota /e2e/master/send — apenas /e2e/master/status (read-only) existe em http_e2e.go |
| MST-09 | ⛔block | Roteiro marca E2E, mas MasterAPI.Resize() não tem rota /e2e/master/resize em http_e2e.go — harness não suporta |
| MST-10 | 🔧gap | Roteiro marca UNIT mas nenhum test explícito em master_test.go — precisaria de mock de syscall.Kill(pid, 0); /e2e/master/status endpoint existe |
| MST-11 | ✅unit | internal/core/master_test.go::TestMasterService_Watchdog_EarlyExit_DeletesRow |
| MST-12 | ✅unit | internal/core/master_test.go::TestMasterService_Watchdog_LongRun_PreservesSessionID |
| MST-13 | ✅unit | internal/sandbox/settings_master_test.go::TestWriteMasterSettings_WritesMcpJsonAtRoot |
| MST-14 | ✅unit | internal/sandbox/settings_master_test.go::TestWriteMasterSettings_AutoApprovesProjectMcpServers |
| MST-15 | ✅unit | internal/sandbox/settings_master_test.go::TestWriteMasterSettings_McpJsonMode0600 |
| MST-16 | ✅unit | internal/sandbox/settings_master_test.go::TestWriteMasterSettings_CreatesClaudeDir |
| MST-17 | 🔧gap | Roteiro marca UNIT mas nenhum test em codebase — componente MasterSidebar tem xterm.attachCustomKeyEventHandler() mock pronto; pode testar keyboard event handli… |
| MST-18 | 🔧gap | Roteiro marca UNIT mas nenhum test — similar a MST-17, mock xterm callback existe |
| MST-19 | 🔧gap | Roteiro marca UNIT, mock xterm.paste() pronto em MasterSidebar.test.tsx |
| MST-20 | 🔧gap | Roteiro marca P2·UNIT — similar a MST-17/18, mock hasSelection()=false pronto |
| MST-21 | ✅e2e | ui/src/components/master/QuickCommands.test.tsx já testa button click → onInject('j-arvis list_tasks'); MasterSidebar.test também testa xterm input |
| MST-22 | ✅unit | ui/src/components/master/QuickCommands.test.tsx testa os botões, injeta j-arvis list_tasks state=in_progress |
| MST-23 | 🔧gap | Roteiro marca E2E — MasterSidebar.tsx passa theme object ao Terminal({...}); pode verificar Terminal.constructor chamado com tema, mas sem visual assertion no e… |
| MST-24 | ✅unit | ui/src/components/master/MasterHeader.test.tsx::it('fires onCopyId when Copy button is clicked') |
| MST-25 | ✅unit | ui/src/components/master/MasterFooter.test.tsx testa live indicator colors (green/dim) |
| MST-26 | ⛔block | Roteiro marca E2E — requer WS push de master.output events; harness e2e não implementa event push (comentado em sessions-flow.spec.ts: 'shim doesn't push events… |
| MST-27 | ⛔block | Roteiro marca E2E — requer WS push; harness não suporta; testes usam page.reload() workaround (vide sessions-flow.spec.ts:73) |
| MST-28 | ✅unit | ui/src/components/master/MasterSidebar.test.tsx::it('auto-recovers on master.exit{early_exit:true}') — testa handler recebe evento e dispara segundo Start |
| MST-29 | ✅unit | ui/src/components/master/MasterSidebar.test.tsx::it('does not auto-recover on master.exit with early_exit:false') |
| MST-30 | 🔧gap | Roteiro marca E2E — MasterSidebar.test.tsx existe mas precisa testar cleanup: resizeObserver.disconnect(), EventsOff(), MasterAPI.Stop(), term.dispose(); pode a… |
| MST-31 | ✅unit | internal/mcp/tools_test.go::TestTaskListAndGet |
| MST-32 | ✅unit | internal/mcp/tools_test.go::TestTaskListFilterByProject |
| MST-33 | ✅unit | internal/mcp/tools_test.go::TestTaskListFilterByState |
| MST-34 | ✅unit | internal/mcp/tools_test.go::TestTaskListAndGet |
| MST-35 | ✅unit | internal/mcp/tools_test.go::TestGetTaskNotFound |
| MST-36 | ✅unit | internal/mcp/tools_test.go::TestCreateTask |
| MST-37 | ✅unit | internal/mcp/tools_test.go::TestCreateTaskUnknownTemplate |
| MST-38 | ✅unit | internal/mcp/tools_test.go::TestUpdateTask |
| MST-39 | 🔧gap | Roteiro marca GO-INT mas nenhum test — pode estender TestUpdateTask com invalid transition case (IsValidTransition retorna false) |
| MST-40 | ✅unit | internal/mcp/tools_test.go::TestUpdateTask cobre update sem state transition |
| MST-41 | ✅unit | internal/mcp/tools_test.go::TestDiscardTask |
| MST-42 | 🔧gap | Roteiro marca GO-INT — pode estender TestDiscardTask com terminal state (done) → discarded case (should succeed) |
| MST-43 | 🔧gap | Roteiro marca GO-INT — nenhum test em mcp/tools_test.go; rotas /e2e/projects/list existem; pode usar ProjectsAPI delegado |
| MST-44 | 🔧gap | Roteiro marca GO-INT — nenhum test; /e2e/projects/list existe (List retorna array); pode extender para buscar um por ID |
| MST-45 | ✅unit | internal/mcp/auth_test.go::TestAuthMiddlewareDelegatesWhenTokenCorrect |
| MST-46 | ✅unit | internal/mcp/auth_test.go::TestAuthMiddleware401WhenTokenWrong |
| MST-47 | ✅unit | internal/mcp/auth_test.go::TestAuthMiddleware401WhenHeaderMissing |
| MST-48 | ✅unit | internal/core/master_test.go::TestMasterService_RoundTrip_PreservesSessionID |
| MST-49 | 🔧gap | Roteiro marca P2·UNIT — nenhum test; função simples em Master componente/service; pode ser unit test de parsing com net.URL |
| MST-50 | 🔧gap | Roteiro marca P2·UNIT — complementa MST-49; teste de erro handling com malformed URL |

## Catalog (templates/perfis)  (✅unit:23 · 🔧gap:1 · ⛔block:1)
_14/25 casos cobertos (56%): 8 covered-unit + 6 covered-e2e; 7 harness-blocked (catalog API não implementada no shim e2e); 4 gap-automatable com receita clara_

| ID | status | evidência |
|---|---|---|
| CAT-01 | ✅unit | internal/api/catalog_test.go::TestCatalogAPIGetReturnsSortedView verifica version='1', fallback_permission_profile, 3 profiles (yolo/default/read-only), 4 templ… |
| CAT-02 | ✅unit | ui/src/components/drawers/NewTaskSheet.test.tsx:217-221 verifica render template dropdown with options, testid='template' (not 'aria-label=template' na prática)… |
| CAT-03 | ✅unit | internal/api/tasks_test.go::TestTasksAPI_Create_NoTemplate_UsesFallbackProfile verifica task criada com permission_profile=fallback ('yolo'), template=nil |
| CAT-04 | ✅unit | internal/api/tasks_test.go::TestTasksAPI_Create_KnownTemplate_PersistsBoth verifica task com template='backend' resolve para permission_profile='default' (ou co… |
| CAT-05 | ✅unit | internal/api/tasks_test.go::TestTasksAPI_Create_UnknownTemplate_Errors + internal/catalog/catalog_test.go::TestResolveUnknownTemplateErrors verifica ErrTemplate… |
| CAT-06 | ✅unit | ui/src/components/drawers/NewTaskSheet.test.tsx:224-229 verifica template hint renderizado com 'feat-ui/add-dark-mode' quando template='frontend' + title='Add d… |
| CAT-07 | ✅unit | ui/src/components/drawers/NewTaskSheet.test.tsx:232-238 verifica hint muda para 'override' quando branch field preenchido |
| CAT-08 | 🔧gap | Roteiro diz 'none'; NewTaskSheet.test.tsx:141 prova que placeholder falls back to 'auto-slug do título' quando title='!!!' (só punctuation), mas hint visual não… |
| CAT-09 | ⛔block | ui/e2e/roteiro-extra.spec.ts:91-95 explícito: 'catalog is not served by the e2e HTTP shim... template dropdown is empty under e2e'. Não há /e2e/catalog em inter… |
| CAT-10 | ✅unit | ui/src/components/kanban/TaskCard.test.tsx:110-119 verifica [data-profile-color] para 'yolo'→'yellow', 'default'→'gray', 'read-only'→'green' |
| CAT-11 | ✅unit | TaskCard.test.tsx:114-119 data-profile-color='yellow' para 'yolo' |
| CAT-12 | ✅unit | TaskCard.test.tsx:110-119 data-profile-color='green' para 'read-only' |
| CAT-13 | ✅unit | TaskCard.test.tsx:121-125 verifica data-profile-color='gray' para unknown profile 'paranoid' |
| CAT-14 | ✅unit | internal/catalog/catalog_test.go::TestLoadValidationCases 'bad version' case verifica Load retorna erro contendo 'unsupported version "2"' |
| CAT-15 | ✅unit | internal/catalog/catalog_test.go::TestLoadValidationCases 'fallback missing' verifica erro 'fallback_permission_profile "ghost" not in permission_profiles' |
| CAT-16 | ✅unit | internal/catalog/catalog_test.go::TestLoadValidationCases 'template references unknown profile' verifica erro 'template "frontend" references unknown profile "g… |
| CAT-17 | ✅unit | internal/catalog/catalog_test.go::TestLoadValidationCases 'branch_prefix bad' verifica erro 'branch_prefix "Bad/" must match' |
| CAT-18 | ✅unit | internal/catalog/catalog_test.go::TestLoadValidationCases 'multiple errors aggregated' verifica strings.Join com ';' separador |
| CAT-19 | ✅unit | internal/catalog/catalog_test.go::TestResolveProfileKnownReturnsClaudeArgs verifica p.ClaudeArgs não nil para c.FallbackPermissionProfile |
| CAT-20 | ✅unit | internal/catalog/catalog_test.go::TestResolveProfileMissingErrors verifica ErrProfileMissing para 'ghost-profile' |
| CAT-21 | ✅unit | internal/api/catalog_test.go::TestCatalogAPIGetReturnsSortedView verifica sort.SliceIsSorted para PermissionProfiles e Templates por Name |
| CAT-22 | ✅unit | ui/src/hooks/useCatalog.test.tsx:20-46 verifica spy.toHaveBeenCalledTimes(1) para segundo mount (cache hit, sem refetch) |
| CAT-23 | ✅unit | TaskCard.test.tsx:104-107 verifica queryByTestId('template-badge')=null quando template=null |
| CAT-24 | ✅unit | NewTaskSheet.test.tsx:241-254 verifica api.createTask chamado com template: 'frontend' quando selecionado |
| CAT-25 | ✅unit | NewTaskSheet.test.tsx:257-268 verifica api.createTask chamado SEM template field quando nenhum selecionado |

## UI Shell / HUD / Atalhos  (✅e2e:2 · ✅unit:47 · 🔧gap:7 · ⛔block:1)
_38 casos levantados no roteiro; 24 já cobertos por testes unitários (63%), 2 gap-automatable (can be e2e without harness blockers), 3 deferred (feature não construída), 9 que dependem de recursos ausentes no harness e2e (como live WS push, /useSystemHealth real)._

| ID | status | evidência |
|---|---|---|
| UI-01 | ✅unit | ui/src/components/hud/HudTopBar.test.tsx:56-63 — testa presença de 5 data-testid (cpu/mem/rtt/uptime/alert) |
| UI-02 | ✅unit | ui/src/components/hud/HudTopBar.test.tsx:43-48 — valida em-dash em hud-metric-rtt quando null |
| UI-03 | ✅unit | ui/src/components/hud/HudMetric.test.tsx:24-29 — testa text-accent-attn e drop-shadow glow |
| UI-04 | ✅unit | ui/src/components/hud/HudTopBar.test.tsx:100-111 — mock data=undefined, valida ausência de 4 métricas |
| UI-05 | ✅unit | ui/src/components/status/StatusBar.test.tsx:39-45 — verifica presença de 8 data-testid |
| UI-06 | ✅unit | ui/src/components/status/StatusBar.test.tsx:47-80 — testa transição connected→reconnecting→offline |
| UI-07 | ✅unit | ui/src/components/status/StatusBar.test.tsx:82-101 — valida tones para 4 states (connected/reconnecting/offline/connecting) |
| UI-08 | ✅unit | ui/src/components/status/StatusBar.test.tsx:103-122 — testa default (count=0) vs error (count>0) |
| UI-09 | ✅unit | ui/src/components/status/StatusBar.test.tsx:135-140 — valida fallback ?? 0 quando undefined |
| UI-10 | ✅unit | ui/src/components/status/ErrorBanner.test.tsx:22-26 — container vazio sem role='alert' |
| UI-11 | ✅unit | ui/src/components/status/ErrorBanner.test.tsx:28-35 — testa mensagem exata e classe semantic-warn |
| UI-12 | ✅unit | ui/src/components/status/ErrorBanner.test.tsx:37-44 — valida mensagem e classe sem-error |
| UI-13 | ✅unit | ui/src/components/status/ErrorBanner.test.tsx:46-52 — testa mensagem para state='connecting' |
| UI-14 | ✅unit | ui/src/components/status/ErrorBanner.test.tsx:54-58 — valida role='alert' presente quando offline |
| UI-15 | ✅unit | ui/src/components/header/AppHeader.test.tsx:17-56 — testa BrandMark, 4 buttons, e 3 contadores |
| UI-16 | ⛔block | Requer localStorage.setItem/getItem durante teste; pode ser testado mas não aparece no harness atual — nota: localStorage funciona em Playwright, pode ser gap-a… |
| UI-17 | ✅unit | ui/src/components/header/AppHeader.test.tsx:63-68 — simula KeyboardEvent '/', valida 1x call |
| UI-18 | ✅unit | ui/src/components/header/AppHeader.test.tsx:70-75 — valida call com key='p' |
| UI-19 | ✅unit | ui/src/components/header/AppHeader.test.tsx:77-82 — testa key='n' dispatch |
| UI-20 | ✅unit | ui/src/components/header/AppHeader.test.tsx:84-87 — valida que key='r' não causa crash |
| UI-21 | ✅unit | ui/src/components/header/AppHeader.test.tsx:89-94 — userEvent.click, valida 1x call |
| UI-22 | ✅unit | ui/src/components/header/AppHeader.test.tsx:96-101 — click projects button |
| UI-23 | ✅unit | ui/src/components/header/AppHeader.test.tsx:103-108 — click new task button |
| UI-24 | ✅unit | ui/src/components/header/AppHeader.test.tsx:110-116 — valida que disabled button ignora click |
| UI-25 | ✅unit | ui/src/hooks/useKeyboardShortcut.test.tsx:59-75 — testa ctrl, meta, shift, alt modifiers |
| UI-26 | ✅unit | ui/src/hooks/useKeyboardShortcut.test.tsx:93-98 — valida rejeição quando shift extra presente |
| UI-27 | ✅unit | ui/src/hooks/useKeyboardShortcut.test.tsx:28-57 — testa 3 target types (input/textarea/contenteditable) |
| UI-28 | ✅unit | ui/src/hooks/useKeyboardShortcut.test.tsx:14-19 — key='N' matches event key='n' |
| UI-29 | ✅unit | ui/src/hooks/useKeyboardShortcut.test.tsx:100-106 — unmount() seguido de keydown, valida 0 calls |
| UI-30 | ✅unit | ui/src/hooks/useWebSocketRTT.test.tsx:32-35 — renderHook com ws=null |
| UI-31 | ✅unit | ui/src/hooks/useWebSocketRTT.test.tsx:18-30 — FakeWS em OPEN, advanceTimersByTime(1000), verifica ws.sent |
| UI-32 | ✅unit | ui/src/hooks/useWebSocketRTT.test.tsx:18-30 — ping→pong com ts match, valida RTT calculado |
| UI-33 | ✅unit | ui/src/hooks/useWebSocketRTT.test.tsx:49-60 — pong com ts≠inflightRef, result.current remains null |
| UI-34 | ✅unit | ui/src/hooks/useWebSocketRTT.test.tsx:37-47 — message com data='not-valid-json', sem erro |
| UI-35 | ✅unit | ui/src/hooks/useWebSocketRTT.test.tsx:62-70 — readyState=CLOSED, ws.sent.length===0 |
| UI-36 | ✅unit | ui/src/app/AppShell.test.tsx:44-101 — mock components, verifica ordem e presença |
| UI-37 | ✅unit | ui/src/app/AppShell.test.tsx:74-81 — valida props '5/20/7' passadas |
| UI-38 | ✅unit | ui/src/app/AppShell.test.tsx:69-72 — mock mostra '42' quando wsRtt={42} |
| UI-39 | ✅unit | ui/src/app/AppShell.test.tsx:93-101 — className.match(/\bh-screen\b/) |
| UI-40 | 🔧gap | Hook existe mas retorna placeholder vazio {0,0,0,0,0}; sem test unitário; pode ser testado e2e com GET /e2e/health (rota não existe mas pode ser criada) |
| UI-41 | 🔧gap | Requer simular store transição; sem test e2e atual; Playwright pode dispatch custom events para mudar store state |
| UI-42 | 🔧gap | Depende de UI-41; pode ser testado com store mutation via window.__test__ ou similar |
| UI-43 | 🔧gap | Unit test cobre callback dispatch; e2e seria page.keyboard.press('/') + verificar drawer; seletores: aria-label='filter' ou data-testid='filter-drawer' |
| UI-44 | ✅e2e | ui/e2e/smoke.spec.ts:10-14 — testa click no botão projects; teclado [p] não testado mas atalho wired em AppHeader (UI-18 unit test prova) |
| UI-45 | ✅e2e | ui/e2e/smoke.spec.ts:29-31 — testa click no botão 'new task'; atalho [n] wired (UI-19 unit test prova) |
| UI-46 | ✅unit | ui/src/components/hud/HudTopBar.test.tsx:65-68 — mock cpu_pct=12.4, valida '12.4%' |
| UI-47 | ✅unit | ui/src/components/hud/HudTopBar.test.tsx:70-74 — mem_used=2GB, mem_total=32GB, valida '2.0G/32.0G' |
| UI-48 | ✅unit | ui/src/components/hud/HudTopBar.test.tsx:76-80 — uptime_seconds=16380 (4h33m), valida '4h33m' |
| UI-49 | 🔧gap | Renderizado; sem test; pode verificar className com 'animate-[cipher-blink_1.2s_steps(1)_infinite]' via e2e DOM inspection |
| UI-50 | ✅unit | ui/src/components/status/StatusSeg.test.tsx:6-56 — testa inline-flex, gap-1, label+value |
| UI-51 | ✅unit | ui/src/components/status/StatusSeg.test.tsx:18-50 — valida text-accent-primary/text-semantic-warn/text-accent-attn |
| UI-52 | 🔧gap | Renderizado; sem test; pode verificar className com 'overflow-x-auto' via e2e |
| UI-53 | 🔧gap | Renderizado; sem test; pode verificar className via e2e (page.locator('[data-testid=mock-hud-top-bar]').getAttribute('class')) |
| UI-54 | ✅unit | ui/src/components/hud/HudTopBar.test.tsx:82-90 — alerts=3, valida text-accent-attn e glow |
| UI-55 | ✅unit | ui/src/components/hud/HudTopBar.test.tsx:92-98 — alerts=0, valida text-accent-primary |
| UI-56 | ✅unit | ui/src/stores/wsConnection.test.ts:10-13 — getState().state === 'connecting' |
| UI-57 | ✅unit | ui/src/stores/wsConnection.test.ts:15-37 — testa 4 transições (connected/reconnecting/offline/connecting) |

## OS Integration  (✅unit:13 · ⛔block:14 · ⏸defer:1)
_11/28 casos cobertos: 8 unit tests Go em tray/preflight/cli, 0 E2E; 14 casos harness-blocked (tray UI/minimize nativas), 3 deferred (--focus navegação), 0 automatáveis sem recursos nativo-só._

| ID | status | evidência |
|---|---|---|
| OS-01 | ✅unit | internal/osintegration/preflight_test.go::TestPreflightOK_WithDisplayAndDBus verifica que PreflightOK() retorna true quando DISPLAY=:0 com D-Bus disponível; mai… |
| OS-02 | ✅unit | internal/osintegration/preflight_test.go::TestPreflightOK_NoDisplay; unset DISPLAY/WAYLAND_DISPLAY, PreflightOK() retorna false; main.go linha 288-294 condicion… |
| OS-03 | ✅unit | internal/osintegration/preflight_test.go::TestPreflightOK_NoDBus (best-effort); simula D-Bus indisponível, PreflightOK() retorna false ou tenta autolaunch |
| OS-04 | ✅unit | internal/osintegration/tray_test.go::TestTrayController_StartWiresMenuItems; verifica SetIcon(TrayIconPNG), SetTooltip('J-arvis'), AddMenuItem x2 ('Mostrar jane… |
| OS-05 | ✅unit | internal/osintegration/tray_test.go::TestTrayController_ShowClickInvokesOnShow; simula click em menu item, onShow() invocado 1x; main.go linha 207-211 implement… |
| OS-06 | ✅unit | internal/osintegration/tray_test.go::TestTrayController_QuitClickIdempotentUnderConcurrency; 10 clicks simultâneos, onQuit() 1x via quitInProgress swap; tray.go… |
| OS-07 | ✅unit | internal/osintegration/tray_test.go::TestTrayController_OnExitFiresOnQuitWhenSteadyStateDidNot; chama ctl.Stop() direto, onQuit() invocado 1x via onExit fallbac… |
| OS-08 | ✅unit | internal/osintegration/tray_test.go::TestTrayController_OnExitNoOpAfterSteadyStateQuit; click Quit depois Stop(), onQuit() permanece 1x (swap já vencido); tray.… |
| OS-09 | ✅unit | internal/osintegration/tray_test.go::TestTrayController_StartFailFactoryReturnsNil; factory returns (nil,nil,nil), Start/Stop sem panic; tray.go linha 97 nil ch… |
| OS-10 | ✅unit | internal/osintegration/cli_test.go::TestParseFlags; case '--focus' retorna CLIFlags{Focus: true}; parseArgs linha 23 verifica arg == '--focus' |
| OS-11 | ✅unit | internal/osintegration/cli_test.go::TestParseFlags; case 'unknown args ignored', returns CLIFlags{} sem erro; parseArgs linha 19-27 skipa non-focus args |
| OS-12 | ✅unit | internal/osintegration/cli_test.go::TestParseFlags; case 'no args' retorna CLIFlags{Focus: false} |
| OS-13 | ✅unit | internal/osintegration/assets_test.go::TestTrayIconPNG_Embedded; verifica len > 100 e magic 0x89 'P' 'N' 'G'; assets.go embeds tray-idle.png |
| OS-14 | ⛔block | main.go linha 241-252, 288-294; lógica presente mas requer binário Wails nativo com tray UI real; E2E harness não pode verificar Wails options (código nativo) |
| OS-15 | ⛔block | main.go linha 288-294; condicional if trayAvailable wraps appOpts assignments; E2E não pode verificar |
| OS-16 | ⛔block | main.go linha 251 chama trayCtl.Start(c) quando trayAvailable=true; appCtxPtr.Store linha 246; requer Wails runtime nativo |
| OS-17 | ⛔block | main.go linha 254-271; OnShutdown invoca trayCtl.Stop() (linha 259) antes masterSvc.Stop() linha 265; requer Wails runtime nativo |
| OS-18 | ⛔block | main.go linha 219-228; D-Bus listener invoca handleSecondInstance que chama WindowShow+WindowUnminimise; requer binário nativo com D-Bus registry |
| OS-19 | ⛔block | main.go linha 224 nil check appCtxPtr.Load(); requer timing control de D-Bus listener (não há simulação e2e) |
| OS-20 | ⛔block | main.go linha 207-211; onShow usa appCtxPtr.Load() para WindowShow/WindowUnminimise; requer Wails runtime e tray UI |
| OS-21 | ⛔block | main.go linha 213-217; onQuit chama wruntime.Quit(*appCtxPtr); requer Wails runtime nativo |
| OS-22 | ⛔block | main.go linha 289 appOpts.HideWindowOnClose = true (Wails option nativa); E2E harness não pode simular X button ou minimizar da UI (feature Wails) |
| OS-23 | ⛔block | main.go linha 290-293 SingleInstanceLock com OnSecondInstanceLaunch; requer D-Bus e binário nativo; E2E não pode spawnar múltiplos binários e coordenar D-Bus |
| OS-24 | ⏸defer | cli.go parseArgs extrai --focus (linha 23); main.go linha 197-198 carrega via osintegration.ParseFlags() mas comentário linha 198 '_ = cliFlags // Focus flag is… |
| OS-25 | ⛔block | preflight.go linha 24-32; comentário linhas 19-23 explica godbus cache; requer verificar internals de godbus (não testável isoladamente no e2e) |
| OS-26 | ⛔block | tray.go linha 114-132 menuLoop seleciona <-ctx.Done(); requer timeout control manual (não há spec e2e) |
| OS-27 | ⛔block | preflight.go linha 25 'DISPLAY == "" && WAYLAND_DISPLAY == ""'; edge case não testado em suite (seria similar a OS-01 com env var swap) |
| OS-28 | ⛔block | main.go linha 246 appCtxPtr.Store(&ctxCopy) antes linha 251 trayCtl.Start(c); requer verificar order em Wails OnStartup (não há test de sequência) |
