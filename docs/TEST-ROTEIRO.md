# Roteiro de Testes — J-arvis (features atuais)

> Gerado a partir de análise do código (9 domínios). **331 casos** · P0=116 P1=166 P2=49 · E2E=76 GO-INT=96 UNIT=154 MANUAL=5 · 176 validam código recém-mudado (F10.8 hardening).

**Legenda método:** `E2E`=automatizável no harness Playwright (vite-preview + jarvis-e2e-http) · `GO-INT`/`UNIT`=melhor em teste Go · `MANUAL`=só no binário Wails nativo (tray/single-instance/notificação).


## Projetos & Repos: CRUD, Detecção (mono/multi), Rescan, Validação de Caminho

_Sistema de gerenciamento de projetos com suporte a mono/multi-repo, detecção automática via DetectRepos (análise de .git na raiz e 1 nível abaixo), operações CRUD (create/list/delete), rescan incremental, validação de caminho único, e integração com tasks (delete bloqueado se project tem tasks)._


### PRJ-01 — Criar projeto monorepo com sucesso (caminho válido com .git na raiz)
`P0` · `E2E` · 🔧recém-mudado
- **Pré:** Git fixture com .git na raiz do diretório preparado via initGitFixture()
- **Passos:**
  1. Abrir drawer de Projects via botão no header
  2. Preencher nome (ex: mono-${Date.now()})
  3. Preencher caminho com path da fixture monorepo
  4. Clicar 'Adicionar projeto'
  5. Aguardar visibilidade do project-node com o nome inserido (5s timeout)
- **Esperado:** Project aparece no drawer com label 'monorepo' (1 repositório); projeto criado com Repositories[0].SubPath === '.'
- **Cobertura atual:** ui/e2e/projects-flow.spec.ts: 'create monorepo: project has one repository'

### PRJ-02 — Criar projeto multi-repo com sucesso (raiz + 2+ subdiretórios com .git)
`P0` · `E2E` · 🔧recém-mudado
- **Pré:** Git fixture com raiz vazia (sem .git) + subdiretórios alpha, beta com .git via initGitFixture({subDirs: ['alpha', 'beta']})
- **Passos:**
  1. Abrir drawer Projects
  2. Preencher nome (ex: multi-${Date.now()})
  3. Preencher caminho com fixture multi-repo
  4. Clicar 'Adicionar projeto'
  5. Aguardar visibilidade do project-node (5s timeout)
  6. Expandir project-node para visualizar repos listadas
- **Esperado:** Project aparece com label '2 sub-repos' (ou N conforme count); repositórios criados em ordem alfabética (alpha, beta); cada repo tem SubPath correto
- **Cobertura atual:** ui/e2e/projects-flow.spec.ts: 'create multi-repo: project lists N repositories'

### PRJ-04 — Rejeitar criação: caminho sem .git (nenhum nível) retorna erro 422
`P0` · `E2E` · 🔧recém-mudado
- **Pré:** Diretório vazio sem .git criado via t.TempDir()
- **Passos:**
  1. Abrir drawer Projects
  2. Preencher nome (ex: reject-${Date.now()})
  3. Preencher caminho com diretório sem .git (ex: /tmp/nonexistent-${Date.now()})
  4. Clicar 'Adicionar projeto'
  5. Aguardar 3s para confirmar que projeto NÃO aparece no drawer
- **Esperado:** Project-node NÃO criado; erro exibido no formulário contendo 'no .git directory at path or one level below'
- **Cobertura atual:** ui/e2e/projects-flow.spec.ts: 'create project at no-git path is rejected'

### PRJ-06 — Listar projetos (List API) retorna array com todas as instâncias
`P0` · `E2E` · 🔧recém-mudado
- **Pré:** 2+ projetos já persistidos no banco (via Create calls anteriores)
- **Passos:**
  1. Abrir drawer Projects (dispara useQuery com enabled=open)
  2. Aguardar carregamento da lista (refetch automático)
  3. Verificar quantos project-nodes renderizam no drawer
- **Esperado:** Todos os projetos aparecem no drawer em ordem de criação (created_at ASC); cada um exibe nome, count de repos, count de tasks ativas; repositories[] hidratado para cada projeto
- **Cobertura atual:** none (List é usado implicitamente por ProjectsDrawer, sem test E2E dedicado)

### PRJ-07 — Excluir projeto com sucesso (sem tasks associadas)
`P0` · `E2E` · 🔧recém-mudado
- **Pré:** Projeto criado; verificado que não tem tasks (count=0)
- **Passos:**
  1. Abrir drawer Projects
  2. Localizar project-node do projeto target
  3. Clicar botão 'Excluir' do project-node
  4. Aguardar reconciliação (refetch projects query via onSuccess de useMutation)
  5. Verificar que project-node desapareceu do drawer (3s timeout)
- **Esperado:** Project deletado do DB; event 'project.deleted' emitido; project-node removido da UI; queryClient invalidate projetos
- **Cobertura atual:** internal/core/projects_test.go: 'TestProjectsService_Delete_OK_EmitsEvent'

### PRJ-08 — Rejeitar exclusão: projeto com tasks bloqueado com erro 409
`P0` · `E2E` · 🔧recém-mudado
- **Pré:** Projeto criado + 1+ task já associada (em qualquer estado: idea/in_progress/done/discarded)
- **Passos:**
  1. Abrir drawer Projects
  2. Localizar project-node com tasks ativas (label mostra 'N tasks ativas')
  3. Clicar 'Excluir'
  4. Aguardar resposta de erro
- **Esperado:** Delete falha com erro 'project has tasks; discard them before deleting' (count variável); toast exibido no drawer; projeto permanece no DB e UI
- **Cobertura atual:** internal/core/projects_test.go: 'TestProjectsService_Delete_RejectsWithTasks'

### PRJ-03 — Criar projeto layout híbrido (raiz com .git + subdiretórios com .git)
`P1` · `E2E` · 🔧recém-mudado
- **Pré:** Git fixture com raiz + .git E subdiretórios backend, frontend + .git cada (simula gcb-hub)
- **Passos:**
  1. Abrir drawer Projects
  2. Preencher nome (ex: hybrid-${Date.now()})
  3. Preencher caminho com fixture hybrid (raiz com .git + subs)
  4. Clicar 'Adicionar projeto'
  5. Aguardar visibilidade projeto (5s timeout)
  6. Expandir para listar repos
- **Esperado:** 3 repositórios criados: root repo (SubPath='.') com nome = project.name, + backend (SubPath='backend'), + frontend (SubPath='frontend'); label '3 sub-repos'
- **Cobertura atual:** none

### PRJ-05 — Rejeitar criação: caminho duplicado (UNIQUE constraint path) retorna erro 409
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** Primeiro projeto já criado com path=/home/test/repo1; preparar segunda tentativa com mesmo path
- **Passos:**
  1. Criar e persistir primeiro projeto com CreateProject(name='proj1', path='/home/test/repo1')
  2. Abrir drawer Projects
  3. Preencher nome (ex: proj2-${Date.now()})
  4. Preencher caminho com MESMO path da primeira (/home/test/repo1)
  5. Clicar 'Adicionar projeto'
  6. Aguardar erro no formulário
- **Esperado:** Erro exibido contendo 'path already used' ou 'UNIQUE constraint'; projeto não criado; primeira instância mantém-se inalterada
- **Cobertura atual:** internal/core/projects_test.go: not explicitly tested (path-unique constraint comentado mas não há test case)

### PRJ-09 — Rescan (DetectRepos hybrid): adiciona novos repos quando disco muda
`P1` · `E2E` · 🔧recém-mudado
- **Pré:** Projeto criado com apenas raiz.git; depois manualmente adicionar backend/.git e frontend/.git no disco (without touching DB)
- **Passos:**
  1. Criar projeto com fixture contendo só raiz/.git
  2. Adicionar subdiretórios backend/.git e frontend/.git ao disco
  3. Abrir drawer Projects
  4. Localizar project-node e clicar botão 'Rescan' (↻ icon)
  5. Aguardar conclusão (refetch projects via onSuccess)
  6. Expandir project-node para visualizar repos
- **Esperado:** Repositories[] agora contém 3 repos (root + backend + frontend); event 'project.updated' emitido uma vez; no duplicatas; DB atualizado para refletir novo disco state
- **Cobertura atual:** internal/core/projects_test.go: 'TestProjectsService_RescanRepositories_AddsNewRepos'

### PRJ-10 — Rescan (idempotent): sem eventos/inserts quando DB já em sync
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** Projeto criado com 2 repos em disco e DB; disco não mudou
- **Passos:**
  1. Abrir drawer Projects
  2. Clicar botão 'Rescan' no project-node
  3. Aguardar conclusão
- **Esperado:** Repositories[] permanece inalterado; nenhum evento 'project.updated' emitido; nenhuma inserção no DB (Rescan é no-op); refetch projects não altera renderização
- **Cobertura atual:** internal/core/projects_test.go: 'TestProjectsService_RescanRepositories_NoChanges'

### PRJ-14 — Contagem de repos no header reflete estado correto (monorepo vs N sub-repos)
`P1` · `E2E` · 🔧recém-mudado
- **Pré:** Múltiplos projetos listados (mono + multi)
- **Passos:**
  1. Abrir drawer Projects
  2. Verificar label para cada project-node
  3. Expandir um project-node mono vs multi
- **Esperado:** Projeto mono exibe 'monorepo' (1 repo); projeto multi exibe 'N sub-repos' (count > 1); label formatado via repoCountLabel computed; sempre sincronizado com project.repositories.length
- **Cobertura atual:** ui/e2e/projects-flow.spec.ts (implícito em renders de project-node)

### PRJ-15 — Contagem de tasks ativas no header (in_progress + review com worktrees)
`P1` · `E2E` · 🔧recém-mudado
- **Pré:** Projeto com múltiplas tasks em estados variados (idea, in_progress, review, done); worktrees associadas aos ativos
- **Passos:**
  1. Abrir drawer Projects
  2. Localizar project-node com múltiplas tasks
  3. Verificar label 'N tasks ativas'
  4. Mudar estado de uma task para terminal (done/discarded)
  5. Aguardar refetch e verificar atualização do label
- **Esperado:** Label mostra apenas tasks com state in (in_progress, review) QUE TÊM worktrees; count atualizado em tempo real via useQuery; task sem worktree não contabilizada
- **Cobertura atual:** none (TaskWorktreeGroup renderização, label compute não testado E2E)

### PRJ-17 — Validar que create mutation atualiza projects queryKey corretamente
`P1` · `E2E` · 🔧recém-mudado
- **Pré:** Drawer Projects com lista inicial vazia ou com N projetos
- **Passos:**
  1. Preencher e submeter formulário com novo projeto
  2. Verificar que useMutation.onSuccess chama invalidateQueries(queryKeys.projects)
  3. Aguardar refetch automático
  4. Verificar que novo projeto aparece na lista
- **Esperado:** Novo projeto refetch automático via React Query; lista atualiza sem page reload; form limpa (name, path resetados); nenhuma duplicata no drawer
- **Cobertura atual:** none (React Query mechanics, não testado)

### PRJ-18 — API delegação: ProjectsAPI passa requests para core.ProjectsService
`P1` · `UNIT` · 🔧recém-mudado
- **Pré:** ProjectsAPI instanciado com fakeProjectsService
- **Passos:**
  1. Chamar api.Create(CreateProjectInput)
  2. Verificar que svc.Create foi delegado com mesmos args
  3. Chamar api.List()
  4. Chamar api.Delete(id)
  5. Chamar api.RescanRepositories(id)
- **Esperado:** Todas as chamadas delegadas corretamente; erros propagados (ErrNoGitRepos, ErrProjectNotFound, ProjectHasTasksError); nenhuma transformação ou swallow de erro
- **Cobertura atual:** internal/api/projects_test.go

### PRJ-19 — DetectRepos: filtra submodules (ignora .git gitlink files)
`P1` · `GO-INT`
- **Pré:** Fixture com root/.git + subdir/.git (regular dir) + submodule/.git (file, gitlink)
- **Passos:**
  1. Criar projeto com DetectRepos(fixture_path)
  2. Inspecionar specs retornados
- **Esperado:** 2 repos retornados (root + subdir); submodule ignorado; specs ordenados alfabéticamente; nenhum erro
- **Cobertura atual:** internal/git/detect_test.go (presumido, verificar)

### PRJ-21 — Erro de criação exibido no formulário com styling de erro (alert role)
`P1` · `E2E` · 🔧recém-mudado
- **Pré:** Create mutation falha (ex: path duplicado, DetectRepos fail)
- **Passos:**
  1. Submeter formulário com dados que causem erro
  2. Aguardar resposta negativa
  3. Verificar que erro aparece abaixo do botão em paragráfo com role='alert'
- **Esperado:** submitError state preenchido com (err as Error).message; renderizado em <p role='alert' class='sem-error'>; texto em mono/monospace para legibilidade; pode ser clicado para desaparecer ou limpo ao resubmeter
- **Cobertura atual:** none

### PRJ-22 — Toast de erro global (onError callback) exibido quando delete ou rescan falha
`P1` · `E2E` · 🔧recém-mudado
- **Pré:** Project-node renderizado; delete ou rescan mutation setup para falhar
- **Passos:**
  1. Clicar 'Excluir' ou 'Rescan' em um projeto
  2. Forçar erro na mutation (ex: mock API para retornar erro)
  3. Verificar toast aparece no drawer com mensagem de erro traduzida
- **Esperado:** onError callback dispara setToast(msg); toast renderiza com role='alert'; mensagem pré-traduzida via translateError; pode ser clicado para fechar
- **Cobertura atual:** none

### PRJ-24 — E2E API /e2e/projects/create com CreateProjectInput delegado corretamente
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** E2EServer montado com /e2e/projects/create endpoint
- **Passos:**
  1. POST /e2e/projects/create com {name, path}
  2. Verificar resposta JSON com project object
- **Esperado:** HTTP 200 + project JSON com id, name, path, created_at, repositories[]; se erro, HTTP 500 + {error: msg}
- **Cobertura atual:** internal/api/http_e2e.go (endpoint; não há unit test)

### PRJ-25 — E2E API /e2e/projects/delete removes project, returns 204
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** E2EServer; projeto já criado
- **Passos:**
  1. POST /e2e/projects/delete com {id}
  2. Verificar resposta
- **Esperado:** HTTP 204 No Content; projeto removido do DB; subsequent List não inclui deletado
- **Cobertura atual:** internal/api/http_e2e.go (endpoint; não há unit test)

### PRJ-26 — Caminho inválido (não é diretório) rejeita com ErrNoGitRepos
`P1` · `UNIT` · 🔧recém-mudado
- **Pré:** Path aponta para arquivo (regular file) ou não-existent path sem permissão
- **Passos:**
  1. Chamar CreateProject com path=/etc/passwd ou /tmp/nonexistent-12345
  2. Aguardar erro retornado
- **Esperado:** DetectRepos retorna ErrNoGitRepos wrapped com 'is not a directory'; Create falha e não persiste; API propagates erro
- **Cobertura atual:** internal/core/projects_test.go (implícito em test de no git repos)

### PRJ-11 — Validar campos obrigatórios do formulário (name + path required)
`P2` · `E2E`
- **Pré:** Drawer Projects aberto, formulário vazio
- **Passos:**
  1. Tentar clicar 'Adicionar projeto' sem preencher nome
  2. Verificar que form não submete (required HTML validation)
  3. Preencher nome, tentar clicar sem preencher path
  4. Verificar bloqueio na validação HTML
- **Esperado:** Form elements com required=true bloqueiam submit; nenhuma chamada API realizada; browser mostra validação nativa ou CSS :invalid
- **Cobertura atual:** none (validação HTML nativa, não testada em spec)

### PRJ-12 — Botão Browse (Pasta) abre file picker nativo e popula path
`P2` · `MANUAL`
- **Pré:** Drawer Projects aberto, formulário visível
- **Passos:**
  1. Clicar botão 'Pasta' (FolderOpen icon)
  2. Invocar ChooseDirectory (Wails native dialog; E2E simula via fixture ou skip se test harness headless)
  3. Selecionar diretório no picker
  4. Verificar que field #cp-path é populado com path selecionado
- **Esperado:** Campo path preenchido com caminho absoluto retornado pelo picker; nenhum erro no browseError; resto do form permanece válido para submit
- **Cobertura atual:** none (requires native dialog interaction, impraticável no Playwright headless)

### PRJ-13 — Erro de Browse (dialog falha) exibido como alerta no formulário
`P2` · `UNIT`
- **Pré:** Drawer Projects aberto; ChooseDirectory preparado para falhar (permissões, etc.)
- **Passos:**
  1. Clicar botão 'Pasta'
  2. Simular erro no onBrowse (throw ou reject da Promise)
  3. Verificar que browseError state atualiza
- **Esperado:** Alerta visível no form com mensagem de erro; path field permanece em edição; form não bloqueia (usuário pode tentar de novo ou digitar manual)
- **Cobertura atual:** none

### PRJ-16 — Collapse/expand project-node persiste estado no localStorage
`P2` · `E2E`
- **Pré:** Project-node renderizado; localStorage vazio para key jarvis.proj.${id}.collapsed
- **Passos:**
  1. Abrir drawer Projects
  2. Clicar toggle (▼/▶) para collapse project-node
  3. Fechar e reabrir drawer
  4. Verificar que project-node permanece collapsed
- **Esperado:** useLocalStorage guarda collapsed state; reload drawer recupera estado anterior; toggle inverte estado corretamente
- **Cobertura atual:** none

### PRJ-20 — Marcar disable no form enquanto create mutation está pendente
`P2` · `E2E`
- **Pré:** Form visível, mutation pronta para ser disparada
- **Passos:**
  1. Preencher formulário e submeter
  2. Antes de receber resposta, tentar clicar botão novamente ou modificar fields
  3. Aguardar resposta (sucesso ou erro)
- **Esperado:** Fieldset com disabled={create.isPending} impede edição durante request; botão mostra Loader2 spinner; opacity:60%; após resposta, fieldset reenabilitado; form aceita input novamente
- **Cobertura atual:** none

### PRJ-23 — Rescan mutation loading state: button mostra '↻ ...' enquanto pendente
`P2` · `E2E` · 🔧recém-mudado
- **Pré:** Project-node com botão rescan visível
- **Passos:**
  1. Clicar botão rescan
  2. Verificar texto do botão durante request
  3. Aguardar conclusão
- **Esperado:** Button renderiza '↻ ...' quando rescan.isPending=true; disabled={true} durante request; após conclusão, volta a '↻'; permite novo rescan
- **Cobertura atual:** none

## Tasks & Kanban

_Cria e gerencia tasks em 5 colunas (Backlog/In Progress/Review/Done/Discarded) com máquina de estados, drag-drop, templates com permissões, discard e filtros._


### TSK-02 — Criar task com projeto obrigatório e template opcional — happy path
`P0` · `E2E` · 🔧recém-mudado
- **Pré:** Projeto 'test-proj-TSK02' existe e está selecionado; nenhuma task com título 'création-test' existe
- **Passos:**
  1. Abrir formulário NewTaskSheet
  2. Selecionar projeto 'test-proj-TSK02' (pré-populado)
  3. Preencher Título: 'création-test'
  4. Deixar Descrição vazia
  5. Selecionar Template: '(nenhum)'
  6. Clicar 'Criar'
  7. Aguardar resposta; observar task aparece no Kanban
- **Esperado:** Task criada com state='idea', PermissionProfile resolvido para fallback do catalog, em coluna Backlog; resposta HTTP 200 com JSON da task
- **Cobertura atual:** ui/e2e/kanban-flow.spec.ts (createTask helper)

### TSK-05 — Transição válida idea→ready funciona
`P0` · `E2E` · 🔧recém-mudado
- **Pré:** Task em estado 'idea' criada via /e2e/tasks/create
- **Passos:**
  1. POST /e2e/tasks/patch { id: task.id, patch: { state: 'ready' } }
  2. Verificar response.state
- **Esperado:** response.state === 'ready'; task listada em Backlog (coluna que bucketiza 'idea' e 'ready')
- **Cobertura atual:** ui/e2e/kanban-flow.spec.ts (idea→ready test)

### TSK-06 — Transição válida ready→in_progress funciona
`P0` · `E2E` · 🔧recém-mudado
- **Pré:** Task em estado 'ready'
- **Passos:**
  1. Usar drag-drop UI ou POST /e2e/tasks/patch { state: 'in_progress' }
  2. Aguardar coluna 'In Progress' apareça (reload se necessário em e2e)
- **Esperado:** Task move para coluna 'In Progress'; state='in_progress'
- **Cobertura atual:** ui/e2e/kanban-flow.spec.ts (task state can be patched directly)

### TSK-10 — Drag-drop task entre colunas valida transição antes de permitir
`P0` · `E2E` · 🔧recém-mudado
- **Pré:** Task em Backlog (state='ready'); coluna 'In Progress' visível
- **Passos:**
  1. Selecionar task card
  2. Drag para coluna 'In Progress'
  3. onDragEnd dispara handleDragEnd → isValidTransition check
  4. Drop
- **Esperado:** Se transição ready→in_progress válida: patch enviado, task move; se inválida: erro banner 'Transição não permitida'
- **Cobertura atual:** none

### TSK-12 — Discard task (estado → 'discarded') move para coluna Discarded
`P0` · `E2E` · 🔧recém-mudado
- **Pré:** Task em qualquer estado ativo (ex: 'ready')
- **Passos:**
  1. POST /e2e/tasks/discard { id: task.id }
  2. Verificar response HTTP 204
  3. GET /e2e/tasks/get { id } para confirmar state='discarded'
- **Esperado:** HTTP 204 sem corpo; task.state='discarded' após GET; task visível em coluna Discarded
- **Cobertura atual:** ui/e2e/kanban-flow.spec.ts (task discard moves it out)

### TSK-26 — Bucketize distribui tasks em 5 colunas corretamente (idea/ready→Backlog; in_progress→In Progress; review→Review; done→Done; discarded→Discarded)
`P0` · `UNIT`
- **Pré:** 5 tasks com estados: idea, ready, in_progress, review, done, discarded
- **Passos:**
  1. Chamar bucketize([...]) função Kanban.tsx
  2. Verificar distribuição por coluna
- **Esperado:** idea+ready em Backlog; in_progress em In Progress; review em Review; done em Done; discarded em Discarded
- **Cobertura atual:** none

### TSK-01 — Criar task sem projeto falha com erro obrigatório
`P1` · `E2E`
- **Pré:** Nenhuma task existe; UI está no formulário NewTaskSheet
- **Passos:**
  1. Abrir NewTaskSheet (clique 'new task')
  2. Deixar select de Projeto vazio ou sem seleção (força project_id='')
  3. Preencher Título: 'test task'
  4. Clicar botão Criar
- **Esperado:** Botão Criar permanece desabilitado (canSubmit=false em NewTaskSheet); formulário não envia
- **Cobertura atual:** none

### TSK-03 — Criar task com template 'backend' resolve permissão do catalog
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** Projeto existe; catalog tem template 'backend' com DefaultPermissionProfile='default'
- **Passos:**
  1. POST /e2e/tasks/create com: { project_id, title: 'back-task', template: 'backend' }
  2. Verificar response.permission_profile via GET /e2e/tasks/get
- **Esperado:** response.permission_profile === 'default' (ou conforme catalog.backend); template field preservado como 'backend'
- **Cobertura atual:** internal/api/tasks_test.go::TestTasksAPI_Create_KnownTemplate_PersistsBoth

### TSK-04 — Criar task com template desconhecido retorna catalog.ErrTemplateUnknown
`P1` · `GO-INT`
- **Pré:** Nenhum template 'ghost-template' existe
- **Passos:**
  1. POST /e2e/tasks/create com: { project_id: 'p', title: 'x', template: 'ghost-template' }
- **Esperado:** HTTP 500 com error message contendo 'template' ou resposta struct { error: '...' }
- **Cobertura atual:** internal/api/tasks_test.go::TestTasksAPI_Create_UnknownTemplate_Errors

### TSK-07 — Transição inválida idea→done rejeitada com ErrInvalidTransition
`P1` · `GO-INT`
- **Pré:** Task em estado 'idea' (logo após create)
- **Passos:**
  1. POST /e2e/tasks/patch { id: task.id, patch: { state: 'done' } }
- **Esperado:** HTTP 500 com error contendo 'invalid state transition' ou 'ErrInvalidTransition'
- **Cobertura atual:** internal/api/tasks_test.go::TestTasksAPI_Patch_InvalidTransition

### TSK-08 — Transição inválida in_progress→done (sem passar por review) rejeitada
`P1` · `GO-INT`
- **Pré:** Task em estado 'in_progress'
- **Passos:**
  1. Tentar PATCH com state='done'
- **Esperado:** Erro: transição não permitida (máquina: in_progress→review→done obrigatória)
- **Cobertura atual:** internal/core/task_test.go (validTransitions map)

### TSK-11 — Drag-drop com alvo inválido (ex: idea→done) mostra erro no banner
`P1` · `E2E`
- **Pré:** Task em Backlog (idea); usuário tenta arrastar para Done
- **Passos:**
  1. Drag task da coluna Backlog para coluna Done
  2. isValidTransition(idea, done) retorna false
  3. setError('Transição não permitida.')
- **Esperado:** Alert banner fixo no topo com mensagem de erro; usuário clica para descartar
- **Cobertura atual:** none

### TSK-13 — Discard de task inexistente retorna ErrTaskNotFound
`P1` · `GO-INT`
- **Pré:** Task ID 'nonexistent-123' não existe
- **Passos:**
  1. POST /e2e/tasks/discard { id: 'nonexistent-123' }
- **Esperado:** HTTP 500 com error 'task not found'
- **Cobertura atual:** internal/store/tasks.go (Discard checks RowsAffected)

### TSK-14 — Estado terminal (done/discarded) dispara cleanup em ordem: bootstrap → session → runs → worktrees
`P1` · `UNIT` · 🔧recém-mudado
- **Pré:** Task em estado 'review'; cleanup handlers registrados
- **Passos:**
  1. PATCH task para state='done' (transição válida review→done)
  2. Verificar ordem de chamadas aos cleanup functions
- **Esperado:** Cleanup chamado nesta ordem: bootstrap cleanup, session cleanup, runs cleanup, worktree cleanup
- **Cobertura atual:** internal/core/tasks_test.go::TestTransition_TerminalRunsAllCleanupsInOrder_BootstrapFirst

### TSK-15 — Discard também dispara cleanup (bootstrap → session → runs → worktrees)
`P1` · `UNIT` · 🔧recém-mudado
- **Pré:** Task em estado 'idea'
- **Passos:**
  1. POST /e2e/tasks/discard { id }
  2. Verificar funções cleanup foram chamadas
- **Esperado:** Discard chama todos 4 cleanups na ordem esperada, mesmo que erro em um não bloqueia os outros
- **Cobertura atual:** internal/api/tasks_test.go::TestTasksAPI_Discard_CallsBothCleanups e cleanup order tests

### TSK-19 — Patch que muda title mas não state emite 'task.updated'
`P1` · `UNIT` · 🔧recém-mudado
- **Pré:** Task com title='old title', state='idea'
- **Passos:**
  1. PATCH { id, patch: { title: 'new title' } } (sem state)
  2. Verificar event bus
- **Esperado:** task.updated emitido com novo title; state não muda
- **Cobertura atual:** internal/api/tasks_test.go (non-state field updates)

### TSK-20 — List tasks filtra por project_ids obrigatório
`P1` · `GO-INT`
- **Pré:** 3 tasks: 2 em proj-A, 1 em proj-B
- **Passos:**
  1. POST /e2e/tasks/list { project_ids: ['proj-A'] }
- **Esperado:** Resposta contém 2 tasks (ambas de proj-A); nenhuma de proj-B
- **Cobertura atual:** internal/api/tasks_test.go::TestTasksAPI_List_FilterByProject

### TSK-24 — NewTaskInline quick-add por coluna cria task com state mapeado correto
`P1` · `E2E` · 🔧recém-mudado
- **Pré:** Kanban renderizado com DefaultProjectId em coluna 'In Progress'
- **Passos:**
  1. Clicar '+ add task' em coluna 'In Progress'
  2. Digitar título 'quick-task'
  3. Enviar form
- **Esperado:** Task criada com project_id=defaultProjectId, title='quick-task', state='in_progress' (conforme COLUMN_STATES)
- **Cobertura atual:** none

### TSK-31 — Transição discarded→idea (restore) é válida
`P1` · `GO-INT`
- **Pré:** Task em estado 'discarded'
- **Passos:**
  1. PATCH { state: 'idea' }
- **Esperado:** Task volta para Backlog com state='idea'; transição permitida pela máquina de estados
- **Cobertura atual:** none

### TSK-32 — Transição review→in_progress (voltar) é válida
`P1` · `GO-INT`
- **Pré:** Task em estado 'review'
- **Passos:**
  1. PATCH { state: 'in_progress' }
- **Esperado:** Transição permitida; task move para coluna 'In Progress'
- **Cobertura atual:** none

### TSK-34 — Get task inexistente retorna 404 ErrTaskNotFound
`P1` · `GO-INT`
- **Pré:** Task ID 'ghost-123' não existe
- **Passos:**
  1. POST /e2e/tasks/get { id: 'ghost-123' }
- **Esperado:** HTTP 404 com error 'task not found'
- **Cobertura atual:** internal/api/http_e2e.go (writeErr 404)

### TSK-35 — Patch task inexistente retorna erro ErrTaskNotFound
`P1` · `GO-INT`
- **Pré:** Task ID 'ghost-123' não existe
- **Passos:**
  1. POST /e2e/tasks/patch { id: 'ghost-123', patch: { state: 'ready' } }
- **Esperado:** HTTP 500 com error contendo 'task not found'
- **Cobertura atual:** internal/store/tasks.go (repo.Get checks ErrTaskNotFound)

### TSK-38 — State transition matrix reject→discard de todo estado não-terminal exceto 'done'
`P1` · `GO-INT`
- **Pré:** Tasks em idea, ready, in_progress, review, done
- **Passos:**
  1. Para cada estado, tentar PATCH { state: 'discarded' }
  2. Verificar cada transição
- **Esperado:** idea→discarded ✓, ready→discarded ✓, in_progress→discarded ✓, review→discarded ✓, done→discarded ✓ (done é terminal mas pode descartar)
- **Cobertura atual:** internal/core/task.go (validTransitions map)

### TSK-09 — Patch para mesmo estado (idea→idea) não emite evento
`P2` · `UNIT`
- **Pré:** Task com state='idea'
- **Passos:**
  1. POST /e2e/tasks/patch { id, patch: { state: 'idea' } }
  2. Verificar event bus (interno em teste Go)
- **Esperado:** Resposta 200, task.state='idea', mas sem event 'task.updated' emitido (só atualiza se houve mudança real)
- **Cobertura atual:** internal/api/tasks_test.go::TestTasksAPI_Patch_SameState_NoEmit

### TSK-16 — Erro em cleanup não propaga para caller (cleanup swallowed)
`P2` · `UNIT` · 🔧recém-mudado
- **Pré:** Task terminal; cleanup function retorna erro
- **Passos:**
  1. PATCH para state='done' com cleanup que falha
  2. Verificar Discard ou Patch retorna sucesso (sem erro propagado)
- **Esperado:** Patch/Discard retorna sucesso; cleanup error logado (log.Printf) mas não retorna erro ao caller
- **Cobertura atual:** internal/api/tasks_test.go::TestTasksAPI_Cleanup_ErrorDoesNotPropagate

### TSK-17 — Patch com nil cleanup function não causa panic
`P2` · `UNIT`
- **Pré:** TasksService init com cleanup=nil; task em estado 'review'
- **Passos:**
  1. PATCH para state='done' (terminal, dispara cleanup check)
  2. Função cleanup é nil
- **Esperado:** Nenhum panic; Patch completa normalmente com sucesso
- **Cobertura atual:** internal/api/tasks_test.go::TestTasksAPI_NilCleanup_DoesNotPanic

### TSK-18 — Patch de campos não-estado (title/description/branch) sem mudança de state não emite update se nenhum field muda
`P2` · `UNIT` · 🔧recém-mudado
- **Pré:** Task existente com title='original', description='desc'
- **Passos:**
  1. PATCH { id, patch: { title: 'original', description: 'desc' } } (mesmo valores)
  2. Verificar event bus
- **Esperado:** Nenhum evento emitido (ou apenas 1 de atualização de fields); sem novo 'task.updated'
- **Cobertura atual:** internal/api/tasks_test.go (Patch logic)

### TSK-21 — Badge de template exibe cor semantica correta (backend=var(--semantic-backend))
`P2` · `E2E`
- **Pré:** Task com template='backend' renderizada no TaskCard
- **Passos:**
  1. Inspecionar elemento com [data-template-name='backend']
  2. Verificar span interno com backgroundColor
- **Esperado:** Dot (span.inline-block h-2 w-2) tem backgroundColor=var(--semantic-backend); cor aplicada conforme TEMPLATE_COLORS
- **Cobertura atual:** none

### TSK-22 — Badge de perfil de permissão exibe nome (ex: 'yolo', 'read-only')
`P2` · `E2E` · 🔧recém-mudado
- **Pré:** Task com permission_profile='yolo' ou 'read-only'
- **Passos:**
  1. Renderizar TaskCard; verificar [data-permission-profile] visível
  2. Verificar atributo [data-profile-color]
- **Esperado:** Badge mostra nome do perfil (ex: 'yolo'); data-profile-color match (yellow/green); title tooltip exibe descrição do perfil
- **Cobertura atual:** none

### TSK-23 — Tempo relativo no card (relativeTime) formata 'agora', '5m', '2h', '3d', '1mo'
`P2` · `UNIT`
- **Pré:** Task com updated_at em timestamp conhecido; horário atual fixo em testes
- **Passos:**
  1. Renderizar TaskCard; verificar elemento com title={task.updated_at} e conteúdo formatado
  2. Chamar formatRelativeTime(iso) diretamente com nowMs variável
- **Esperado:** formatRelativeTime('2026-06-01T21:00:00Z', 21:00) → 'agora'; ('21:00' - 5min) → '5m'; válido até 30 dias → 'Nmo'
- **Cobertura atual:** ui/src/lib/relativeTime.ts (test via jest ou similar)

### TSK-25 — NewTaskInline form cancela com Escape sem criar task
`P2` · `E2E`
- **Pré:** Form expandido ('+ add task' clicado)
- **Passos:**
  1. Digitar em input
  2. Pressionar 'Escape'
  3. Observar form estado
- **Esperado:** Form colapse (expanded=false); input clearado; nenhuma task criada
- **Cobertura atual:** none

### TSK-27 — Kanban com task.state desconhecido (não mapeado) cai na coluna Discarded (fallback)
`P2` · `UNIT`
- **Pré:** Task com state='unknown-state' (edge case, não deve ocorrer em produção)
- **Passos:**
  1. Chamar stateToColumn('unknown-state')
  2. Observar resposta
- **Esperado:** Retorna 'Discarded' (fallback no return statement da função)
- **Cobertura atual:** none

### TSK-28 — Kanban loading state mostra 4 skeleton cards por coluna
`P2` · `E2E`
- **Pré:** tasks.isLoading === true
- **Passos:**
  1. Renderizar Kanban com useQuery ainda pending
  2. Observar DOM
- **Esperado:** 5 colunas, cada uma com 4 TaskCardSkeleton (SKELETON_COUNT=4); data-testid='kanban-loading'
- **Cobertura atual:** none

### TSK-29 — Kanban empty state mostra mensagem quando tasks.data.length === 0
`P2` · `E2E`
- **Pré:** Nenhuma task existe no projeto selecionado
- **Passos:**
  1. Abrir Kanban
  2. tasks.data === []
- **Esperado:** Centro da tela: ASCII art + 'Create a task to get started — press [N] or click + new task'; data-testid='kanban-empty-state'
- **Cobertura atual:** none

### TSK-30 — Task com id.slice(0,4) mostra short ID no card (ex: 'abc1...' → '#abc1')
`P2` · `E2E`
- **Pré:** Task com id='abc123def456-xxx'
- **Passos:**
  1. Renderizar TaskCard
  2. Verificar elemento span.font-mono com '#'
- **Esperado:** Exibe '#abc1' (após remover '-' e pegar 4 primeiros chars)
- **Cobertura atual:** none

### TSK-33 — Transição ready→idea (voltar para idea) é válida
`P2` · `GO-INT`
- **Pré:** Task em estado 'ready'
- **Passos:**
  1. PATCH { state: 'idea' }
- **Esperado:** Transição permitida; task permanece em Backlog (ambas mapeiam para Backlog visualmente)
- **Cobertura atual:** none

### TSK-36 — Patch com apenas branch field (sem state, title, description) atualiza branch
`P2` · `GO-INT` · 🔧recém-mudado
- **Pré:** Task com branch=nil
- **Passos:**
  1. PATCH { id, patch: { branch: 'feature/TSK-36' } }
  2. GET para verificar
- **Esperado:** response.branch === 'feature/TSK-36'; state e title não mudaram
- **Cobertura atual:** internal/store/tasks.go (UpdateFields dynamic SQL)

### TSK-37 — Patch com branch=null no JSON limpa o branch (set to null via pointer)
`P2` · `GO-INT` · 🔧recém-mudado
- **Pré:** Task com branch='old-branch'
- **Passos:**
  1. PATCH { id, patch: { branch: null } } (JSON null)
  2. Observar como API trata: branch pointer é nil → UpdateFields recebe nil
- **Esperado:** Problema potencial: Go pointer null não limpa campo; espera-se branch='' ou mantém old-branch conforme implementation
- **Cobertura atual:** none (edge case)

### TSK-39 — Sub-tag badge ('idea', 'ready') exibe em Backlog tasks
`P2` · `E2E`
- **Pré:** Task com state='idea' em Backlog
- **Passos:**
  1. Renderizar TaskCard
  2. Verificar badge com subTag
- **Esperado:** Badge exibe 'idea' (ou 'ready'); hidden para outros estados (line 63 TaskCard: state==='idea' || state==='ready')
- **Cobertura atual:** none

### TSK-40 — Create task com description preenchida persiste description
`P2` · `E2E`
- **Pré:** Formulário NewTaskSheet aberto
- **Passos:**
  1. Preencher Título: 'task-with-desc', Descrição: 'This is a long description with details'
  2. Criar task
  3. GET /e2e/tasks/get
- **Esperado:** response.description === 'This is a long description with details'
- **Cobertura atual:** none

## Sessions & Sandbox & Hooks: AI-Jail Session Lifecycle + Hook-Driven Status Transitions + WebSocket Broadcasting

_Sessions domain: spawn Claude sessions in ai-jail sandbox via SessionsService.Start() on a Task, manage semantic status via HTTP hooks (Notification/PreToolUse/Stop) registered with token-based authentication, persist state to DB, broadcast WS events (session.started/stopped/status_changed/tool_use), cleanup on task terminal state or manual stop. Hooks handle status transitions (executing→awaiting_response→idle→done/error), BumpLastHookAt tracking, and event emission to UI via event bus._


### SES-01 — Start session on valid task in idea state → spawns ai-jail, writes settings, creates DB row
`P0` · `GO-INT` · 🔧recém-mudado
- **Pré:** Task exists in DB with state='idea', sandbox available (ai-jail in PATH), temp worktree created
- **Passos:**
  1. Create project and task via API (state='idea')
  2. Call SessionsService.Start(ctx, taskID)
  3. Verify spawned process (runtime.Spawn called with correct cwd + Terminal)
  4. Check DB: session row inserted with status='executing', PID set, HookToken generated
  5. Verify sandbox files written: .claude/settings.json + .ai-jail in cwd
  6. Verify event emitted: bus.Emit('session.started', row)
- **Esperado:** Returns Session{ID, TaskID, Status='executing', PID, Cwd, HookToken, StartedAt}, no error; process spawned in background; settings files exist
- **Cobertura atual:** internal/core/sessions_test.go has test stubs (TestSessionsService_Stop_AlreadyEndedIsNoop, CleanupForTask)

### SES-02 — Start rejects task in terminal state (done/discarded) → returns ErrTaskInTerminalState
`P0` · `UNIT`
- **Pré:** Task exists in DB with state='done' or 'discarded'
- **Passos:**
  1. Create task with state='done'
  2. Call SessionsService.Start(ctx, taskID)
  3. Verify error chain
- **Esperado:** Returns nil, ErrTaskInTerminalState (wrapped); no session row created, no process spawned
- **Cobertura atual:** internal/core/sessions_test.go: TestSessionsService_Start_RejectsWhenSandboxUnavailable (pattern exists, different condition)

### SES-03 — Start rejects when task already has active session → returns ErrTaskAlreadyHasActiveSession
`P0` · `UNIT`
- **Pré:** Task has active session (ended_at IS NULL)
- **Passos:**
  1. Create task, start first session
  2. Attempt to start second session on same task
  3. Verify error
- **Esperado:** Returns nil, ErrTaskAlreadyHasActiveSession; second session not created
- **Cobertura atual:** none

### SES-04 — Start rejects when sandbox unavailable (no ai-jail, no terminal env) → returns ErrSandboxUnavailable
`P0` · `GO-INT`
- **Pré:** PATH emptied or ai-jail binary missing; JARVIS_TERMINAL unset
- **Passos:**
  1. Clear PATH or remove ai-jail
  2. Call SessionsService.Start(ctx, taskID)
  3. Verify error
- **Esperado:** Returns nil, ErrSandboxUnavailable (wraps underlying SandboxAvailable/DetectTerminal error)
- **Cobertura atual:** internal/core/sessions_test.go: TestSessionsService_Start_RejectsWhenSandboxUnavailable

### SES-05 — Hook Notification transitions status executing→awaiting_response, emits session.status_changed
`P0` · `GO-INT` · 🔧recém-mudado
- **Pré:** Session exists with status='executing'; valid hook token registered
- **Passos:**
  1. Create session with executing status
  2. POST /api/hooks/Notification/{token} with {"message": "..."}
  3. Handler calls UpdateStatus(sid, 'awaiting_response')
  4. Verify DB row updated, event emitted if status changed
- **Esperado:** HTTP 204 NoContent; DB shows status='awaiting_response'; bus emits session.status_changed{id, previous='executing', current='awaiting_response'}
- **Cobertura atual:** internal/hooks/server_test.go: TestHandler_Notification_HappyPath

### SES-07 — Hook PreToolUse bumps last_hook_at, emits session.tool_use, returns {"continue": true}
`P0` · `GO-INT` · 🔧recém-mudado
- **Pré:** Session exists, valid token, tool_name in payload
- **Passos:**
  1. POST /api/hooks/PreToolUse/{token} with {"tool_name": "Read"}
  2. Handler calls BumpLastHookAt(sid), emits session.tool_use with tool name
- **Esperado:** HTTP 200; body {"continue": true}; DB last_hook_at updated to ~now; bus emits session.tool_use{id, tool='Read'}
- **Cobertura atual:** internal/hooks/server_test.go: TestHandler_PreToolUse_Returns200WithContinueTrue

### SES-09 — Hook Stop transitions status to idle, emits session.status_changed (not session.stopped)
`P0` · `GO-INT` · 🔧recém-mudado
- **Pré:** Session exists with status='executing' or other non-idle; token valid
- **Passos:**
  1. POST /api/hooks/Stop/{token}
  2. Handler calls UpdateStatus(sid, 'idle'), emits status_changed
  3. Note: session.stopped event is NOT emitted by hook (reserved for manual SessionsService.Stop)
- **Esperado:** HTTP 204; DB status='idle'; bus emits session.status_changed; no session.stopped event
- **Cobertura atual:** internal/hooks/server_test.go: TestHandler_Stop_StatusChangedOnlyIfPrevDifferent

### SES-12 — Stop session: kill subprocess, revoke token, remove config files, mark ended, emit session.stopped
`P0` · `GO-INT` · 🔧recém-mudado
- **Pré:** Active session with PID set
- **Passos:**
  1. Call SessionsService.Stop(ctx, sessionID)
  2. Verify runtime.Kill called with correct PID
  3. Verify registry.Revoke called
  4. Verify sandbox.RemoveSettings, RemoveAijailConfig called
  5. Verify DB: MarkEnded called with final_status, ended_at set
- **Esperado:** Returns nil; process terminated; config cleaned; DB updated; bus emits session.stopped{id, task_id, final_status='done'}
- **Cobertura atual:** internal/core/sessions_test.go: TestSessionsService_Stop_NotFound, Stop_AlreadyEndedIsNoop (partial)

### SES-18 — CleanupForTask stops all active sessions for taskID, tolerant of per-session errors
`P0` · `GO-INT` · 🔧recém-mudado
- **Pré:** Task with multiple active sessions; one Kill will fail
- **Passos:**
  1. Create task with 3 active sessions
  2. Mock second session's Kill to error
  3. Call CleanupForTask(ctx, taskID)
  4. Verify all Stop calls attempted despite second one failing
- **Esperado:** Returns nil (no error propagated); all 3 sessions ended; errors logged but not returned
- **Cobertura atual:** internal/core/sessions_test.go: TestSessionsService_CleanupForTask_NoActiveSessions (happy path only)

### SES-29 — Worktree auto-create: if no worktrees exist for task, CreateForTask invoked via taskBranchOrSlug
`P0` · `GO-INT`
- **Pré:** Task has no worktrees, branch field set or nil
- **Passos:**
  1. Create task with branch='feat/x'
  2. Start session (no pre-existing worktrees)
  3. Verify wtSvc.CreateForTask called with branch='feat/x'
  4. Verify session cwd points to created worktree path
- **Esperado:** Worktree created on-demand; session cwd set to worktree[0].Path
- **Cobertura atual:** none (auto-create path untested)

### SES-43 — E2E: Start session on task → observe spawned subprocess, websocket broadcast of session.started
`P0` · `E2E` · 🔧recém-mudado
- **Pré:** App running, task created, browser connected to WS
- **Passos:**
  1. Navigate to task detail
  2. Click 'Start Session' button
  3. Verify POST /api/sessions/start called
  4. Observe WS event: {type: 'session.started', session_id, task_id, at}
  5. Verify session chip/card appears in UI with status='executing'
- **Esperado:** Process spawned (ps aux shows ai-jail); WS event received; UI reflects new session
- **Cobertura atual:** ui/e2e/sessions-flow.spec.ts (stub only, 1 line)

### SES-44 — E2E: Simulate hook Notification via loopback → observe status transition in UI
`P0` · `E2E` · 🔧recém-mudado
- **Pré:** Session active, client can POST to hook endpoint
- **Passos:**
  1. Start session
  2. POST /api/hooks/Notification/{token} locally (simulating claude)
  3. Observe WS: session.status_changed{previous: 'executing', current: 'awaiting_response'}
  4. Verify UI updates session chip to awaiting_response
- **Esperado:** Status transitions in DB and UI via WS event
- **Cobertura atual:** none (hook simulation tested via http_e2e.go; e2e spec stub)

### SES-45 — E2E: Stop session → subprocess killed, WS session.stopped event, UI removes session
`P0` · `E2E` · 🔧recém-mudado
- **Pré:** Active session with running process
- **Passos:**
  1. Click Stop on session card
  2. Verify POST /api/sessions/stop called
  3. Verify process killed (ps aux no longer shows PID)
  4. Observe WS: session.stopped{session_id, task_id}
  5. Verify UI removes or marks session as ended
- **Esperado:** Process gone, event emitted, UI updated
- **Cobertura atual:** none

### SES-46 — Integration: Start → Notification hook → Stop flow, full lifecycle in single test
`P0` · `GO-INT` · 🔧recém-mudado
- **Pré:** All components wired, DB ready
- **Passos:**
  1. Create task
  2. Start session, verify executing
  3. Simulate Notification hook, verify awaiting_response
  4. Simulate Stop hook, verify idle
  5. Manual Stop via API, verify done/error + config cleaned
- **Esperado:** Full state machine traversal: executing→awaiting_response→idle→done; no residual processes or tokens
- **Cobertura atual:** none (end-to-end integration test missing)

### SES-47 — Regression: task deletion triggers CleanupForTask → all active sessions stopped
`P0` · `GO-INT` · 🔧recém-mudado
- **Pré:** Task with 2 active sessions
- **Passos:**
  1. Transition task to terminal state (done/discarded) via TasksService.UpdateState
  2. Verify TasksService cleanup cascade calls SessionsService.CleanupForTask
  3. Verify all sessions ended, tokens revoked, config removed
- **Esperado:** Sessions automatically cleaned on task terminal transition
- **Cobertura atual:** none (cleanup cascade untested end-to-end)

### SES-06 — Hook Notification with invalid payload (missing 'message') → returns 422
`P1` · `GO-INT`
- **Pré:** Hook token valid, session exists
- **Passos:**
  1. POST /api/hooks/Notification/{token} with empty or malformed JSON
  2. Handler calls ParseNotification, gets ErrInvalidHookPayload
- **Esperado:** HTTP 422 Unprocessable Entity; no status update, no event emitted
- **Cobertura atual:** internal/hooks/server_test.go (pattern in PreToolUse test; Notification not explicitly tested)

### SES-08 — Hook PreToolUse with missing tool_name → returns 422
`P1` · `GO-INT`
- **Pré:** Session exists, token valid
- **Passos:**
  1. POST /api/hooks/PreToolUse/{token} with {} (no tool_name)
  2. Handler calls ParsePreToolUse, gets ErrInvalidHookPayload
- **Esperado:** HTTP 422; no BumpLastHookAt call, no event emitted
- **Cobertura atual:** internal/hooks/server_test.go: TestHandler_PreToolUse_MissingToolNameReturns422

### SES-10 — Hook with unknown token → returns 404
`P1` · `GO-INT`
- **Pré:** Token not registered in TokenRegistry
- **Passos:**
  1. POST /api/hooks/Notification/badtoken with valid payload
  2. Handler resolveToken returns false
- **Esperado:** HTTP 404 Not Found; no DB mutation, no event
- **Cobertura atual:** internal/hooks/server_test.go: TestHandler_Notification_UnknownTokenReturns404

### SES-11 — Hook status unchanged (e.g. prev=awaiting_response, new=awaiting_response) → no event emitted
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** Session status already matches incoming hook status
- **Passos:**
  1. Create session with status='awaiting_response'
  2. POST /api/hooks/Notification/{token} with {"message": "..."}
  3. UpdateStatus returns prev='awaiting_response', next='awaiting_response'
- **Esperado:** HTTP 204; DB status unchanged; bus does NOT emit session.status_changed (guard: if prev != next)
- **Cobertura atual:** internal/hooks/server_test.go: TestHandler_Notification_NoEmitIfStatusUnchanged

### SES-13 — Stop session when kill fails → sets final_status='error' but still cleans up and clears token
`P1` · `UNIT` · 🔧recém-mudado
- **Pré:** Session with PID, runtime.Kill returns error
- **Passos:**
  1. Mock runtime.Kill to return error
  2. Call Stop(ctx, sessionID)
  3. Verify error from Kill is caught, not propagated
- **Esperado:** No error returned; finalStatus='error'; token revoked; config files removed; DB marked ended with error status
- **Cobertura atual:** none (error path untested)

### SES-14 — Stop idempotent: session already ended (ended_at != nil) → no-op, returns nil
`P1` · `UNIT`
- **Pré:** Session with ended_at already set
- **Passos:**
  1. Mark session ended
  2. Call Stop(ctx, sessionID) a second time
  3. Verify no further cleanup, no double Kill
- **Esperado:** Returns nil (early exit); no Kill, revoke, or cleanup called again
- **Cobertura atual:** internal/core/sessions_test.go: TestSessionsService_Stop_AlreadyEndedIsNoop

### SES-15 — Stop session not found in DB → returns ErrSessionNotFound
`P1` · `UNIT`
- **Pré:** sessionID does not exist
- **Passos:**
  1. Call Stop(ctx, invalidSessionID)
- **Esperado:** Returns ErrSessionNotFound; no cleanup attempted
- **Cobertura atual:** internal/core/sessions_test.go: TestSessionsService_Stop_NotFound

### SES-16 — ListByTask returns all sessions (active and ended) for taskID, ordered by started_at ASC
`P1` · `UNIT`
- **Pré:** Task with multiple sessions (some active, some ended)
- **Passos:**
  1. Insert 3 sessions for taskID: (id=a, status=executing, ended_at=nil), (id=b, status=done, ended_at=<time>), (id=c, status=executing, ended_at=nil)
  2. Call ListByTask(ctx, taskID)
  3. Verify order
- **Esperado:** Returns [a, b, c] in started_at order, includes ended sessions, 3 total
- **Cobertura atual:** internal/store/sessions_test.go: TestSessionsRepo_ListByTask_IncludesEnded

### SES-17 — ListActiveByTask returns only sessions where ended_at IS NULL
`P1` · `UNIT`
- **Pré:** Task with mix of active and ended sessions
- **Passos:**
  1. Create sessions as per SES-16
  2. Call ListActiveByTask(ctx, taskID)
- **Esperado:** Returns [a, c]; excludes session b (ended_at set)
- **Cobertura atual:** internal/store/sessions_test.go: TestSessionsRepo_ListActiveByTask

### SES-19 — GetTranscript reads JSONL files from .claude/projects/{encoded-cwd}, parses and aggregates messages
`P1` · `GO-INT`
- **Pré:** Session exists, transcript files in .claude/projects/{encoded-cwd}
- **Passos:**
  1. Create session pointing to worktree cwd
  2. Write mock JSONL transcript: {"role": "user", "content": "hi"}
  3. Call GetTranscript(ctx, sessionID)
  4. Verify FindTranscriptFiles + ParseTranscript calls
- **Esperado:** Returns []TranscriptMessage with Role/Content parsed; empty array if files not found (not error)
- **Cobertura atual:** internal/core/sessions_test.go: TestSessionsService_GetTranscript_NoFiles

### SES-20 — UpdateStatus in repo: returns previous status, updates row, atomic via transaction
`P1` · `UNIT`
- **Pré:** Session exists with status='executing'
- **Passos:**
  1. Call UpdateStatus(ctx, sessionID, 'idle')
  2. Verify returned previous='executing'
  3. Verify DB row updated to 'idle'
- **Esperado:** Returns 'executing', nil; isolation via transaction (no dirty reads)
- **Cobertura atual:** internal/store/sessions_test.go: TestSessionsRepo_UpdateStatus_ReturnsPrev

### SES-21 — BumpLastHookAt updates last_hook_at to current time, idempotent on missing session
`P1` · `UNIT`
- **Pré:** Session exists
- **Passos:**
  1. Call BumpLastHookAt(ctx, sessionID, now)
  2. Verify DB last_hook_at updated
  3. Call on non-existent session, verify ErrSessionNotFound
- **Esperado:** Updates DB on valid session, nil error; returns ErrSessionNotFound on invalid sessionID
- **Cobertura atual:** internal/store/sessions_test.go: TestSessionsRepo_BumpLastHookAt

### SES-23 — Token registry Generate/Resolve: generates unique token, stores mapping sessionID→token, Resolve retrieves
`P1` · `UNIT`
- **Pré:** Registry initialized
- **Passos:**
  1. Call Generate('sid-1'), get tok1
  2. Call Generate('sid-2'), get tok2 (different from tok1)
  3. Call Resolve(tok1), verify returns 'sid-1'
  4. Call Resolve(invalid), verify returns empty string
- **Esperado:** Tokens unique, mapping bidirectional, Resolve returns empty on unknown token
- **Cobertura atual:** internal/hooks/tokens_test.go likely covers; verify via grep

### SES-24 — Token registry Revoke removes token mapping, subsequent Resolve returns empty
`P1` · `UNIT` · 🔧recém-mudado
- **Pré:** Token registered
- **Passos:**
  1. Generate and Resolve token (confirms registered)
  2. Call Revoke(token)
  3. Call Resolve(token) again
- **Esperado:** Before revoke: Resolve returns sessionID; after revoke: Resolve returns empty string
- **Cobertura atual:** none (Revoke logic untested?)

### SES-25 — Write settings: .claude/settings.json created with hookBaseURL + token, readable by ai-jail
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** cwd exists, writable
- **Passos:**
  1. Call sandbox.WriteSettings(cwd, 'http://127.0.0.1:55555', 'tok-123')
  2. Read .claude/settings.json
  3. Verify JSON structure has hook_base_url + hook_token fields
- **Esperado:** File created with correct fields; ai-jail can read and use it
- **Cobertura atual:** internal/sandbox/settings_test.go (if exists)

### SES-26 — Write aijail config: .ai-jail created with resolved permission profile claude_args
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** Profile resolved from catalog, cwd writable
- **Passos:**
  1. Call sandbox.WriteAijailConfig(cwd, profile.ClaudeArgs, nil)
  2. Read .ai-jail YAML
  3. Verify claude_args field contains expected tool allowlist
- **Esperado:** File created; structure matches ai-jail expectations
- **Cobertura atual:** internal/sandbox/aijail_config_test.go

### SES-27 — Remove settings/aijail: files deleted after session cleanup, idempotent
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** Files exist
- **Passos:**
  1. Call RemoveSettings(cwd)
  2. Verify .claude/settings.json deleted
  3. Call RemoveSettings again (files gone)
- **Esperado:** First call deletes files; second call succeeds without error (idempotent via os.RemoveAll or similar)
- **Cobertura atual:** none

### SES-28 — Permission profile resolution: task profile_name overrides catalog fallback
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** Task has profile_name='restricted' set, catalog loaded
- **Passos:**
  1. Create task with permission_profile='restricted'
  2. Start session, verify profile resolved to 'restricted' not fallback
  3. Create task without profile_name, verify fallback used
- **Esperado:** Profile correctly resolved; aijail config written with appropriate claude_args
- **Cobertura atual:** none (profile logic verified in Start method, no dedicated test)

### SES-30 — Worktree fallback branch: if task branch not set, use 'task-{taskID}' for worktree creation
`P1` · `UNIT`
- **Pré:** Task has no branch (nil or empty)
- **Passos:**
  1. Create task without branch
  2. Start session, auto-create worktree
  3. Verify CreateForTask called with 'task-{taskID}'
- **Esperado:** Worktree created with generated branch name
- **Cobertura atual:** internal/core/sessions_test.go: TestTaskBranchOrSlug

### SES-32 — Parse Notification: valid {"message": "...", ...} → returns 'awaiting_response' status
`P1` · `UNIT`
- **Pré:** Payload with 'message' key
- **Passos:**
  1. Call ParseNotification({"message": "user waiting"})
  2. Verify returns 'awaiting_response', nil
- **Esperado:** Status constant returned; extra fields in payload ignored
- **Cobertura atual:** internal/hooks/parser_test.go (if exists)

### SES-33 — Parse Notification missing 'message' → returns ErrInvalidHookPayload
`P1` · `UNIT`
- **Pré:** Payload without 'message'
- **Passos:**
  1. Call ParseNotification({})
  2. Verify error
- **Esperado:** Returns '', ErrInvalidHookPayload
- **Cobertura atual:** none (explicit error case untested)

### SES-34 — Parse Stop: any payload → returns 'idle' status
`P1` · `UNIT`
- **Pré:** Any payload (ignored)
- **Passos:**
  1. Call ParseStop({}) and ParseStop({"extra": "field"})
  2. Verify both return 'idle', nil
- **Esperado:** Status constant returned regardless of payload
- **Cobertura atual:** internal/hooks/server_test.go (implicit in Stop test)

### SES-35 — Parse PreToolUse: valid {"tool_name": "Read"} → returns 'Read', nil
`P1` · `UNIT`
- **Pré:** Payload with tool_name string
- **Passos:**
  1. Call ParsePreToolUse({"tool_name": "Bash"})
  2. Verify returns 'Bash', nil
- **Esperado:** Tool name extracted and returned
- **Cobertura atual:** none (explicit test for happy path missing)

### SES-36 — Parse PreToolUse missing/non-string tool_name → returns ErrInvalidHookPayload
`P1` · `UNIT`
- **Pré:** Payload with tool_name missing or non-string
- **Passos:**
  1. Call ParsePreToolUse({})
  2. Call ParsePreToolUse({"tool_name": 123})
  3. Verify both return '', ErrInvalidHookPayload
- **Esperado:** Error in both cases
- **Cobertura atual:** none

### SES-39 — Database session insert validates constraints: status must be one of valid enum values
`P1` · `GO-INT`
- **Pré:** Session row with invalid status value
- **Passos:**
  1. Attempt to Insert row with status='invalid_status'
  2. Verify DB constraint error
- **Esperado:** INSERT fails with CHECK constraint violation; valid values: executing, awaiting_response, idle, error, done
- **Cobertura atual:** none (constraint validation not explicitly tested)

### SES-40 — Database session uniqueness: hook_token is UNIQUE WHERE NOT NULL (NULL allowed for ended sessions without token)
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** Two sessions with same non-NULL hook_token
- **Passos:**
  1. Insert session-a with hook_token='tok-1'
  2. Attempt insert session-b with hook_token='tok-1'
  3. Verify UNIQUE constraint violation
- **Esperado:** Second insert fails; constraint enforced by DB
- **Cobertura atual:** none

### SES-41 — Wails binding: SessionsAPI.Start callable from UI via Wails RPC
`P1` · `E2E` · 🔧recém-mudado
- **Pré:** Wails runtime context active, SessionsAPI bound in main.go
- **Passos:**
  1. Call window.go.api.SessionsAPI.Start(taskID) from React
  2. Verify RPC marshals Session struct correctly
- **Esperado:** UI receives Session{id, task_id, status, pid, cwd, started_at, ended_at}
- **Cobertura atual:** none (Wails RPC not e2e tested in current spec.ts)

### SES-49 — Catalog permission profile hardening: profile not found → Start fails gracefully
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** Task has permission_profile='nonexistent'
- **Passos:**
  1. Create task with invalid profile_name
  2. Call Start(ctx, taskID)
  3. Verify ResolveProfile error handling
- **Esperado:** Returns error wrapped with context; token revoked before returning; no session row inserted
- **Cobertura atual:** none (profile error path untested)

### SES-22 — SessionsHookAdapter bridges repo to hooks.SessionUpdater interface (background task pattern)
`P2` · `UNIT`
- **Pré:** Adapter constructed from repo
- **Passos:**
  1. Call adapter.UpdateStatus(sid, 'idle')
  2. Call adapter.BumpLastHookAt(sid)
  3. Verify calls proxied to repo methods with background context
- **Esperado:** All calls succeed; adapter satisfies hooks.SessionUpdater interface
- **Cobertura atual:** internal/store/sessions_test.go: TestSessionsRepo_HookAdapter_PassThrough

### SES-31 — Multi-repo worktree handling: session cwd = parent directory of all worktrees
`P2` · `GO-INT`
- **Pré:** Task has >1 worktree (multi-repo)
- **Passos:**
  1. Create task with multiple worktrees sharing parent
  2. Start session
  3. Verify cwd = filepath.Dir(worktrees[0].Path)
- **Esperado:** cwd is parent dir, not individual worktree; claude session cwd in workspace root
- **Cobertura atual:** none (multi-repo cwd logic untested)

### SES-37 — API SessionsAPI.Start wraps core with Context.Background()
`P2` · `UNIT`
- **Pré:** SessionsAPI initialized with core service
- **Passos:**
  1. Call api.Start(taskID)
  2. Verify core.Start called with context.Background()
- **Esperado:** Returns same Session row; errors propagated
- **Cobertura atual:** internal/api/sessions_test.go: TestSessionsAPI_Start

### SES-38 — API SessionsAPI.Stop wraps core with Context.Background()
`P2` · `UNIT`
- **Pré:** SessionsAPI initialized
- **Passos:**
  1. Call api.Stop(sessionID)
  2. Verify core.Stop called with context.Background()
- **Esperado:** Returns nil on success; errors propagated
- **Cobertura atual:** internal/api/sessions_test.go: TestSessionsAPI_Stop

### SES-42 — useSessions hook: fetches sessions for taskID via api.listSessions, disabled when taskId null
`P2` · `UNIT`
- **Pré:** React hook mounted with taskId='task-1'
- **Passos:**
  1. Mount useSessions('task-1')
  2. Verify useQuery triggered, api.listSessions called
  3. Verify query key: ['sessions', 'task-1']
- **Esperado:** Hook returns {data: Session[], isLoading, error}; disabled={!taskId}
- **Cobertura atual:** none (useSessions not unit tested)

### SES-48 — Stress: rapid Start/Stop/Start on same task → no race conditions, tokens unique, cleanup complete
`P2` · `GO-INT` · 🔧recém-mudado
- **Pré:** DB and runtime ready
- **Passos:**
  1. Start session-a, get token-a
  2. Stop session-a immediately (before process fully started)
  3. Start session-b on same task, get token-b
  4. Verify token-a revoked, token-b valid and different
  5. Verify config files for session-a cleaned, session-b's present
- **Esperado:** No token collisions, no file conflicts, cleanup races handled correctly
- **Cobertura atual:** none (concurrency/stress untested)

### SES-50 — Transcript JSONL parsing edge case: malformed JSONL line → skipped, other lines parsed
`P2` · `GO-INT`
- **Pré:** Transcript file with mixed valid/invalid JSONL
- **Passos:**
  1. Write transcript file: line1 valid JSON, line2 garbage, line3 valid
  2. Call GetTranscript(ctx, sessionID)
  3. Verify line2 skipped, lines 1&3 parsed
- **Esperado:** Returns [msg1, msg3]; invalid line logged/skipped, no error returned
- **Cobertura atual:** none (error resilience untested)

## Worktrees

_Criação, sincronização e limpeza automática de git worktrees vinculados ao ciclo de vida das tasks (criação ao iniciar sessão, remoção ao descartar task). Detecção de orphans externos preservando trabalho do usuário._


### WT-01 — CreateForTask cria worktree único para monorepo com branch derivado
`P0` · `GO-INT` · 🔧recém-mudado
- **Pré:** Projeto monorepo (1 repo) 'proj' em /tmp/proj criado; task 'feature-x' na state 'ready' sem worktrees
- **Passos:**
  1. Chamar WorktreesService.CreateForTask(ctx, taskID, 'feat/new-feature')
  2. Verificar retorno: lista com 1 Worktree
  3. Inspecionar disco: worktree criado em /tmp/proj--feat-new-feature
- **Esperado:** Worktree existe em DB com TaskID=taskID, Path=/tmp/proj--feat-new-feature, Branch=feat/new-feature; arquivo .jarvis/CONTEXT.md escrito no cwd
- **Cobertura atual:** internal/core/worktrees_test.go::TestCreateForTask_Monorepo

### WT-02 — CreateForTask cria worktrees N (um por repo) para multi-repo com diretório pai
`P0` · `GO-INT` · 🔧recém-mudado
- **Pré:** Projeto multi-repo (3 repos: 'backend', 'frontend', 'infra') em /proj; task 'deliver' sem worktrees
- **Passos:**
  1. Chamar CreateForTask(ctx, taskID, 'release/v1.0')
  2. Verificar retorno: lista com 3 Worktrees
  3. Inspecionar disco: /proj--release-v1.0 existe como dir; contém subdir 'backend', 'frontend', 'infra'
- **Esperado:** 3 worktrees em DB, cada um TaskID=taskID, Path=/proj--release-v1.0/{repo}, Branch=release/v1.0; cada repositório tem seu próprio git worktree isolado
- **Cobertura atual:** none

### WT-03 — CreateForTask rejeita idempotentemente task com worktrees existentes
`P0` · `GO-INT` · 🔧recém-mudado
- **Pré:** Task 'ongoing' já tem 1 worktree associado em DB
- **Passos:**
  1. Chamar CreateForTask(ctx, taskID, 'feat/attempt2')
  2. Capturar erro retornado
- **Esperado:** Retorna ErrTaskAlreadyHasWorktrees (não cria novos worktrees, não faz git.Add)
- **Cobertura atual:** internal/core/worktrees_test.go::TestCreateForTask_RejectsIfTaskHasWorktrees

### WT-05 — CreateForTask rollback atomicamente remove worktrees criados se git.Add falha
`P0` · `GO-INT` · 🔧recém-mudado
- **Pré:** Projeto multi-repo (2 repos); mock git.Add configurado para falhar no 2º repo
- **Passos:**
  1. Chamar CreateForTask(ctx, taskID, 'feat/fail-second')
  2. Capturar erro git.Add
  3. Inspecionar DB: nenhuma worktree vinculada à task
- **Esperado:** Retorna erro formatado 'git worktree add...'; rollback() removeu worktrees de ambos repos via git.Remove; DB limpeza completa (nenhuma orfã deixada)
- **Cobertura atual:** none

### WT-06 — SyncProjectWorktrees não importa worktrees externos (preserva experiência do usuário)
`P0` · `GO-INT` · 🔧recém-mudado
- **Pré:** Repositório /tmp/proj tem 2 worktrees no git: 1 tracked em DB (/tmp/proj-tracked), 1 externo (/tmp/proj-user-feat) criado fora J-arvs
- **Passos:**
  1. Chamar SyncProjectWorktrees(ctx, projectID)
  2. Verificar retorno: lista com 1 worktree
  3. Confirmar DB: nenhuma nova row para /tmp/proj-user-feat
- **Esperado:** Apenas worktrees já em knownPaths são reconciliados; worktree externo permanece invisível na UI (não vira orphan fake); não há emissão de worktree.created
- **Cobertura atual:** internal/core/worktrees_test.go::TestSyncProjectWorktrees_IgnoresExternalWorktrees

### WT-08 — CleanupForTask remove worktrees vinculadas e emite evento worktree.removed
`P0` · `GO-INT` · 🔧recém-mudado
- **Pré:** Task 'cleanup-me' tem 1 worktree em DB (TaskID set); git worktree exists no disco
- **Passos:**
  1. Chamar CleanupForTask(ctx, taskID)
  2. Verificar git.Remove foi chamado com Path correto
  3. Inspecionar DB: worktree não existe mais para taskID
- **Esperado:** git.Remove sucesso; worktree row deletada de DB; event emitter chamado com 'worktree.removed' payload incluindo project_id/worktree_id/path/task_id
- **Cobertura atual:** internal/core/worktrees_test.go::TestCleanupForTask_HappyPath

### WT-09 — CleanupForTask converte em orphan se git.Remove falha (não propaga erro)
`P0` · `GO-INT` · 🔧recém-mudado
- **Pré:** Worktree /tmp/broken vinculada à task; git.Remove mock retorna erro genérico 'worktree locked'
- **Passos:**
  1. Chamar CleanupForTask(ctx, taskID)
  2. Inspecionar retorno: sem erro (operação non-fatal)
  3. Verificar DB: worktree row existe mas TaskID=null
- **Esperado:** Worktree orfanizado (TaskID=null); event 'worktree.orphaned' emitido com reason (stderr do git); UI mostra em orfãs para cleanup manual
- **Cobertura atual:** internal/core/worktrees_test.go::TestCleanupForTask_GitFailure_OrphansRow_AndEmitsOrphaned

### WT-10 — CleanupForTask é idempotente para worktrees já removidos (git AlreadyRemoved)
`P0` · `GO-INT` · 🔧recém-mudado
- **Pré:** Worktree /tmp/ghost em DB com TaskID; dir não existe no disco; git.Remove retorna AlreadyRemoved error
- **Passos:**
  1. Chamar CleanupForTask(ctx, taskID)
  2. Capturar resultado
- **Esperado:** Sem erro de propagação; worktree row deletada de DB; event 'worktree.removed' emitido (idempotent success); CleanupForTask pode ser chamado múltiplas vezes
- **Cobertura atual:** internal/core/worktrees_test.go::TestCleanupForTask_AlreadyRemoved_IsIdempotentSuccess

### WT-12 — DeleteOrphan rejeita worktree com task_id ainda vinculado
`P0` · `GO-INT` · 🔧recém-mudado
- **Pré:** Worktree /tmp/owned em DB com TaskID='task-123' set
- **Passos:**
  1. Chamar DeleteOrphan(ctx, worktreeID)
  2. Capturar erro
- **Esperado:** Retorna WorktreeNotOrphanError; UI não permite ✕ em worktrees não-orphans; deve usar task cleanup flow
- **Cobertura atual:** internal/core/worktrees_test.go::TestDeleteOrphan_RejectsOwnedWorktree

### WT-13 — DeleteOrphan remove orphan worktree e emite worktree.removed
`P0` · `GO-INT` · 🔧recém-mudado
- **Pré:** Worktree orphan /tmp/experiment em DB com TaskID=null; git worktree exists
- **Passos:**
  1. Chamar DeleteOrphan(ctx, worktreeID)
  2. Verificar git.Remove chamado com Path
- **Esperado:** git.Remove sucesso; worktree row deletada de DB; event 'worktree.removed' emitido com task_id=null
- **Cobertura atual:** internal/core/worktrees_test.go::TestDeleteOrphan_HappyPath

### WT-14 — DeleteOrphan propaga erro git se worktree não é AlreadyRemoved
`P0` · `GO-INT` · 🔧recém-mudado
- **Pré:** Orphan /tmp/wt-fail em DB; git.Remove mock retorna 'permission denied'
- **Passos:**
  1. Chamar DeleteOrphan(ctx, worktreeID)
  2. Capturar erro
- **Esperado:** Retorna erro git (não converte em orphan); worktree row ainda em DB com TaskID=null; UI mostra erro ao usuário (contraste com CleanupForTask)
- **Cobertura atual:** internal/core/worktrees_test.go::TestDeleteOrphan_GitErrorPropagates

### WT-15 — DeleteOrphan é idempotente para orphan já removido no disco
`P0` · `GO-INT` · 🔧recém-mudado
- **Pré:** Orphan /tmp/ghost em DB com TaskID=null; git.Remove retorna AlreadyRemoved
- **Passos:**
  1. Chamar DeleteOrphan(ctx, worktreeID)
  2. Capturar resultado
- **Esperado:** Sem erro propagado; worktree row deletada de DB; event 'worktree.removed' emitido
- **Cobertura atual:** internal/core/worktrees_test.go::TestDeleteOrphan_AlreadyGone_IsIdempotent

### WT-18 — E2E: Sync descobre orphan após gitWorktreeAdd externo
`P0` · `E2E`
- **Pré:** Projeto criado em /tmp/repo-xyz; user via CLI fez `git worktree add /tmp/repo-xyz-orphan feature/orphan`
- **Passos:**
  1. POST /e2e/worktrees/list_by_project com project_id
  2. Verificar retorno contém /tmp/repo-xyz-orphan
- **Esperado:** Worktree descoberto como orphan (is_orphan=true, task_id=null); branch='feature/orphan'; path no disco confere
- **Cobertura atual:** ui/e2e/projects-flow.spec.ts::listWorktrees via API after gitWorktreeAdd discovers orphan

### WT-20 — E2E: Task discard automaticamente limpa worktrees (cleanup hook)
`P0` · `E2E` · 🔧recém-mudado
- **Pré:** Task 'cleanup-task' em state='in_progress' tem 1 worktree em DB; git worktree existe no disco
- **Passos:**
  1. POST /e2e/tasks/discard com task id
  2. Verificar HTTP 204 (success)
  3. GET /e2e/tasks/get confirma state='discarded'
  4. POST /e2e/worktrees/list_by_project: worktree não aparece mais (ou é orphan se git.Remove falhou)
- **Esperado:** Discard dispara runWorktreeCleanup; CleanupForTask chamado; task state transiciona para 'discarded'; worktrees removidos ou orfanizados conforme necessário
- **Cobertura atual:** ui/e2e/projects-flow.spec.ts::discard task end-to-end (cleanup hook wired)

### WT-04 — CreateForTask falha se cwd derivado já existe no disco (race condition)
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** Dir /proj--feat-exists já está ocupado em disco; task sem worktrees
- **Passos:**
  1. Criar arquivo/dir /proj--feat-exists com permissões de escrita
  2. Chamar CreateForTask(ctx, taskID, 'feat/exists')
  3. Capturar erro
- **Esperado:** Retorna erro 'derived cwd already exists'; nenhum git.Add foi chamado; DB intacto
- **Cobertura atual:** none

### WT-07 — SyncProjectWorktrees atualiza branch de worktree conhecido após checkout manual
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** Worktree /tmp/proj-x em DB com Branch='old'; user fez `git checkout new-branch` manualmente
- **Passos:**
  1. git.List retorna /tmp/proj-x com Branch='new-branch'
  2. Chamar SyncProjectWorktrees(ctx, projectID)
  3. Consultar DB para worktree /tmp/proj-x
- **Esperado:** Branch atualizado de 'old' para 'new-branch' em DB via upsert; worktree.Branch agora reflects realidade do disco
- **Cobertura atual:** internal/core/worktrees_test.go::TestSyncProjectWorktrees_UpdatesBranchOnExisting

### WT-11 — CleanupForTask continua em erro de repo não encontrado (orphana worktree, não falha)
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** Worktree em DB referencia RepositoryID que foi deletado; task em state='discarded'
- **Passos:**
  1. Chamar CleanupForTask(ctx, taskID)
  2. Verificar se função retorna sem erro
- **Esperado:** repoAndProjectPath retorna 'repository not found'; worktree orfanizado; event 'worktree.orphaned' com reason=error message; tarefa discarded completa normalmente
- **Cobertura atual:** none

### WT-16 — API ListByProject retorna worktrees ordenados por path com IsOrphan flag
`P1` · `UNIT`
- **Pré:** 3 worktrees em projeto: 1 com TaskID, 2 orphans; paths /a, /b, /c fora de ordem
- **Passos:**
  1. Chamar WorktreesAPI.ListByProject(projectID)
  2. Verificar cada WorktreeRead
- **Esperado:** Lista retorna 3 elementos; IsOrphan=true iff TaskID==nil; ordenados por path asc; RepositoryName populado (join com repositories)
- **Cobertura atual:** internal/api/worktrees_test.go::TestWorktreesAPI_ListByProject

### WT-17 — API Delete propaga WorktreeNotOrphanError corretamente
`P1` · `UNIT`
- **Pré:** API Delete chamado em worktree com task_id set
- **Passos:**
  1. Chamar WorktreesAPI.Delete(worktreeID)
  2. Capturar erro retornado
- **Esperado:** Retorna WorktreeNotOrphanError (não 422 genérico); mensagem clara para UI
- **Cobertura atual:** internal/api/worktrees_test.go::TestWorktreesAPI_Delete_PropagatesNotOrphan

### WT-19 — E2E: UI OrphansGroup renderiza e remove orfã com ✕
`P1` · `E2E`
- **Pré:** Worktree orphan /tmp/exp em DB; UI carregada em ProjectNode
- **Passos:**
  1. Verificar OrphansGroup exibe 'órfãs (1)'
  2. Clicar ✕ no WorktreeRow
  3. Aguardar api.deleteWorktree chamado
- **Esperado:** Button remove-worktree-{id} visível; click dispara mutation; toast ou inline error se falhar (e.g. 'worktree belongs to active task')
- **Cobertura atual:** ui/src/components/OrphansGroup.test.tsx + ui/src/components/WorktreeRow.test.tsx

### WT-21 — UI OverviewTab mostra branch imutável após worktree criado (1ª sessão)
`P1` · `E2E` · 🔧recém-mudado
- **Pré:** Task sem worktrees, branch=null; branch input editável; usuário inicia sessão
- **Passos:**
  1. Clicar 'Iniciar sessão'
  2. Aguardar worktrees criados (CreateForTask sucesso)
  3. Recarregar OverviewTab
- **Esperado:** BranchEditField desaparece; exibe 'Branch: <code>feat/x</code> (imutável após 1ª sessão)'; worktrees renderizados em <details> com repo names e paths
- **Cobertura atual:** ui/src/components/task-detail/OverviewTab.tsx + ui/src/hooks/useTaskMutations.ts

### WT-23 — Task context file (.jarvis/CONTEXT.md) escrito atomicamente em CreateForTask
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** CreateForTask executado com sucesso em disco real (não fakes)
- **Passos:**
  1. Inspecionar cwd do worktree: <path>/.jarvis/CONTEXT.md deve existir
  2. Ler conteúdo: deve conter task title, project name, branch, repo list
- **Esperado:** Arquivo escrito com mode 0644; contém rendição markdown com estrutura esperada; não é deletado se git.Add falha (best-effort)
- **Cobertura atual:** internal/core/task_context_test.go::TestWriteTaskContext_*

### WT-24 — Project delete rejeita se tem tasks não-discarded (worktrees são dependência transitive)
`P1` · `GO-INT`
- **Pré:** Projeto com task em state='in_progress' que tem worktrees
- **Passos:**
  1. Chamar ProjectsService.Delete(projectID)
  2. Capturar erro
- **Esperado:** Retorna ProjectHasTasksError; projeto não deletado; worktrees intactos; força user a discard task primeiro
- **Cobertura atual:** none

### WT-22 — Branch slug converte path-unsafe chars (/, espaço) para hífen
`P2` · `UNIT`
- **Pré:** CreateForTask chamado com branch strings variadas
- **Passos:**
  1. Testar branchSlug('feat/new-thing') -> 'feat-new-thing'
  2. Testar branchSlug('x y z') -> 'x-y-z'
  3. Testar branchSlug('feat/foo/bar') -> 'feat-foo-bar'
- **Esperado:** Todas conversões corretas; cwd derivado tem syntax válida no filesystem
- **Cobertura atual:** internal/core/worktrees_test.go::TestBranchSlug

### WT-25 — Worktree repo não encontrado: repoAndProjectPath retorna erro tratado em cleanup
`P2` · `GO-INT`
- **Pré:** Worktree em DB com RepositoryID que não existe mais
- **Passos:**
  1. Chamar CleanupForTask(ctx, taskID)
  2. Verificar logs/events
- **Esperado:** repoAndProjectPath retorna 'repository not found'; worktree orfanizado; operação não falha; task cleanup continua para outros worktrees
- **Cobertura atual:** none

## Runs from Panel & Bootstrap

_Initiate containerized stacks via manifest (Run Panel), bootstrap ephemeral Claude sessions to generate manifests, manage Docker lifecycle (building/seeding/ready/failed/stopped), allocate ports, emit logs via SSE, handle healthchecks, keep failed runs visible via GetLatestByTask banner._


### RUN-01 — Start Run happy path: manifest valid, containers start ready
`P0` · `E2E` · 🔧recém-mudado
- **Pré:** Task in_progress or review state, valid .orchestrator/run.yml exists, docker available, ports available
- **Passos:**
  1. UI: Click ▶ Run button in TaskCard RunStatus component
  2. API/Wails: RunsAPI.Start(taskID) calls core.RunsService.StartRun
  3. Core: Verify task state not terminal, no active run exists
  4. Core: Load manifest from .orchestrator/run.yml, validate schema
  5. Core: Topo-sort services by depends_on, detect cycles
  6. Core: Allocate unique ports for each service.port > 0
  7. Core: Create Docker network jarvis-run-{runID[:8]}
  8. Core: Build container images (if spec.Build set) with tag jarvis-run-{runID[:8]}-{service}
  9. Core: Start containers in dependency order via docker run, inject resolved $PORT_* and $URL_* env vars
  10. Core: Poll healthcheck via docker inspect HealthStatus (interval 5s, max 10 retries) for each service
  11. Core: Run seed scripts via docker exec (timeout 60s default) if spec.Seed exists
  12. Store: Update run_instances row: status='ready', containers_json={service->container_id}
  13. Bus: Emit run.status_changed event
  14. UI: useRun query invalidated, RunStatus re-renders with status=ready, URL chips visible
- **Esperado:** RunStatus shows ● ready label, ⏹ Stop button, one URL chip per exposed service (e.g. 🌐 backend :31101); clicking chip opens http://localhost:31101 in browser; no errors
- **Cobertura atual:** internal/core/runs_integration_test.go (partial: seeding, container start); ui/src/components/RunStatus.test.tsx (mock run ready state)

### RUN-02 — Start Run detects missing manifest, triggers Bootstrap
`P0` · `E2E` · 🔧recém-mudado
- **Pré:** Task in_progress, no .orchestrator/run.yml exists
- **Passos:**
  1. UI: Click ▶ Run on TaskCard
  2. API: RunsAPI.Start returns {run: null, bootstrap: {reason: 'manifest_missing'}}
  3. UI: useStartRun catches StartRunResult, checks result.bootstrap?.reason
  4. UI: RunStatus calls setBootstrapOpen(true), renders BootstrapModal
  5. BootstrapModal: Phase idle, displays 'Manifesto faltando' + 'Iniciar bootstrap' button
- **Esperado:** BootstrapModal appears with title 'Manifesto faltando', initial phase=idle, error-free
- **Cobertura atual:** ui/src/components/RunStatus.test.tsx (mock startRun.isError branch)

### RUN-03 — Bootstrap flow: Start → Waiting → Propose Valid → Auto-fire in 10s
`P0` · `E2E` · 🔧recém-mudado
- **Pré:** BootstrapModal open (idle phase), task has worktree or will auto-create one
- **Passos:**
  1. UI: Click 'Iniciar bootstrap' button in BootstrapModal
  2. BootstrapModal: phase → starting, bootstrap.mutate() calls api.bootstrapManifest
  3. API: BootstrapAPI.Start(taskID) → core.BootstrapService.Start
  4. Core: Resolve worktree CWD (create if missing via WorktreesService), mkdir .orchestrator, write BOOTSTRAP_PROMPT.md
  5. Core: Setup fsnotify watcher on .orchestrator dir, spawn ephemeral Claude session with ai-jail config + auto-trigger message
  6. Core: watchManifest goroutine listens for run.yml Create/Write events
  7. Claude: (simulated) writes .orchestrator/run.yml with valid manifest
  8. Core: handleDetection reads manifest, validates via yaml.Unmarshal + Validate(), emits bootstrap.proposed event
  9. UI/Event: receives 'bootstrap.proposed' event, updates bootstrapProposedStore
  10. BootstrapModal: useEffect on proposed updates phase to 'preview-valid', renders manifest preview + countdown timer
  11. BootstrapModal: Timer auto-fires at 10s (AUTO_FIRE_MS), startRun.mutate() starts the run and closes modal
- **Esperado:** Modal phases: idle → starting → waiting → preview-valid (countdown 10...1...0); auto-fires and modal closes; run starts successfully; no invalid manifests accepted
- **Cobertura atual:** internal/core/bootstrap_integration_test.go (manifest detection + event emit); ui/src/components/dialogs/BootstrapModal.test.tsx (phase transitions mock)

### RUN-16 — RunStatus banner: when no active run, GetLatestByTask surfaces failed run + error message
`P0` · `E2E` · 🔧recém-mudado
- **Pré:** Task has previous failed run (status='failed', ended_at set, error_message='seed failed: db')
- **Passos:**
  1. UI: RunStatus renders, useRun(taskId) returns null (no active run → 404 handled as null)
  2. UI: Calls useLatestRun(taskId) → api.getLatestRun
  3. API: RunsAPI.GetLatest calls repo.GetLatestByTask (ORDER BY started_at DESC LIMIT 1)
  4. Store: Returns failed run row with status='failed', error_message='seed failed: db'
  5. UI: RunStatus renders idle state, lastFailed = latestRun.data?.status === 'failed'
  6. UI: Renders <div data-status='failed'> with text '✗ última run: seed failed: db'
  7. UI: ▶ Run button below allows retry
- **Esperado:** Failed run visible even when no active run; error message displayed; user can click Run to retry
- **Cobertura atual:** ui/src/hooks/useRun.ts (useLatestRun); internal/store/runs.go::GetLatestByTask

### RUN-17 — Stop Run: gracefully stops all containers, releases ports, marks stopped
`P0` · `GO-INT` · 🔧recém-mudado
- **Pré:** Active run in status=ready with 2+ containers
- **Passos:**
  1. UI: Click ⏹ Stop button in RunStatus
  2. API: RunsAPI.Stop(runID) → core.StopRun
  3. Core: repo.GetByID, checks EndedAt == nil (not already stopped)
  4. Core: Transitions to stopping
  5. Core: Extracts containerIDs from ContainersJSON, launches parallel WaitGroup goroutines
  6. Docker: docker.Stop(cid) + docker.Rm(cid) for each container in parallel
  7. Docker: docker.NetworkRm(networkName)
  8. Core: Allocator.Release(port) for each port in Ports()
  9. Store: repo.MarkEnded(runID, 'stopped', '')
  10. Bus: Emits run.status_changed → stopped
- **Esperado:** Run transitions stopped → ready, all containers stopped and removed, network cleaned, ports released, UI RunStatus re-renders idle with ▶ Run
- **Cobertura atual:** internal/core/runs_integration_test.go::TestStopRun

### RUN-04 — Bootstrap rejects invalid manifest, keeps session alive for edits
`P1` · `UNIT` · 🔧recém-mudado
- **Pré:** Bootstrap session active, Claude writes invalid manifest (e.g., missing image/build, circular deps)
- **Passos:**
  1. Claude: writes .orchestrator/run.yml with invalid schema
  2. Core: handleDetection reads file, validateManifestBytes returns valid=false + error list
  3. Bus: Emits bootstrap.proposed with valid=false, errors=['service backend: must specify image or build']
  4. BootstrapModal: phase → preview-invalid, renders <AlertCircle> icon, error list in red box
  5. BootstrapModal: Entry NOT deleted from bootstrap.active[taskID] (session still running)
  6. Claude: (user can edit via still-running session) fixes manifest, writes again
  7. Core: Next handleDetection validates again, now valid=true, transitions to preview-valid
- **Esperado:** Modal shows validation errors, user can fix in running Claude, next write event re-evaluates; session keeps running until valid manifest accepted
- **Cobertura atual:** internal/core/bootstrap_test.go (validateManifestBytes); internal/core/manifest_test.go (Validate schema)

### RUN-05 — Bootstrap errors: task terminal state → blocks start
`P1` · `UNIT` · 🔧recém-mudado
- **Pré:** Task state = done or discarded (terminal)
- **Passos:**
  1. UI: Attempt api.bootstrapManifest(taskID)
  2. API: BootstrapAPI.Start delegates to core.BootstrapService.Start
  3. Core: tasks.Get(taskID), checks IsTerminal(task.State) returns true
  4. Core: Returns ErrTaskInTerminalState
  5. API: translateBootstrapErr maps to human message 'task is already in a terminal state; bootstrap not allowed'
  6. UI: Error rendered in BootstrapModal.bootstrap.isError alert
- **Esperado:** Error alert appears with message about terminal task, no session spawned, modal stays open for retry or cancel
- **Cobertura atual:** internal/core/bootstrap_test.go::TestBootstrapStart_TaskTerminal

### RUN-06 — Bootstrap errors: manifest already exists → prevent double-bootstrap
`P1` · `UNIT` · 🔧recém-mudado
- **Pré:** Previous bootstrap completed or manual .orchestrator/run.yml exists, user clicks Run again
- **Passos:**
  1. UI: BootstrapModal opens (manifest_missing), user clicks 'Iniciar bootstrap'
  2. Core: resolveCwd, mkdir .orchestrator succeeds, then checks os.Stat(manifestPath)
  3. os.Stat: Returns !os.IsNotExist(err) (file exists)
  4. Core: Returns ErrManifestAlreadyExists
  5. API: Translates to 'manifest already exists; click ▶ Run again to start the stack'
  6. UI: Error shown, modal suggests user retry Run button (which should now start the stack, not bootstrap)
- **Esperado:** Error alert guides user to retry Run, no manifest overwritten
- **Cobertura atual:** internal/core/bootstrap_test.go::TestBootstrapStart_ManifestExists

### RUN-07 — Cancel Bootstrap: kills ephemeral session, cleans .ai-jail + prompt file
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** Bootstrap session waiting phase, user clicks X (Cancelar) button
- **Passos:**
  1. UI: BootstrapModal onCancelAll calls useCancelBootstrap(taskID).mutate()
  2. API: BootstrapAPI.Cancel(taskID) → core.BootstrapService.Cancel
  3. Core: Acquires mu lock, finds entry in active[taskID]
  4. Core: Calls entry.cancel() (context.CancelFunc), stops watchManifest goroutine
  5. Core: Calls runtime.Kill(context.Background(), entry.handle) on ephemeral process
  6. Core: Removes .orchestrator/BOOTSTRAP_PROMPT.md
  7. Core: Removes entry from active map under lock
  8. Core: Sandbox.RemoveAijailConfig(cwd) cleans .ai-jail config file
  9. UI: Modal closes, RunStatus returns to idle state with ▶ Run button
- **Esperado:** Session process killed, cleanup files removed, modal closed, no orphaned watcher/process; user can retry Run later
- **Cobertura atual:** internal/core/bootstrap_test.go::TestBootstrapCancel (partial)

### RUN-08 — Topo-sort: services with depends_on start in correct order
`P1` · `UNIT`
- **Pré:** Manifest has frontend→backend→db dependencies
- **Passos:**
  1. Manifest: frontend depends_on=[backend], backend depends_on=[db], db has no deps
  2. Core: topoSort via Kahn's algorithm returns [db, backend, frontend]
  3. Core: StartRun iterates order for Build/ContainerStart, db launched first
  4. Docker: db fully healthy before backend starts, backend fully healthy before frontend starts
  5. Core: Healthcheck polled in order (db, then backend, then frontend)
- **Esperado:** Services start in dependency order; earlier services are ready before dependents begin; no ordering errors or timeouts
- **Cobertura atual:** internal/core/runs_test.go::TestTopoSort_DependencyChain

### RUN-09 — Circular dependency detected → manifest validation fails
`P1` · `UNIT`
- **Pré:** Manifest has A→B→A or A→B→C→A circular chain
- **Passos:**
  1. Manifest: a depends_on=[b], b depends_on=[a]
  2. Core: topoSort runs Kahn's algorithm, len(order) < len(services) after queue exhausted
  3. Core: Returns ErrCircularDeps
  4. StartRun: Short-circuits before Docker operations
- **Esperado:** ErrCircularDeps error returned, run not started, user sees error message
- **Cobertura atual:** internal/core/runs_test.go::TestTopoSort_Cycle_ReturnsError; internal/core/manifest_test.go::detectCycle

### RUN-10 — Port allocation: unique host ports assigned, released on failure
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** Two services expose ports, allocator has available range
- **Passos:**
  1. Manifest: backend port=8080, frontend port=3000
  2. Core: Iterates services, backend.Port > 0 → allocator.Allocate() returns e.g. 31101
  3. Core: frontend.Port > 0 → allocator.Allocate() returns e.g. 31102
  4. Core: ports map = {backend: 31101, frontend: 31102}
  5. Core: Substitutions resolve $PORT_backend → 31101, $URL_backend → http://localhost:31101
  6. [Error scenario]: ContainerStart fails on second service
  7. Core: rollback releases [31101, 31102] back to allocator pool
  8. Allocator: Both ports now available for next run
- **Esperado:** Ports unique per run, released on failure, substitutions propagated to env vars, accessible via URLs
- **Cobertura atual:** internal/core/runs_integration_test.go (port allocation mocked in fakeDocker)

### RUN-11 — Healthcheck timeout → rollback, mark run failed
`P1` · `UNIT` · 🔧recém-mudado
- **Pré:** Container started but health check never passes (interval 5s, max 10 retries = 50s timeout)
- **Passos:**
  1. Core: StartRun calls docker.ContainerStart for service with healthcheck
  2. Docker: Container starts but docker inspect HealthStatus returns 'unhealthy'
  3. Core: waitHealthy polls ContainerHealthStatus, loop max retries times
  4. Loop: i=0..9, status != healthy, sleep interval
  5. After retries: Returns error 'healthcheck timeout'
  6. Core: rollback(…, 'healthcheck timeout: {service}')
  7. Rollback: Stops/removes container, cleans network, releases ports, calls repo.MarkFailed
  8. Store: run_instances row status=failed, error_message='healthcheck timeout: db'
  9. Bus: Emits run.status_changed with status=failed
- **Esperado:** Run marked failed with descriptive error, containers cleaned up, ports released, UI shows ✗ failed banner
- **Cobertura atual:** internal/core/runs_test.go::TestStartRun_HealthcheckFailure (partial)

### RUN-12 — Seed command execution → timeout 60s default, custom timeout respected
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** Service has seed spec with command and optional timeout, container healthy
- **Passos:**
  1. Manifest: db service has seed: {command: [bash, -c, 'mysql < init.sql'], timeout: 120s}
  2. Core: After healthcheck passes, StartRun transitions to seeding
  3. Core: Iterates services, db.Seed exists, timeout = 120s
  4. Core: docker.RunInContainer(ctx, cid, [bash, -c, 'mysql < init.sql'], 120s)
  5. [Success]: Script completes in 30s, no error
  6. Core: Continues to next service or finish
  7. [Error]: Script hangs, context timeout fires at 120s, RunInContainer returns error
  8. Core: rollback with 'seed failed: db: context deadline exceeded'
- **Esperado:** Seed runs with custom timeout (or 60s default), blocks on until complete or timeout; failure triggers rollback and run.failed
- **Cobertura atual:** internal/core/runs_integration_test.go (seed execution mocked)

### RUN-13 — Docker build: Dockerfile from spec.Build, image tagged as jarvis-run-{ID[:8]}-{service}
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** Service has build: './Dockerfile' (relative to cwd)
- **Passos:**
  1. Manifest: backend service has build='./Dockerfile'
  2. Core: StartRun iterates order, backend.Build != '', constructs tag 'jarvis-run-abc12345-backend'
  3. Core: docker.Build(ctx, filepath.Join(cwd, './Dockerfile'), 'jarvis-run-abc12345-backend')
  4. Docker: builds image from cwd/Dockerfile, tags as jarvis-run-abc12345-backend
  5. [Error]: Build fails (e.g., syntax error in Dockerfile)
  6. Core: rollback with 'image build error' in error_message
- **Esperado:** Image built and tagged correctly, used for ContainerStart; build errors trigger rollback
- **Cobertura atual:** internal/core/runs_integration_test.go::TestStartRun_BuildAndStart

### RUN-15 — Env substitution: $RUN_ID, $CWD, $PORT_*, $URL_* resolved before container start
`P1` · `UNIT` · 🔧recém-mudado
- **Pré:** Manifest specifies env vars with tokens
- **Passos:**
  1. Manifest: backend {port: 8080, env: {DB_URL: '$URL_db', CACHE_PORT: '$PORT_cache', RUN_ID: '$RUN_ID', BASEDIR: '$CWD'}}
  2. Core: startRun allocates ports {db: 31101, cache: 31102}, runID='abc-123...'
  3. Core: ResolveSubstitutions replaces tokens: DB_URL → 'http://localhost:31101', CACHE_PORT → '31102', RUN_ID → 'abc-123...', BASEDIR → '/path/to/cwd'
  4. Core: ContainerSpec.Env = {DB_URL: 'http://localhost:31101', CACHE_PORT: '31102', RUN_ID: 'abc-123...', BASEDIR: '/path/to/cwd'}
  5. Docker: Container launched with resolved env vars
- **Esperado:** All tokens resolved correctly, containers can reference sibling services by port/URL, run-specific IDs available
- **Cobertura atual:** internal/core/manifest.go::ResolveSubstitutions + ResolveSubstitutionErrors (validation)

### RUN-19 — Task cleanup on terminal: CleanupForTask stops active run if task moves to done/discarded
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** Task has active run, task state changes to done or discarded
- **Passos:**
  1. Task state → done via API
  2. TasksService.Update dispatches cleanup hooks
  3. RunsService.CleanupForTask(taskID) is called
  4. Core: repo.GetActiveByTask(taskID) returns active run
  5. Core: StopRun called on that run_id
  6. Docker: Containers and network cleaned
- **Esperado:** Active run automatically stopped when task terminal, no orphaned containers
- **Cobertura atual:** internal/core/runs.go::CleanupForTask

### RUN-21 — Docker unavailable: docker CLI not found → ErrDockerUnavailable before any work
`P1` · `UNIT` · 🔧recém-mudado
- **Pré:** Docker not in PATH, manifest valid
- **Passos:**
  1. API: api.startRun(taskID)
  2. Core: StartRun first line checks defaultDockerCheck() → exec.LookPath('docker') error
  3. Core: Returns ErrDockerUnavailable wrapped
  4. No manifest loaded, no DB changes
- **Esperado:** Error returned immediately, user sees 'docker CLI not available' or similar message
- **Cobertura atual:** internal/core/runs_test.go (dockerCheck injected)

### RUN-22 — Task not eligible: task state = draft or discarded → blocks StartRun
`P1` · `UNIT` · 🔧recém-mudado
- **Pré:** Task state = draft (terminal, not in_progress/review)
- **Passos:**
  1. API: startRun(taskID)
  2. Core: tasks.Get(taskID).State = 'draft'
  3. Core: IsTerminal(draft) = true
  4. Core: Returns ErrTaskNotEligible
  5. RunsAPI.Start propagates error to UI
- **Esperado:** Error prevents run start, user sees 'task state does not allow runs' or 'must be in_progress or review'
- **Cobertura atual:** internal/core/runs.go::StartRun task guard

### RUN-23 — Task has active run: second start attempt rejected
`P1` · `UNIT` · 🔧recém-mudado
- **Pré:** Task has active run (status pending/building/seeding/ready)
- **Passos:**
  1. API: startRun(taskID) while run already active
  2. Core: repo.GetActiveByTask(taskID) returns non-nil run
  3. Core: Returns ErrTaskHasActiveRun
- **Esperado:** Error 'task already has an active run', user cannot start second parallel run
- **Cobertura atual:** internal/core/runs.go::StartRun active run guard

### RUN-24 — Logs SSE stream: /api/runs/{runID}/logs?service=backend streams container logs line-by-line
`P1` · `E2E` · 🔧recém-mudado
- **Pré:** Run active, service=backend container running and producing logs
- **Passos:**
  1. UI: Open RunLogsPanel or similar, calls api.getRunLogsEventSourceURL(runID, 'backend')
  2. API: Constructs 'http://127.0.0.1:48123/api/runs/{runID}/logs?service=backend'
  3. Browser: EventSource(url) opens SSE connection
  4. Server: RunsAPI.LogsHandler handles GET /api/runs/{runID}/logs
  5. Handler: Extracts runID + service from query, calls ContainerIDFor(runID, service)
  6. Handler: docker.StreamLogs(ctx, cid, pw) pipes container logs to PipeWriter
  7. Handler: bufio.Scanner reads lines, emits 'data: {line}\n\n'
  8. Browser: onmessage fires per line, UI appends to logs panel
- **Esperado:** Container logs stream real-time as SSE events, no buffering, readable in logs panel
- **Cobertura atual:** internal/api/runs.go::LogsHandler; ui/src/components/RunLogsPanel.tsx

### RUN-25 — Manifest validation: env var references unknown service → error
`P1` · `UNIT`
- **Pré:** Manifest has backend service referencing undefined service in env var
- **Passos:**
  1. Manifest: backend {env: {OTHER_API: '$URL_nonexistent'}}
  2. Core: LoadManifest + Validate runs tokenRe.FindAllStringSubmatch on env values
  3. Validate: Finds '$URL_nonexistent', checks m.Services['nonexistent'] → not found
  4. Problems list += 'service backend: env value ... references unknown service nonexistent'
  5. ManifestSpec.Validate returns error with that message
- **Esperado:** Validation fails with clear error, run not started, user sees which service ref is broken
- **Cobertura atual:** internal/core/manifest_test.go::TestValidate_EnvRefUnknownService

### RUN-26 — Manifest validation: env references service with no port → error
`P1` · `UNIT`
- **Pré:** Manifest has service A {env: '$URL_db'} but db {port: 0} (no port)
- **Passos:**
  1. Manifest: frontend {env: {DB: '$URL_db'}}, db {image: postgres} (port not set, default 0)
  2. Validate: tokenRe finds '$URL_db', checks m.Services['db'].Port == 0
  3. Problems += 'service frontend: env value ... references service db which has no port'
  4. ManifestSpec.Validate returns error
- **Esperado:** Validation fails, prevents run with unportable dependency
- **Cobertura atual:** internal/core/manifest_test.go::TestValidate_EnvRefNoPort

### RUN-27 — Manifest validation: image and build mutually exclusive → error
`P1` · `UNIT`
- **Pré:** Service specifies both image and build
- **Passos:**
  1. Manifest: backend {image: 'node:18', build: './Dockerfile'}
  2. Validate: hasImage && hasBuild → true
  3. Problems += 'service backend: image and build are mutually exclusive'
- **Esperado:** Validation fails with clear message
- **Cobertura atual:** internal/core/manifest_test.go::TestValidate_MutualExclusive

### RUN-28 — DeriveRunCWD: worktree exists → use its path (multi-worktree uses parent dir)
`P1` · `UNIT` · 🔧recém-mudado
- **Pré:** Task has one or more worktrees
- **Passos:**
  1. Scenario 1 (single worktree): worktrees.ListByTask returns [{Path: '/user/repos/myapp/feat-x'}]
  2. DeriveRunCWD: len(wts) == 1 → returns wts[0].Path = '/user/repos/myapp/feat-x'
  3. Scenario 2 (multi-worktree): returns [{Path: '/user/repos/myapp/feat-x'}, {Path: '/user/repos/myapp/hotfix-y'}]
  4. DeriveRunCWD: len(wts) > 1 → returns filepath.Dir(wts[0].Path) = '/user/repos/myapp' (shared parent)
- **Esperado:** Single worktree: exact path used. Multi-worktree: shared parent used as run CWD
- **Cobertura atual:** internal/core/runs.go::DeriveRunCWD

### RUN-29 — DeriveRunCWD: no worktree → derive from project path + branch slug
`P1` · `UNIT` · 🔧recém-mudado
- **Pré:** Task has no worktree, project path=/projects/myapp, branch=feat/x-y
- **Passos:**
  1. worktrees.ListByTask returns []
  2. projects.Get(projectID) returns {Path: '/projects/myapp'}
  3. task.Branch = 'feat/x-y' → slug = 'feat-x-y' (ReplaceAll('/', '-'))
  4. DeriveRunCWD returns '/projects/myapp-feat-x-y'
- **Esperado:** CWD derived correctly, manifest looked up in .orchestrator/run.yml under that dir
- **Cobertura atual:** internal/core/runs_test.go (DeriveRunCWD scenarios)

### RUN-14 — Mount source: spec.MountSource auto-enabled if build present, explicit override respected
`P2` · `UNIT` · 🔧recém-mudado
- **Pré:** Service has build set or mount_source explicitly set
- **Passos:**
  1. Manifest case 1: backend service {build: './app', port: 8080} (mount_source not set)
  2. Core: buildContainerSpec checks mount_source nil → defaults to (spec.Build != ''), true
  3. Docker: Volumes={cwd/app -> /workspace} in ContainerSpec
  4. Manifest case 2: db service {image: 'postgres', mount_source: false} (explicit no mount)
  5. Core: buildContainerSpec checks mount_source = false → override respected
  6. Docker: No volume mounted for db
- **Esperado:** Source mounted by default for build services, respected if explicitly false; databases or non-dev containers can skip mount
- **Cobertura atual:** internal/core/runs.go::buildContainerSpec logic

### RUN-18 — Idempotent stop: calling Stop twice on same run succeeds both times
`P2` · `UNIT` · 🔧recém-mudado
- **Pré:** Run already stopped (EndedAt set)
- **Passos:**
  1. API: StopRun(runID) first time completes successfully
  2. Store: run_instances.ended_at = <timestamp>
  3. API: StopRun(runID) second time
  4. Core: run.EndedAt != nil returns immediately with nil error (no-op)
- **Esperado:** Second stop returns nil error, no re-cleanup attempted, idempotent
- **Cobertura atual:** internal/core/runs.go::StopRun idempotent check

### RUN-20 — CleanupOrphans on boot: finds runs with ended_at=null, stops containers
`P2` · `UNIT` · 🔧recém-mudado
- **Pré:** Unclean shutdown left active runs in DB (ended_at IS NULL)
- **Passos:**
  1. App boot: core.CleanupOrphans() called
  2. Core: ListActive returns all runs where ended_at IS NULL
  3. For each: Extracts containerIDs, stops/removes each container
  4. Docker: NetworkRm for each run's network_name
  5. Store: MarkEnded(runID, 'stopped', 'orphan_cleanup_on_boot')
- **Esperado:** Orphaned containers cleaned, database marked, app restarts clean
- **Cobertura atual:** internal/core/runs.go::CleanupOrphans

### RUN-30 — RunStatus test: transitions from idle→building→seeding→ready show correct spinner text
`P2` · `UNIT` · 🔧recém-mudado
- **Pré:** Run object with various status values
- **Passos:**
  1. RunStatus component receives run data
  2. status=pending: renders '· pending'
  3. status=building: renders '◐ building'
  4. status=seeding: renders '◑ seeding'
  5. status=ready: renders '● ready' + Stop button + URL chips
  6. status=stopping: renders '◯ stopping' (spinner-text)
- **Esperado:** Each status renders correct label and state-appropriate UI
- **Cobertura atual:** ui/src/components/RunStatus.test.tsx (status branches)

## Master Session & MCP (Claude persistent PTY + JSON-RPC task tools)

_Gerencia sessão Claude persistente em PTY (xterm), spawn via ai-jail, persiste via DB, comunica com frontend via events, expõe 7 MCP tools (list/create/update/discard tasks), clipboard terminal (Ctrl+C/Shift+C/Shift+V), settings com enableAllProjectMcpServers, status connected/disconnected._


### MST-01 — Master Start preflight: rejeita se sandbox indisponível
`P0` · `UNIT` · 🔧recém-mudado
- **Pré:** MasterService.Start() é chamado com sandbox check retornando erro
- **Passos:**
  1. Injeta sandboxCheck() para retornar ErrSandboxUnavailable
  2. Chama MasterAPI.Start() via Wails
- **Esperado:** Erro ErrMasterSandboxUnavailable; nenhum processo spawned; status permanece disconnected
- **Cobertura atual:** internal/core/master_test.go não cobre este cenário explicitamente

### MST-02 — Master Start preflight: rejeita se MCP URL não está ready
`P0` · `UNIT` · 🔧recém-mudado
- **Pré:** MasterService.Start() é chamado com mcpURL returning empty string
- **Passos:**
  1. Configura mcpURL func() para retornar ""
  2. Chama MasterAPI.Start()
- **Esperado:** Erro ErrMasterMCPUnavailable; nenhum spawn; DB vazio
- **Cobertura atual:** internal/core/master_test.go::TestMasterService_Start_MCPUnavailable_Errors

### MST-03 — Master Start cria nova sessão com UUID gerado
`P0` · `UNIT` · 🔧recém-mudado
- **Pré:** DB vazio, sandbox ok, MCP URL ready (http://127.0.0.1:8080)
- **Passos:**
  1. Chama MasterAPI.Start()
  2. Valida resposta MasterStatusView
- **Esperado:** session_id é UUID válido não-vazio, pid > 0, running=true, arquivo ~/.mcp.json criado com bearer token
- **Cobertura atual:** internal/core/master_test.go::TestMasterService_Start_NoRow_GeneratesNewSessionID

### MST-04 — Master Start idempotent: processo vivo reusa session_id
`P0` · `UNIT` · 🔧recém-mudado
- **Pré:** DB tem row com pid=<vivo>, ClaudeSessionID="saved-uuid"
- **Passos:**
  1. Chama MasterAPI.Start() segunda vez
- **Esperado:** Retorna session_id "saved-uuid" (reusado), não spawna novo processo, fs.spawnedAt vazio
- **Cobertura atual:** internal/core/master_test.go::TestMasterService_Start_AlreadyRunning_IsIdempotent

### MST-06 — Master Stop limpa PID preserva session_id
`P0` · `UNIT` · 🔧recém-mudado
- **Pré:** Master está running com session_id e pid > 0
- **Passos:**
  1. Chama MasterAPI.Stop()
  2. Lê status do DB
- **Esperado:** PID=nil, ClaudeSessionID preservado, evento master.status {running:false} emitido
- **Cobertura atual:** internal/core/master_test.go::TestMasterService_Stop_ClearsPIDPreservesSessionID

### MST-08 — Master Send delega para underlying PTY session
`P0` · `E2E` · 🔧recém-mudado
- **Pré:** Master running, termref válido na UI
- **Passos:**
  1. Chama MasterAPI.Send("j-arvis list_tasks\n")
  2. Monitora xterm.write via JS
- **Esperado:** Dados entram no stdin do processo PTY, QuickCommands pode injetar comandos
- **Cobertura atual:** none

### MST-10 — Master Status verifica PID vivo vs stale
`P0` · `UNIT` · 🔧recém-mudado
- **Pré:** DB tem row com pid, processo realmente morreu mas watchdog não rodou ainda
- **Passos:**
  1. Chama MasterAPI.Status()
  2. usa syscall.Kill(pid, 0) para validar
- **Esperado:** Running=false, PID=0 (stale PID); não bloqueia esperando processo
- **Cobertura atual:** none

### MST-13 — WriteMasterSettings: .mcp.json criado com bearer token no root
`P0` · `UNIT` · 🔧recém-mudado
- **Pré:** cwd vazio, mcpURL="http://127.0.0.1:42037", token="tok-abc"
- **Passos:**
  1. Chama WriteMasterSettings(cwd, mcpURL, token)
  2. Lê .mcp.json
- **Esperado:** JSON contém mcpServers.j-arvis-master.url=<base>/api/mcp, Authorization header com Bearer token, modo 0600
- **Cobertura atual:** internal/sandbox/settings_master_test.go::TestWriteMasterSettings_WritesMcpJsonAtRoot

### MST-14 — WriteMasterSettings: enableAllProjectMcpServers=true em .claude/settings.json
`P0` · `UNIT` · 🔧recém-mudado
- **Pré:** cwd vazio
- **Passos:**
  1. Chama WriteMasterSettings(cwd, url, token)
  2. Lê .claude/settings.json
- **Esperado:** JSON contém {"enableAllProjectMcpServers": true}; sem hooks, sem secrets
- **Cobertura atual:** internal/sandbox/settings_master_test.go::TestWriteMasterSettings_AutoApprovesProjectMcpServers

### MST-21 — QuickCommands: botão 'list tasks' injeta comando no terminal
`P0` · `E2E` · 🔧recém-mudado
- **Pré:** MasterSidebar montado, QuickCommands visível
- **Passos:**
  1. Clica botão com label 'list tasks'
  2. onInject('j-arvis list_tasks') é chamado
  3. MasterAPI.Send('j-arvis list_tasks\n') executa
- **Esperado:** Comando injetado no stdin do PTY com newline
- **Cobertura atual:** none

### MST-26 — MasterSidebar: evento master.output escreve no xterm
`P0` · `E2E` · 🔧recém-mudado
- **Pré:** Master rodando, MasterSidebar montado
- **Passos:**
  1. Backend emite EventsOn('master.output', 'hello\n')
  2. Component listener recebe chunk
- **Esperado:** term.write('hello\n') chamado, texto aparece no xterm
- **Cobertura atual:** none

### MST-27 — MasterSidebar: evento master.status atualiza status e pid
`P0` · `E2E` · 🔧recém-mudado
- **Pré:** MasterAPI.Start() completado
- **Passos:**
  1. Backend emite EventsOn('master.status', {running:true, pid:999, session_id:'uuid'})
  2. Component setState({status:connected, pid:999, sessionId:'uuid'})
- **Esperado:** Status='connected', pid=999, sessionId visível em header
- **Cobertura atual:** none

### MST-28 — MasterSidebar: evento master.exit com early_exit=true tenta recuperar
`P0` · `E2E` · 🔧recém-mudado
- **Pré:** Master rodando, processo morre < 2s
- **Passos:**
  1. Backend emite EventsOn('master.exit', {early_exit:true, elapsed_ms:100, session_id:'uuid'})
  2. Component recebe e chama MasterAPI.Start() para recovery
- **Esperado:** Mensagem 'crashed after 100ms — recovering...' exibida, novo Start() tentado, novo sessionId gerado
- **Cobertura atual:** none

### MST-31 — MCP Tool: list_tasks sem filtro retorna todos
`P0` · `GO-INT` · 🔧recém-mudado
- **Pré:** MCP Server rodando, 3 tasks no DB em diferentes projetos
- **Passos:**
  1. Claude chama list_tasks {}
  2. Handler chama s.tasks.List(ctx, []string{})
- **Esperado:** Retorna JSON array com todas as 3 tasks, sem filtro
- **Cobertura atual:** internal/mcp/tools_test.go::TestTaskListAndGet

### MST-34 — MCP Tool: get_task retorna task por ID
`P0` · `GO-INT` · 🔧recém-mudado
- **Pré:** DB tem task ID='tsk-123'
- **Passos:**
  1. Claude chama get_task {task_id:'tsk-123'}
- **Esperado:** Retorna JSON com campos completos da task
- **Cobertura atual:** internal/mcp/tools_test.go::TestTaskListAndGet

### MST-36 — MCP Tool: create_task sem template começa em state=idea
`P0` · `GO-INT` · 🔧recém-mudado
- **Pré:** DB tem proj-A
- **Passos:**
  1. Claude chama create_task {project_id:'proj-A', title:'fix bug'}
  2. Handler chama s.tasks.Create() com template=nil
- **Esperado:** Task criada com state='idea', PermissionProfile=null ou default do catalog, branch=nil
- **Cobertura atual:** internal/mcp/tools_test.go::TestCreateTask

### MST-38 — MCP Tool: update_task transição válida idea→ready sucede
`P0` · `GO-INT` · 🔧recém-mudado
- **Pré:** Task ID tsk-1 em estado idea
- **Passos:**
  1. Claude chama update_task {task_id:'tsk-1', state:'ready'}
  2. Handler valida IsValidTransition('idea', 'ready')=true
- **Esperado:** Task atualizada para state='ready', evento task.updated emitido
- **Cobertura atual:** internal/mcp/tools_test.go::TestUpdateTask

### MST-41 — MCP Tool: discard_task move para discarded
`P0` · `GO-INT` · 🔧recém-mudado
- **Pré:** Task tsk-4 em estado idea ou ready ou qualquer não-terminal
- **Passos:**
  1. Claude chama discard_task {task_id:'tsk-4'}
  2. Handler chama Patch com state='discarded'
- **Esperado:** Task.state='discarded', IsTerminal('discarded')=true, cleanup funções chamadas
- **Cobertura atual:** internal/mcp/tools_test.go::TestDiscardTask

### MST-45 — MCP Auth middleware: Bearer token válido passa
`P0` · `GO-INT` · 🔧recém-mudado
- **Pré:** Server.Token() retorna 'sec-abc', request tem Authorization: Bearer sec-abc
- **Passos:**
  1. HTTP POST /api/mcp com Authorization header correto
- **Esperado:** Request passa para MCP handler, processa normalmente
- **Cobertura atual:** internal/mcp/auth_test.go

### MST-46 — MCP Auth middleware: Bearer token inválido rejeita
`P0` · `GO-INT` · 🔧recém-mudado
- **Pré:** Server.Token() retorna 'sec-abc', request tem Authorization: Bearer wrong-token
- **Passos:**
  1. HTTP POST /api/mcp com token incorreto
- **Esperado:** HTTP 401 Unauthorized retornado, nenhuma ferramenta executada
- **Cobertura atual:** internal/mcp/auth_test.go

### MST-48 — Master Round-trip: Start → Stop → Start reusa session_id
`P0` · `UNIT` · 🔧recém-mudado
- **Pré:** Nova DB vazia
- **Passos:**
  1. Chama MasterAPI.Start() → session_id_1
  2. Chama MasterAPI.Stop()
  3. Chama MasterAPI.Start() novamente → session_id_2
- **Esperado:** session_id_1 == session_id_2 (reutilizado), dois PIDs diferentes
- **Cobertura atual:** internal/core/master_test.go::TestMasterService_RoundTrip_PreservesSessionID

### MST-05 — Master Start reusa session_id depois de parada limpa
`P1` · `UNIT` · 🔧recém-mudado
- **Pré:** DB tem row com ClaudeSessionID="uuid-x", PID=nil (parado)
- **Passos:**
  1. Chama MasterAPI.Start()
- **Esperado:** session_id reutilizado="uuid-x", novo PID gerado, spawna novo processo
- **Cobertura atual:** internal/core/master_test.go::TestMasterService_Start_ExistingRow_ReusesSessionID

### MST-07 — Master Stop no-op se DB vazio
`P1` · `UNIT` · 🔧recém-mudado
- **Pré:** DB sem master_session row
- **Passos:**
  1. Chama MasterAPI.Stop()
- **Esperado:** Nenhum erro, nada acontece (no-op)
- **Cobertura atual:** internal/core/master_test.go::TestMasterService_Stop_NoRow_NoOp

### MST-09 — Master Resize atualiza dimensões PTY
`P1` · `E2E` · 🔧recém-mudado
- **Pré:** MasterSidebar montado, ResizeObserver ativo
- **Passos:**
  1. Redimensiona janela do navegador
  2. Valida que fit.fit() é chamado e Resize(rows, cols) é enviado
- **Esperado:** PTY recebe SIGWINCH, dimensões refletem novo tamanho da viewport
- **Cobertura atual:** none

### MST-11 — Master Watchdog: early exit (< 2s) deleta DB row
`P1` · `UNIT` · 🔧recém-mudado
- **Pré:** Processo morre rapidamente após spawn (crash)
- **Passos:**
  1. Injeta waitForProcessExit que retorna imediatamente
  2. Chama watchdog(sessionID, pid)
  3. Tenta Get(ctx) da DB
- **Esperado:** Erro ErrMasterSessionNotFound; row deleted; evento master.exit {early_exit:true}
- **Cobertura atual:** internal/core/master_test.go::TestMasterService_Watchdog_EarlyExit_DeletesRow

### MST-12 — Master Watchdog: long run (>= 2s) preserva session_id
`P1` · `UNIT` · 🔧recém-mudado
- **Pré:** Processo rodam >= 2s antes de sair
- **Passos:**
  1. Injeta waitForProcessExit que dorme 2100ms
  2. Chama watchdog(sessionID, pid)
  3. Lê DB
- **Esperado:** PID=nil, ClaudeSessionID preservado; evento master.exit {early_exit:false}
- **Cobertura atual:** internal/core/master_test.go::TestMasterService_Watchdog_LongRun_PreservesSessionID

### MST-15 — WriteMasterSettings: .mcp.json permissão 0600 (token seguro)
`P1` · `UNIT` · 🔧recém-mudado
- **Pré:** WriteMasterSettings completo
- **Passos:**
  1. Stat .mcp.json
  2. Valida Mode().Perm()
- **Esperado:** Mode = 0o600 (rw-------, não world-readable)
- **Cobertura atual:** internal/sandbox/settings_master_test.go::TestWriteMasterSettings_McpJsonMode0600

### MST-16 — WriteMasterSettings: cria diretório .claude/ se não existir
`P1` · `UNIT` · 🔧recém-mudado
- **Pré:** .claude não existe
- **Passos:**
  1. Chama WriteMasterSettings(cwd, url, token)
  2. Stat .claude
- **Esperado:** Diretório criado com sucesso
- **Cobertura atual:** internal/sandbox/settings_master_test.go::TestWriteMasterSettings_CreatesClaudeDir

### MST-17 — Terminal Clipboard: Ctrl+C copia seleção para clipboard
`P1` · `UNIT` · 🔧recém-mudado
- **Pré:** Texto selecionado no terminal (xterm), Ctrl+C pressionado
- **Passos:**
  1. handleTerminalKeyEvent recebe ev {type:keydown, ctrlKey:true, key:'c', shiftKey:false}
  2. ctx.hasSelection()=true, ctx.getSelection()=<text>
- **Esperado:** ctx.writeText(<text>) chamado, ctx.clearSelection() chamado, retorna false (preventDefault)
- **Cobertura atual:** none

### MST-18 — Terminal Clipboard: Ctrl+Shift+C copia e limpa seleção
`P1` · `UNIT` · 🔧recém-mudado
- **Pré:** Texto selecionado, Ctrl+Shift+C pressionado
- **Passos:**
  1. handleTerminalKeyEvent recebe ev {ctrlKey:true, shiftKey:true, key:'c'}
- **Esperado:** ctx.writeText(<text>) chamado, ctx.clearSelection() chamado, preventDefault retorna false
- **Cobertura atual:** none

### MST-19 — Terminal Clipboard: Shift+V cola texto do clipboard
`P1` · `UNIT` · 🔧recém-mudado
- **Pré:** Clipboard tem texto, Ctrl+Shift+V pressionado
- **Passos:**
  1. handleTerminalKeyEvent recebe ev {ctrlKey:true, shiftKey:true, key:'v'}
  2. ctx.readText() retorna Promise<'pasted text'>
- **Esperado:** ctx.paste('pasted text') chamado, preventDefault retorna false
- **Cobertura atual:** none

### MST-22 — QuickCommands: botão 'show doing' filtra por state=in_progress
`P1` · `E2E` · 🔧recém-mudado
- **Pré:** QuickCommands renderizado
- **Passos:**
  1. Clica 'show doing'
  2. Injeta 'j-arvis list_tasks state=in_progress'
- **Esperado:** Comando com filtro enviado ao PTY
- **Cobertura atual:** none

### MST-23 — MasterSidebar: xterm tema escuro renderiza corretamente
`P1` · `E2E` · 🔧recém-mudado
- **Pré:** MasterSidebar montado
- **Passos:**
  1. Valida Terminal({ fontSize: 13, fontFamily: 'monospace', theme: {...} })
  2. Verifica background='#030503', foreground='#d4e4d0', cursor='#ff10f0'
- **Esperado:** Terminal criado com tema fornecido
- **Cobertura atual:** none

### MST-24 — MasterHeader: botão copy-id copia sessionId ao clipboard
`P1` · `E2E` · 🔧recém-mudado
- **Pré:** MasterHeader montado, sessionId="abc-123"
- **Passos:**
  1. Clica ícone copy ao lado do sessionId
  2. handleCopyId() chama navigator.clipboard.writeText(sessionId)
- **Esperado:** sessionId copiado para clipboard
- **Cobertura atual:** none

### MST-25 — MasterFooter: status chip mostra 'connected' quando live=true
`P1` · `E2E` · 🔧recém-mudado
- **Pré:** MasterFooter com live=true, pid=1234
- **Passos:**
  1. Valida rendering
- **Esperado:** Chip exibe status connected, pid visível
- **Cobertura atual:** none

### MST-29 — MasterSidebar: evento master.exit com early_exit=false mostra erro final
`P1` · `E2E` · 🔧recém-mudado
- **Pré:** Master rodando > 2s, sai voluntariamente
- **Passos:**
  1. Backend emite EventsOn('master.exit', {early_exit:false, elapsed_ms:5000})
  2. setStatus('disconnected'), setSystemMsg(error)
- **Esperado:** Mensagem 'master exited (5000ms)' exibida, status=disconnected, sem tentativa de recovery
- **Cobertura atual:** none

### MST-30 — MasterSidebar: limpa observers e listeners no unmount
`P1` · `E2E` · 🔧recém-mudado
- **Pré:** MasterSidebar montado
- **Passos:**
  1. Desmonta component (navigate away ou close tab)
  2. Cleanup function executa
- **Esperado:** resizeObserver.disconnect() chamado, EventsOff('master.*') x3, MasterAPI.Stop() chamado, term.dispose()
- **Cobertura atual:** none

### MST-32 — MCP Tool: list_tasks filtra por project_id
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** DB tem 3 tasks: 2 em proj-A, 1 em proj-B
- **Passos:**
  1. Claude chama list_tasks {project_id:'proj-A'}
  2. Handler filtra por projectIDs=['proj-A']
- **Esperado:** Retorna 2 tasks de proj-A apenas
- **Cobertura atual:** internal/mcp/tools_test.go::TestTaskListFilterByProject

### MST-33 — MCP Tool: list_tasks filtra por state
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** DB tem tasks com estados: 1 idea, 2 in_progress, 1 done
- **Passos:**
  1. Claude chama list_tasks {state:'in_progress'}
  2. Handler filtra in-memory por estado
- **Esperado:** Retorna 2 tasks com state='in_progress'
- **Cobertura atual:** internal/mcp/tools_test.go::TestTaskListFilterByState

### MST-35 — MCP Tool: get_task task não encontrada retorna erro
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** DB não tem task ID='nonexistent'
- **Passos:**
  1. Claude chama get_task {task_id:'nonexistent'}
  2. Handler retorna errorResult('task not found: nonexistent')
- **Esperado:** Retorna erro JSON com IsError=true, mensagem legível
- **Cobertura atual:** internal/mcp/tools_test.go::TestGetTaskNotFound

### MST-37 — MCP Tool: create_task com template inválido retorna erro
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** Catalog não tem template 'invalid'
- **Passos:**
  1. Claude chama create_task {project_id:'p1', title:'t', template:'invalid'}
  2. Handler retorna errorResult('unknown template: invalid')
- **Esperado:** Erro com mensagem clara, IsError=true
- **Cobertura atual:** internal/mcp/tools_test.go::TestCreateTaskUnknownTemplate

### MST-39 — MCP Tool: update_task transição inválida done→idea falha
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** Task ID tsk-2 em estado done
- **Passos:**
  1. Claude chama update_task {task_id:'tsk-2', state:'idea'}
  2. IsValidTransition('done', 'idea')=false
- **Esperado:** Erro 'invalid state transition', IsError=true, task preservada em state=done
- **Cobertura atual:** none

### MST-40 — MCP Tool: update_task apenas título sem state transição
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** Task tsk-3 {title:'old', state:'idea'}
- **Passos:**
  1. Claude chama update_task {task_id:'tsk-3', title:'new title'}
  2. Handler chama UpdateFields, nenhuma transição
- **Esperado:** Task.title='new title', state preservado='idea', evento task.updated emitido
- **Cobertura atual:** internal/mcp/tools_test.go::TestUpdateTask

### MST-42 — MCP Tool: discard_task de task já terminal (done) falha
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** Task tsk-5 já em state=done
- **Passos:**
  1. Claude chama discard_task {task_id:'tsk-5'}
  2. IsValidTransition('done', 'discarded')=true (terminal→discarded permitido)
- **Esperado:** Task.state='discarded', sucede (done→discarded é válido)
- **Cobertura atual:** none

### MST-43 — MCP Tool: list_projects retorna todos com id, name, path
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** DB tem 2 projetos
- **Passos:**
  1. Claude chama list_projects {}
- **Esperado:** Retorna array [{id, name, path}, {...}]
- **Cobertura atual:** none

### MST-44 — MCP Tool: get_project retorna projeto por ID
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** DB tem proj-A
- **Passos:**
  1. Claude chama get_project {project_id:'proj-A'}
- **Esperado:** Retorna {id:'proj-A', name, path}
- **Cobertura atual:** none

### MST-47 — MCP Auth middleware: sem Authorization header rejeita
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** Request sem Authorization header
- **Passos:**
  1. HTTP POST /api/mcp
- **Esperado:** HTTP 401 retornado
- **Cobertura atual:** internal/mcp/auth_test.go

### MST-20 — Terminal Clipboard: Ctrl+C sem seleção não copia (pass-through)
`P2` · `UNIT` · 🔧recém-mudado
- **Pré:** Nenhum texto selecionado, Ctrl+C
- **Passos:**
  1. ctx.hasSelection()=false
- **Esperado:** ctx.writeText não chamado, retorna true (permite default behavior)
- **Cobertura atual:** none

### MST-49 — Master: portFromURL extrai port corretamente
`P2` · `UNIT` · 🔧recém-mudado
- **Pré:** URL válida http://127.0.0.1:8080
- **Passos:**
  1. Chama portFromURL('http://127.0.0.1:8080')
- **Esperado:** Retorna 8080
- **Cobertura atual:** none

### MST-50 — Master: portFromURL retorna 0 se URL inválida
`P2` · `UNIT` · 🔧recém-mudado
- **Pré:** URL malformed
- **Passos:**
  1. Chama portFromURL('invalid')
- **Esperado:** Retorna 0
- **Cobertura atual:** none

## Catalog

_Gerencia templates (frontend/backend/refactor/bugfix) com 3 perfis de permissão (yolo/default/read-only). Resolução de template no spawn com validação YAML, hint dinâmico no form NewTask, badges color-coded no TaskCard._


### CAT-01 — Catalog boot: versão correta e profiles existem
`P0` · `E2E` · 🔧recém-mudado
- **Pré:** Aplicação Wails iniciando com catalog.yml embedado
- **Passos:**
  1. 1. Inicializar app via Wails
  2. 2. Hook useCatalog executa getCatalog() contra CatalogAPI.Get()
  3. 3. Validar resposta contém version='1', fallback_permission_profile, permission_profiles array com 3 items, templates array com 4 items
- **Esperado:** Version '1' retornado; fallback_permission_profile='yolo'; 3 profiles (yolo/default/read-only) + 4 templates (frontend/backend/refactor/bugfix) em ordem alfabética
- **Cobertura atual:** api/catalog_test.go:TestCatalogAPIGetReturnsSortedView

### CAT-03 — Resolução template fallback: sem template selecionado
`P0` · `GO-INT` · 🔧recém-mudado
- **Pré:** Backend catalog.yml loaded; call TasksAPI.Create({project_id, title, template: nil})
- **Passos:**
  1. 1. Chamar api.createTask({project_id: 'p1', title: 'Test Task'})
  2. 2. Backend executa TasksService.Create com template vazio
  3. 3. Resolve('') retorna Resolved{ProfileName: 'yolo', ClaudeArgs: ['--dangerously-skip-permissions'], TemplateName: '', BranchPrefix: ''}
  4. 4. Persistir PermissionProfile='yolo' em store.Task
- **Esperado:** Task criada com permission_profile='yolo', template=null (ou empty string), sem branch_prefix aplicado
- **Cobertura atual:** internal/api/tasks_test.go:TestTasksAPI_Create_NoTemplate_UsesFallbackProfile

### CAT-04 — Resolução template known: backend → default profile
`P0` · `GO-INT` · 🔧recém-mudado
- **Pré:** Backend catalog.yml loaded; call TasksAPI.Create({project_id, title, template: 'backend'})
- **Passos:**
  1. 1. Chamar api.createTask({project_id: 'p1', title: 'API Refactor', template: 'backend'})
  2. 2. Backend executa Resolve('backend') → Resolved{TemplateName: 'backend', ProfileName: 'default', ClaudeArgs: [], BranchPrefix: 'feat-be/'}
  3. 3. Persistir permission_profile='default' e branch_prefix='feat-be/' em Task
- **Esperado:** Task criada com template='backend', permission_profile='default', branch_prefix derivado para próxima criação de worktree
- **Cobertura atual:** internal/api/tasks_test.go:TestTasksAPI_Create_KnownTemplate_PersistsBoth

### CAT-14 — Catalog validation na boot: version unsupported
`P0` · `UNIT`
- **Pré:** catalog.yml com version='2' (simulado durante testes unitários)
- **Passos:**
  1. 1. Chamar catalog.Load([]byte{version: '2', ...})
  2. 2. Unmarshal sucesso, populate Name fields
  3. 3. Check c.Version != '1' → adiciona erro 'unsupported version "2"' ao problems
- **Esperado:** Load retorna erro com substring 'unsupported version "2"'; processo recusa iniciar
- **Cobertura atual:** internal/catalog/catalog_test.go:TestLoadValidationCases — bad version

### CAT-15 — Catalog validation: fallback profile missing
`P0` · `UNIT`
- **Pré:** catalog.yml com fallback_permission_profile='ghost' não definido em permission_profiles
- **Passos:**
  1. 1. Chamar catalog.Load com YAML inválido
  2. 2. Check fallback_permission_profile existe em c.PermissionProfiles → não encontra
  3. 3. Adiciona 'fallback_permission_profile "ghost" not in permission_profiles' ao problems
- **Esperado:** Load retorna erro aggregado; MustLoad() fatals aplicação
- **Cobertura atual:** internal/catalog/catalog_test.go:TestLoadValidationCases — fallback missing

### CAT-16 — Catalog validation: template references unknown profile
`P0` · `UNIT`
- **Pré:** catalog.yml com templates.frontend.default_permission_profile='ghost' não em permission_profiles
- **Passos:**
  1. 1. Chamar catalog.Load
  2. 2. Para cada template, verificar se default_permission_profile existe
  3. 3. 'frontend' → 'ghost' não encontrada → add 'template "frontend" references unknown profile "ghost"'
- **Esperado:** Load retorna erro com esse substring; validação impede boot
- **Cobertura atual:** internal/catalog/catalog_test.go:TestLoadValidationCases — template references unknown profile

### CAT-17 — Catalog validation: branch_prefix pattern inválido
`P0` · `UNIT`
- **Pré:** catalog.yml com templates.bad.branch_prefix='Bad/' (uppercase, não match regex ^[a-z][a-z0-9-]*/$)
- **Passos:**
  1. 1. Chamar catalog.Load
  2. 2. Para cada template, verificar branchPrefixRe.MatchString(t.BranchPrefix)
  3. 3. 'Bad/' não match → add 'branch_prefix "Bad/" must match ^[a-z][a-z0-9-]*/$'
- **Esperado:** Load retorna erro; catalog recusado; processo não inicia
- **Cobertura atual:** internal/catalog/catalog_test.go:TestLoadValidationCases — branch_prefix bad

### CAT-02 — Template dropdown population em NewTaskSheet
`P1` · `E2E`
- **Pré:** NewTaskSheet aberto com catalog carregado e títulos: empty, 'Add dark mode', nenhum template selecionado
- **Passos:**
  1. 1. Abrir NewTaskSheet via '+new task' no header
  2. 2. Attendar useCatalog fetch resolve
  3. 3. Verificar select aria-label='template' tem options: '', 'backend', 'bugfix', 'frontend', 'refactor' (ordem alfabética)
  4. 4. Verificar cada option contém: name + ' — ' + description
- **Esperado:** Dropdown mostra todas 4 templates em ordem alfabética, cada uma com description (e.g., 'frontend — UI/UX, componentes, estilo')
- **Cobertura atual:** ui/src/components/drawers/NewTaskSheet.test.tsx:it('renders template dropdown with options from catalog', ...)

### CAT-05 — Template inválido → erro ErrTemplateUnknown
`P1` · `GO-INT`
- **Pré:** Backend catalog.yml loaded; attempt TasksAPI.Create({template: 'ghost-template'})
- **Passos:**
  1. 1. Chamar api.createTask({project_id: 'p1', title: 'X', template: 'ghost-template'})
  2. 2. Backend executa Resolve('ghost-template')
  3. 3. Template não existe em c.Templates map
  4. 4. Erro fmt.Errorf('%w: %s', ErrTemplateUnknown, 'ghost-template') propagado ao caller
- **Esperado:** ErrTemplateUnknown retornado para UI; criar task é abortado; TaskCard não criado
- **Cobertura atual:** internal/api/tasks_test.go:TestTasksAPI_Create_UnknownTemplate_Errors; internal/catalog/catalog_test.go:TestResolveUnknownTemplateErrors

### CAT-06 — Hint dinâmico: template + title válido sem branch override
`P1` · `E2E`
- **Pré:** NewTaskSheet aberto; title='' template=''; depois title → 'Add dark mode' → template → 'frontend'; branch field vazio
- **Passos:**
  1. 1. Digitar title='Add dark mode' no input aria-label='título'
  2. 2. Selecionar template='frontend' via dropdown
  3. 3. Verificar template está selecionado (selectedTemplate = catalog.templates.find(t => t.name === 'frontend'))
  4. 4. Verificar branch.trim() === '' (vazio)
  5. 5. Observar hint em p[aria-label='template-hint']
- **Esperado:** Hint exibe 'Branch será: feat-ui/add-dark-mode' (prefixo do template 'feat-ui/' + slug do título 'add-dark-mode')
- **Cobertura atual:** ui/src/components/drawers/NewTaskSheet.test.tsx:it('shows branch hint when template + title provided + no branch override', ...)

### CAT-07 — Hint dinâmico: branch override anula template prefix
`P1` · `E2E`
- **Pré:** NewTaskSheet com template='frontend' selecionado; digitar branch override 'my-custom'
- **Passos:**
  1. 1. Selecionar template='frontend'
  2. 2. Digitar título 'Add dark mode'
  3. 3. Clique em 'Avançado' para expandir details
  4. 4. Digitar input[aria-label='task-branch'] = 'my-custom'
  5. 5. Observar p[aria-label='template-hint']
- **Esperado:** Hint muda para 'Branch override — prefix do template ignorado'; não mostra 'feat-ui/...'
- **Cobertura atual:** ui/src/components/drawers/NewTaskSheet.test.tsx:it('shows override hint when template + branch typed', ...)

### CAT-09 — TaskCard template badge color-coded
`P1` · `E2E` · 🔧recém-mudado
- **Pré:** Task com template='frontend' criada e visível no kanban
- **Passos:**
  1. 1. Criar task com template='frontend' via NewTaskSheet
  2. 2. Task aparece no kanban
  3. 3. Localizar span[data-testid='template-badge'] com data-template-name='frontend'
  4. 4. Verificar inline-block child (color square) tem backgroundColor calculada via templateColor('frontend')
- **Esperado:** Badge exibe 'frontend' com marker square azul/ciano (var(--semantic-frontend)); tooltip mostra 'UI/UX, componentes, estilo' (description do catalog)
- **Cobertura atual:** ui/src/components/kanban/TaskCard.test.tsx:it.each([...]) — template color tests

### CAT-10 — TaskCard permission profile badge color
`P1` · `E2E` · 🔧recém-mudado
- **Pré:** Task com template='backend' (default profile) criada no kanban
- **Passos:**
  1. 1. Criar task com template='backend'; backend resolves → permission_profile='default'
  2. 2. Task aparece no kanban
  3. 3. Localizar span[data-testid='profile-badge'] com data-permission-profile='default'
  4. 4. Verificar data-profile-color='gray' (PROFILE_COLORS['default'])
- **Esperado:** Badge exibe 'default' com cor cinza; tooltip mostra description do profile ('Claude pergunta a cada tool — postura cuidadosa')
- **Cobertura atual:** ui/src/components/kanban/TaskCard.test.tsx profileColor tests

### CAT-11 — TaskCard yolo profile badge amarela
`P1` · `E2E` · 🔧recém-mudado
- **Pré:** Task com template='bugfix' (default profile yolo) ou sem template no kanban
- **Passos:**
  1. 1. Criar task com template='bugfix' ou sem template; resolve → permission_profile='yolo'
  2. 2. Task aparece no kanban com span[data-permission-profile='yolo']
  3. 3. Verificar PROFILE_COLORS['yolo'] = 'yellow'
- **Esperado:** Badge exibe 'yolo' com cor amarela; tooltip: 'Skip todos os prompts — modo dev rápido'
- **Cobertura atual:** ui/src/components/kanban/TaskCard.test.tsx:PROFILE_COLORS

### CAT-18 — Catalog validation: múltiplos erros agregados
`P1` · `UNIT`
- **Pré:** catalog.yml com version='9' AND fallback_permission_profile='ghost' AND empty permission_profiles
- **Passos:**
  1. 1. Chamar catalog.Load
  2. 2. Validação coleta ALL problemas: unsupported version, fallback missing
  3. 3. Return error com strings.Join(problems, '; ')
- **Esperado:** Erro contém ';' separador; ambos os problemas listados; facilita debug
- **Cobertura atual:** internal/catalog/catalog_test.go:TestLoadValidationCases — multiple errors aggregated

### CAT-19 — ResolveProfile: profile conhecido retorna ClaudeArgs
`P1` · `UNIT`
- **Pré:** Backend catalog.yml loaded; call c.ResolveProfile('yolo')
- **Passos:**
  1. 1. Chamar catalog.ResolveProfile('yolo')
  2. 2. Lookup c.PermissionProfiles['yolo']
  3. 3. Retorna PermissionProfile{Name: 'yolo', Description: '...', ClaudeArgs: ['--dangerously-skip-permissions']}
- **Esperado:** ClaudeArgs array não nil (pode estar vazio para 'default'), contém flags esperadas para 'yolo'
- **Cobertura atual:** internal/catalog/catalog_test.go:TestResolveProfileKnownReturnsClaudeArgs

### CAT-20 — ResolveProfile: profile desconhecido retorna ErrProfileMissing
`P1` · `UNIT`
- **Pré:** Backend call c.ResolveProfile('ghost-profile')
- **Passos:**
  1. 1. Lookup c.PermissionProfiles['ghost-profile'] → não existe
  2. 2. Retorna error fmt.Errorf('%w: %s', ErrProfileMissing, 'ghost-profile')
- **Esperado:** ErrProfileMissing error; caller processa como erro de validação
- **Cobertura atual:** internal/catalog/catalog_test.go:TestResolveProfileMissingErrors

### CAT-21 — Catalog API Get() retorna sorted view
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** Backend NewCatalogAPI(catalog.MustLoad()).Get()
- **Passos:**
  1. 1. Chamar a.Get()
  2. 2. Itera PermissionProfiles map, cria array, sort.Slice by Name
  3. 3. Itera Templates map, cria array, sort.Slice by Name
  4. 4. Retorna CatalogView com ambas as arrays sorted
- **Esperado:** PermissionProfiles array: ['default', 'read-only', 'yolo']; Templates: ['backend', 'bugfix', 'frontend', 'refactor']; determinístico para UI
- **Cobertura atual:** internal/api/catalog_test.go:TestCatalogAPIGetReturnsSortedView

### CAT-22 — useCatalog hook: fetch → cache com staleTime Infinity
`P1` · `UNIT`
- **Pré:** React component com useCatalog(); QueryClient com cache
- **Passos:**
  1. 1. First mount: renderHook(() => useCatalog(), {wrapper: QueryClientProvider})
  2. 2. Hook chama api.getCatalog() → fetch
  3. 3. Second mount: renderHook(() => useCatalog(), {wrapper: same QueryClientProvider})
  4. 4. Verificar spy call count === 1 (não refetch)
- **Esperado:** staleTime: Infinity → cache never expires; segunda renderização reutiliza resultado sem network
- **Cobertura atual:** ui/src/hooks/useCatalog.test.tsx:it('fetches catalog and caches it', ...)

### CAT-23 — Kanban: task sem template não exibe badge
`P1` · `E2E`
- **Pré:** Task criada sem template (template=null); kanban renderizado
- **Passos:**
  1. 1. TaskCard recebe task com template=null
  2. 2. {task.template && (...)} condicional não renderiza
  3. 3. Verificar não há span[data-testid='template-badge']
- **Esperado:** Nenhuma badge de template no card; apenas permission_profile (yolo) se houver
- **Cobertura atual:** ui/src/components/kanban/TaskCard.test.tsx:it('omits badges when template/permission_profile are null', ...)

### CAT-24 — Form submit com template inclui no payload
`P1` · `E2E`
- **Pré:** NewTaskSheet com template='backend' selecionado; título preenchido
- **Passos:**
  1. 1. Selecionar template='backend'
  2. 2. Preencher title='API Service'
  3. 3. Clicar submit
  4. 4. create.mutate({project_id, title, description, template: 'backend', ...}) executado
- **Esperado:** api.createTask recebe {template: 'backend'} no payload; backend persiste template + resolve profile
- **Cobertura atual:** ui/src/components/drawers/NewTaskSheet.test.tsx:it('submit includes template in payload when selected', ...)

### CAT-25 — Form submit sem template omite do payload
`P1` · `E2E`
- **Pré:** NewTaskSheet com template='(nenhum)' (default value); título preenchido
- **Passos:**
  1. 1. Deixar template vazio (default option selecionado)
  2. 2. Preencher title='Quick Task'
  3. 3. Clicar submit
  4. 4. template && {template} na spread → template não incluído
- **Esperado:** api.createTask recebe payload SEM template field; backend usa fallback profile 'yolo'
- **Cobertura atual:** ui/src/components/drawers/NewTaskSheet.test.tsx:it('submit omits template when not selected', ...)

### CAT-08 — Hint dinâmico: título inválido para slug mostra fallback
`P2` · `E2E`
- **Pré:** NewTaskSheet; template='frontend' selecionado; título = '!!!' (só punctuation)
- **Passos:**
  1. 1. Selecionar template='frontend'
  2. 2. Digitar título='!!!'
  3. 3. slugifyForBranch('!!!') throws InvalidBranchSlugError
  4. 4. Observar hint
- **Esperado:** Hint exibe 'Branch será: feat-ui/<slug-do-título>' sem expandir slug (fallback text)
- **Cobertura atual:** none

### CAT-12 — TaskCard read-only profile badge verde
`P2` · `E2E` · 🔧recém-mudado
- **Pré:** Task com permission_profile='read-only' (não há template padrão; edge case de edição manual via backend)
- **Passos:**
  1. 1. Persistir task com explicit permission_profile='read-only' (via database update ou API patch)
  2. 2. Task carrega no kanban
  3. 3. Localizar span[data-permission-profile='read-only']
  4. 4. Verificar PROFILE_COLORS['read-only'] = 'green'
- **Esperado:** Badge exibe 'read-only' com cor verde; tooltip: 'Plan mode + tools de leitura — exploração/code review'
- **Cobertura atual:** none

### CAT-13 — Badge fallback color: unknown template/profile
`P2` · `E2E`
- **Pré:** Task com template='custom' ou permission_profile='future-profile' não no TEMPLATE_COLORS/PROFILE_COLORS map
- **Passos:**
  1. 1. Persistir task com template='custom' (edge case de upgrade com novos templates)
  2. 2. Task carrega no kanban
  3. 3. Verificar templateColor('custom') → TEMPLATE_COLORS['custom'] ?? 'var(--text-subtle)' (fallback)
- **Esperado:** Badge exibe 'custom' com cor fallback text-subtle; não quebra renderização
- **Cobertura atual:** ui/src/components/kanban/TaskCard.test.tsx:it('applies gray color fallback for unknown profiles', ...)

## UI Shell / HUD / Health / Keyboard Shortcuts

_Camada de apresentação do shell J-arvis: AppShell layout (HudTopBar, AppHeader, StatusBar, ErrorBanner), métricas de sistema (CPU/mem/RTT/uptime/alerts), atalhos de teclado global ([/], [p], [n], [r]), e estado WebSocket (connected/reconnecting/offline/connecting)._


### UI-01 — HudTopBar renderiza todas as 5 métricas quando saúde está disponível
`P0` · `UNIT`
- **Pré:** useSystemHealth retorna data completo (cpu, mem, uptime, alerts)
- **Passos:**
  1. Montar HudTopBar com wsRtt={10}
  2. Verificar que os 5 data-testid estão presentes: hud-metric-cpu, hud-metric-mem, hud-metric-rtt, hud-metric-uptime, hud-metric-alert
- **Esperado:** Todos os 5 segmentos visíveis com valores formatados corretamente (e.g., '12.4%', '2.0G/32.0G', '10ms', '4h33m', '0')
- **Cobertura atual:** ui/src/components/hud/HudTopBar.test.tsx:56-63

### UI-02 — HudTopBar exibe '--' para RTT quando wsRtt é null
`P0` · `UNIT`
- **Pré:** wsRtt={null}, useSystemHealth retorna data válido
- **Passos:**
  1. Montar HudTopBar com wsRtt={null}
  2. Procurar elemento com data-testid='hud-metric-rtt'
- **Esperado:** Métrica RTT exibe '—' (em-dash Unicode), não 'null'
- **Cobertura atual:** ui/src/components/hud/HudTopBar.test.tsx:43-48

### UI-03 — HudMetric com tone='hot' aplica classes de alerta magenta + glow
`P0` · `UNIT`
- **Pré:** HudMetric recebe tone='hot' (usado quando alerts > 0)
- **Passos:**
  1. Montar HudMetric com label='alert', value={3}, tone='hot'
  2. Inspecionar elemento de valor (span text-accent-attn)
- **Esperado:** Valor tem classe 'text-accent-attn' e 'drop-shadow-[0_0_6px_rgba(255,16,240,0.6)]' (glow magenta)
- **Cobertura atual:** ui/src/components/hud/HudMetric.test.tsx:24-29

### UI-05 — StatusBar renderiza 8 segmentos: state/ws/mcp/alerts/mode/profile/git/v
`P0` · `UNIT`
- **Pré:** wsConnectionStore state='connected', health data com alerts=0
- **Passos:**
  1. Montar StatusBar
  2. Procurar pelos 8 data-testid: status-seg-state, status-seg-ws, status-seg-mcp, status-seg-alerts, status-seg-mode, status-seg-profile, status-seg-git, status-seg-v
- **Esperado:** Todos os 8 segmentos presentes com valores: 'online'|'offline', 'connected'|'reconnecting'|'offline'|'connecting', 'ok', '0'|N, 'ops', '—', 'main', 'v0.0.1'
- **Cobertura atual:** ui/src/components/status/StatusBar.test.tsx:39-45

### UI-06 — StatusBar segmento 'state' mostra 'online' quando ws connected, 'offline' caso contrário
`P0` · `UNIT`
- **Pré:** wsConnectionStore controlável; testará 3 transições: connected → reconnecting → offline
- **Passos:**
  1. Montar StatusBar, mock ws state='connected'
  2. Verificar que status-seg-state mostra 'online' com tone default (green)
  3. Transicionar para state='reconnecting'
  4. Verificar que status-seg-state mostra 'offline' com tone error (magenta)
  5. Transicionar para state='offline'
  6. Verificar que status-seg-state ainda mostra 'offline' com tone error
- **Esperado:** Label 'state' sempre presente; value muda entre 'online'↔'offline'; tone varia (default→error)
- **Cobertura atual:** ui/src/components/status/StatusBar.test.tsx:47-80

### UI-07 — StatusBar segmento 'ws' mostra estado exato e tones corretos (default/warn/error)
`P0` · `UNIT`
- **Pré:** useWsConnectionStore pode ser mockado com cada WsState
- **Passos:**
  1. Montar StatusBar 4x com states: 'connected', 'reconnecting', 'offline', 'connecting'
  2. Para cada estado, verificar tone do status-seg-ws
- **Esperado:** Estado 'connected' → tone default (green); 'reconnecting' → tone warn (amarelo); 'offline' → tone error (magenta); 'connecting' → tone default
- **Cobertura atual:** ui/src/components/status/StatusBar.test.tsx:82-101

### UI-08 — StatusBar segmento 'alerts' muda de tone quando count > 0
`P0` · `UNIT`
- **Pré:** useSystemHealth retorna data com active_alerts_count mutável
- **Passos:**
  1. Montar StatusBar com alerts=0, verificar tone default
  2. Mudar mock para alerts=1
  3. Remontagem ou re-render, verificar que tone muda para error
- **Esperado:** alerts=0 → tone default (green), valor '0'; alerts>0 → tone error (magenta), valor com número correto
- **Cobertura atual:** ui/src/components/status/StatusBar.test.tsx:103-122

### UI-10 — ErrorBanner não renderiza quando ws state é 'connected'
`P0` · `UNIT`
- **Pré:** useWsConnectionStore state='connected'
- **Passos:**
  1. Montar ErrorBanner
  2. Verificar DOM
- **Esperado:** Container está vazio (nenhum role='alert')
- **Cobertura atual:** ui/src/components/status/ErrorBanner.test.tsx:22-26

### UI-11 — ErrorBanner mostra 'Connection lost — reconnecting...' com tone warn quando reconnecting
`P0` · `UNIT`
- **Pré:** useWsConnectionStore state='reconnecting'
- **Passos:**
  1. Montar ErrorBanner
  2. Procurar role='alert'
- **Esperado:** Banner visível com mensagem exata 'Connection lost — reconnecting...' e classe contendo 'semantic-warn' (fundo/texto amarelo)
- **Cobertura atual:** ui/src/components/status/ErrorBanner.test.tsx:28-35

### UI-12 — ErrorBanner mostra 'Offline — backend unreachable' com tone error quando offline
`P0` · `UNIT`
- **Pré:** useWsConnectionStore state='offline'
- **Passos:**
  1. Montar ErrorBanner
  2. Procurar role='alert'
- **Esperado:** Banner visível com mensagem 'Offline — backend unreachable' e classe contendo 'sem-error' (fundo/texto magenta)
- **Cobertura atual:** ui/src/components/status/ErrorBanner.test.tsx:37-44

### UI-15 — AppHeader renderiza brand + 4 botões + contadores de projetos/tarefas/ativas
`P0` · `UNIT`
- **Pré:** AppHeader montado com projectsCount=3, tasksCount=12, activeCount=2
- **Passos:**
  1. Montar AppHeader com props padrão
  2. Procurar: BrandMark (j-arvis), botões filter/projects/run/new task, e textos '3', '12', '2'
- **Esperado:** Todos os 7 elementos visíveis com conteúdo correto
- **Cobertura atual:** ui/src/components/header/AppHeader.test.tsx:17-56

### UI-17 — AppHeader teclado [/] dispara onFilter callback
`P0` · `UNIT`
- **Pré:** AppHeader com onFilter definido
- **Passos:**
  1. Montar AppHeader com vi.fn() onFilter
  2. Disparar KeyboardEvent 'keydown' com key='/'
  3. Verificar chamadas
- **Esperado:** onFilter foi chamado exatamente 1x
- **Cobertura atual:** ui/src/components/header/AppHeader.test.tsx:63-68

### UI-18 — AppHeader teclado [p] dispara onToggleProjects callback
`P0` · `UNIT`
- **Pré:** AppHeader com onToggleProjects definido
- **Passos:**
  1. Montar AppHeader com vi.fn() onToggleProjects
  2. Disparar KeyboardEvent 'keydown' com key='p' (case-insensitive)
  3. Verificar chamadas
- **Esperado:** onToggleProjects foi chamado exatamente 1x
- **Cobertura atual:** ui/src/components/header/AppHeader.test.tsx:70-75

### UI-19 — AppHeader teclado [n] dispara onNewTask callback
`P0` · `UNIT`
- **Pré:** AppHeader com onNewTask definido
- **Passos:**
  1. Montar AppHeader com vi.fn() onNewTask
  2. Disparar KeyboardEvent 'keydown' com key='n'
  3. Verificar chamadas
- **Esperado:** onNewTask foi chamado exatamente 1x
- **Cobertura atual:** ui/src/components/header/AppHeader.test.tsx:77-82

### UI-21 — AppHeader botão click filter dispara onFilter
`P0` · `UNIT`
- **Pré:** AppHeader com onFilter, vi.fn()
- **Passos:**
  1. Montar AppHeader
  2. userEvent.click no botão 'filter'
  3. Verificar chamadas
- **Esperado:** onFilter chamado 1x
- **Cobertura atual:** ui/src/components/header/AppHeader.test.tsx:89-94

### UI-22 — AppHeader botão click projects dispara onToggleProjects
`P0` · `UNIT`
- **Pré:** AppHeader com onToggleProjects, vi.fn()
- **Passos:**
  1. Montar AppHeader
  2. userEvent.click no botão 'projects'
  3. Verificar chamadas
- **Esperado:** onToggleProjects chamado 1x
- **Cobertura atual:** ui/src/components/header/AppHeader.test.tsx:96-101

### UI-23 — AppHeader botão click 'new task' dispara onNewTask
`P0` · `UNIT`
- **Pré:** AppHeader com onNewTask, vi.fn()
- **Passos:**
  1. Montar AppHeader
  2. userEvent.click no botão 'new task'
  3. Verificar chamadas
- **Esperado:** onNewTask chamado 1x
- **Cobertura atual:** ui/src/components/header/AppHeader.test.tsx:103-108

### UI-27 — useKeyboardShortcut ignora eventos em input/textarea/contenteditable
`P0` · `UNIT`
- **Pré:** Hook registrado, input/textarea/contenteditable no DOM
- **Passos:**
  1. Montar input/textarea/contenteditable no DOM
  2. renderHook useKeyboardShortcut
  3. Disparar keydown a partir do elemento
  4. Verificar chamadas
- **Esperado:** Handler nunca dispara (proteção contra atalhos em campos de texto)
- **Cobertura atual:** ui/src/hooks/useKeyboardShortcut.test.tsx:28-57

### UI-31 — useWebSocketRTT envia ping a cada 1000ms quando ws está OPEN
`P0` · `UNIT`
- **Pré:** FakeWS com readyState=OPEN
- **Passos:**
  1. renderHook com FakeWS em OPEN
  2. useFakeTimers, advanceTimersByTime(1000)
  3. Verificar ws.sent length e estrutura
- **Esperado:** ws.sent contém JSON {type:'ping', ts: number} após 1s
- **Cobertura atual:** ui/src/hooks/useWebSocketRTT.test.tsx:18-30

### UI-32 — useWebSocketRTT calcula RTT correto após pong matching
`P0` · `UNIT`
- **Pré:** FakeWS em OPEN, ping sent, pong received com ts correto
- **Passos:**
  1. renderHook, fakeTimers, enviar ping
  2. Simular pong com msg.ts === enviado ts
  3. Verificar result.current
- **Esperado:** result.current é um número >= 0, representando ms entre ping→pong
- **Cobertura atual:** ui/src/hooks/useWebSocketRTT.test.tsx:18-30

### UI-36 — AppShell renderiza árvore correta: HudTopBar → ErrorBanner → AppHeader → main → StatusBar
`P0` · `UNIT`
- **Pré:** AppShell com children='content', mocks internos
- **Passos:**
  1. Montar AppShell com props padrão
  2. Procurar: mock-hud-top-bar (topo), error-banner, mock-app-header, main com children, mock-status-bar (rodapé)
- **Esperado:** Ordem visual: HudTopBar→ErrorBanner→AppHeader→main(content)→StatusBar; hierarquia correta
- **Cobertura atual:** ui/src/app/AppShell.test.tsx:44-101

### UI-37 — AppShell passa projectsCount/tasksCount/activeCount para AppHeader
`P0` · `UNIT`
- **Pré:** AppShell com projectsCount=5, tasksCount=20, activeCount=7
- **Passos:**
  1. Montar AppShell
  2. Verificar conteúdo mock-app-header
- **Esperado:** Mock mostra '5/20/7'
- **Cobertura atual:** ui/src/app/AppShell.test.tsx:74-81

### UI-38 — AppShell passa wsRtt para HudTopBar
`P0` · `UNIT`
- **Pré:** AppShell com wsRtt={42}
- **Passos:**
  1. Montar AppShell
  2. Verificar conteúdo mock-hud-top-bar
- **Esperado:** Mock mostra '42'
- **Cobertura atual:** ui/src/app/AppShell.test.tsx:69-72

### UI-41 — Transição WebSocket connected → reconnecting atualiza UI em tempo real (e2e-playwright)
`P0` · `E2E` · 🔧recém-mudado
- **Pré:** App rodando, WebSocket mockável via test harness
- **Passos:**
  1. Abrir app via openApp(page)
  2. Esperar por elemento 'new task' (prova shell carregado)
  3. Simular transição do store ws state para 'reconnecting'
  4. Verificar ErrorBanner apareceu com mensagem 'Connection lost'
  5. Verificar StatusBar.ws-seg mudou para 'reconnecting' com tone warn
  6. Verificar StatusBar.state-seg mudou para 'offline' com tone error
- **Esperado:** UI atualiza em <200ms para refletir reconexão, banners e tons corretos
- **Cobertura atual:** none

### UI-42 — Transição WebSocket offline → connected fecha ErrorBanner (e2e-playwright)
`P0` · `E2E` · 🔧recém-mudado
- **Pré:** ErrorBanner visível (state='offline')
- **Passos:**
  1. Estar com state='offline', ErrorBanner visível
  2. Simular transição para 'connected'
  3. Verificar que ErrorBanner desapareceu
  4. Verificar StatusBar.state-seg agora mostra 'online' com tone default
- **Esperado:** Banner removido do DOM, status refrescado
- **Cobertura atual:** none

### UI-43 — Tecla [/] no teclado global abre filter (sem estar em input) — e2e
`P0` · `E2E` · 🔧recém-mudado
- **Pré:** App rodando, AppHeader com onFilter wired
- **Passos:**
  1. Abrir app
  2. Pressionar tecla [/] no teclado
  3. Verificar se drawer de filtro abriu (deve haver nova sheet/dialog visível)
- **Esperado:** Drawer aparece ou callback disparado (comportamento depende de App.tsx)
- **Cobertura atual:** none

### UI-44 — Tecla [p] abre Projects drawer — e2e
`P0` · `E2E` · 🔧recém-mudado
- **Pré:** App rodando
- **Passos:**
  1. Abrir app
  2. Pressionar tecla [p]
  3. Verificar se Projects drawer abriu
- **Esperado:** Drawer Projects visível ou comportamento esperado
- **Cobertura atual:** ui/e2e/smoke.spec.ts:10-14 (click via botão, não teclado)

### UI-45 — Tecla [n] abre NewTask sheet — e2e
`P0` · `E2E` · 🔧recém-mudado
- **Pré:** App rodando
- **Passos:**
  1. Abrir app
  2. Pressionar tecla [n]
  3. Verificar se NewTask sheet abriu
- **Esperado:** Sheet NewTask visível
- **Cobertura atual:** ui/e2e/smoke.spec.ts:29-31 (click via botão)

### UI-54 — Quando alerts > 0, HudTopBar alert-metric tem drop-shadow glow + tone hot
`P0` · `UNIT`
- **Pré:** useSystemHealth retorna active_alerts_count=3
- **Passos:**
  1. Montar HudTopBar com mock alerts=3
  2. Procurar hud-metric-alert
- **Esperado:** Value span tem 'text-accent-attn' (magenta) e glow drop-shadow
- **Cobertura atual:** ui/src/components/hud/HudTopBar.test.tsx:82-90

### UI-55 — Quando alerts=0, HudTopBar alert-metric usa tone default (verde)
`P0` · `UNIT`
- **Pré:** useSystemHealth retorna active_alerts_count=0
- **Passos:**
  1. Montar HudTopBar com alerts=0
  2. Procurar hud-metric-alert
- **Esperado:** Value span tem 'text-accent-primary' (verde), sem glow
- **Cobertura atual:** ui/src/components/hud/HudTopBar.test.tsx:92-98

### UI-04 — HudTopBar esconde métricas cpu/mem/uptime/alert quando saúde carrega (undefined)
`P1` · `UNIT`
- **Pré:** useSystemHealth retorna {data: undefined} (estado loading)
- **Passos:**
  1. Montar HudTopBar com wsRtt={10}, mock useSystemHealth com data=undefined
  2. Procurar por data-testid='hud-metric-cpu', 'hud-metric-mem', 'hud-metric-uptime', 'hud-metric-alert'
- **Esperado:** Nenhum desses 4 elementos visível; OPER badge, titulo, env, e rtt continuam visíveis
- **Cobertura atual:** ui/src/components/hud/HudTopBar.test.tsx:100-111

### UI-09 — StatusBar segmento 'alerts' reseta para '0' quando health data é undefined
`P1` · `UNIT`
- **Pré:** useSystemHealth retorna {data: undefined}
- **Passos:**
  1. Montar StatusBar com mock health data=undefined
  2. Procurar status-seg-alerts
- **Esperado:** Segmento alerts mostra '0' (default ?? 0), não erro
- **Cobertura atual:** ui/src/components/status/StatusBar.test.tsx:135-140

### UI-13 — ErrorBanner mostra 'Connecting...' durante estado 'connecting'
`P1` · `UNIT`
- **Pré:** useWsConnectionStore state='connecting' (estado inicial)
- **Passos:**
  1. Montar ErrorBanner
  2. Procurar role='alert'
- **Esperado:** Banner visível com mensagem 'Connecting...' e tone warn (esperado transição inicial)
- **Cobertura atual:** ui/src/components/status/ErrorBanner.test.tsx:46-52

### UI-14 — ErrorBanner tem role='alert' para acessibilidade (ARIA live region)
`P1` · `UNIT`
- **Pré:** ErrorBanner renderizado (qualquer estado ≠ connected)
- **Passos:**
  1. Montar ErrorBanner com state='offline'
  2. Procurar por role='alert'
- **Esperado:** Elemento com role='alert' encontrado (anunciado via screen readers)
- **Cobertura atual:** ui/src/components/status/ErrorBanner.test.tsx:54-58

### UI-16 — AppHeader botão 'run' está disabled (F9+1 placeholder)
`P1` · `UNIT`
- **Pré:** AppHeader montado
- **Passos:**
  1. Procurar role='button' com nome /run/i
  2. Verificar atributo disabled
- **Esperado:** Botão existe com disabled=true, title='F9+1'
- **Cobertura atual:** ui/src/components/header/AppHeader.test.tsx:58-61

### UI-20 — AppHeader teclado [r] está registrado mas não faz nada (no-op)
`P1` · `UNIT`
- **Pré:** AppHeader montado
- **Passos:**
  1. Disparar KeyboardEvent com key='r'
  2. Verificar se há erro ou comportamento inesperado
- **Esperado:** Nenhum erro, nenhuma ação disparada (placeholder futuro para F9+1)
- **Cobertura atual:** ui/src/components/header/AppHeader.test.tsx:84-87

### UI-24 — AppHeader botão 'run' disabled não dispara handlers ao click
`P1` · `UNIT`
- **Pré:** AppHeader com handlers mocked
- **Passos:**
  1. Montar AppHeader
  2. userEvent.click no botão 'run' (disabled)
  3. Verificar se nenhum handler foi chamado
- **Esperado:** Nenhum callback disparado (browser ignora click em disabled)
- **Cobertura atual:** ui/src/components/header/AppHeader.test.tsx:110-116

### UI-25 — useKeyboardShortcut respeita modificadores (meta/ctrl/shift/alt) obrigatórios
`P1` · `UNIT`
- **Pré:** Hook registrado com opts={ctrl: true}
- **Passos:**
  1. renderHook useKeyboardShortcut com handler vi.fn() e opts={ctrl: true}
  2. Disparar keydown com key='k' SEM ctrl
  3. Disparar keydown com key='k' COM ctrlKey=true
  4. Verificar chamadas
- **Esperado:** Primeira dispara 0x, segunda dispara 1x exatamente
- **Cobertura atual:** ui/src/hooks/useKeyboardShortcut.test.tsx:59-75

### UI-26 — useKeyboardShortcut rejeita se modificador extra foi pressionado acidentalmente
`P1` · `UNIT`
- **Pré:** Hook sem modificadores (opts={})
- **Passos:**
  1. renderHook useKeyboardShortcut com key='n', handler vi.fn(), opts={} vazio
  2. Disparar keydown com key='n' E shiftKey=true
  3. Verificar chamadas
- **Esperado:** Handler não dispara (rejeita quando extra modifier present)
- **Cobertura atual:** ui/src/hooks/useKeyboardShortcut.test.tsx:93-98

### UI-28 — useKeyboardShortcut é case-insensitive para key matching
`P1` · `UNIT`
- **Pré:** Hook registrado com key='N'
- **Passos:**
  1. renderHook useKeyboardShortcut com key='N'
  2. Disparar keydown com key='n'
  3. Verificar chamadas
- **Esperado:** Handler dispara (uppercase key matches lowercase event)
- **Cobertura atual:** ui/src/hooks/useKeyboardShortcut.test.tsx:14-19

### UI-29 — useKeyboardShortcut remove listener ao desmontar
`P1` · `UNIT`
- **Pré:** Hook renderizado
- **Passos:**
  1. renderHook useKeyboardShortcut
  2. unmount()
  3. Disparar keydown
  4. Verificar chamadas
- **Esperado:** Handler não dispara após unmount
- **Cobertura atual:** ui/src/hooks/useKeyboardShortcut.test.tsx:100-106

### UI-30 — useWebSocketRTT retorna null quando ws=null
`P1` · `UNIT`
- **Pré:** Hook invocado com ws={null}
- **Passos:**
  1. renderHook useWebSocketRTT com ws=null
  2. Verificar result.current
- **Esperado:** result.current === null
- **Cobertura atual:** ui/src/hooks/useWebSocketRTT.test.tsx:32-35

### UI-33 — useWebSocketRTT ignora pong com ts desalinhado (proteção contra reordenação)
`P1` · `UNIT`
- **Pré:** Hook com ping pendente, pong recebido com ts ≠ inflightRef
- **Passos:**
  1. renderHook, fakeTimers, enviar ping (ts=X)
  2. Simular pong com ts=9999999 (diferente)
  3. Verificar result.current
- **Esperado:** result.current permanece null (ignorado)
- **Cobertura atual:** ui/src/hooks/useWebSocketRTT.test.tsx:49-60

### UI-34 — useWebSocketRTT ignora JSON inválido
`P1` · `UNIT`
- **Pré:** Hook rodando, ws recebe dado não-JSON
- **Passos:**
  1. renderHook, fakeTimers, enviar ping
  2. Simular message com data='not-valid-json'
  3. Verificar result.current e se há erro
- **Esperado:** Nenhum erro lançado, result.current permanece null
- **Cobertura atual:** ui/src/hooks/useWebSocketRTT.test.tsx:37-47

### UI-35 — useWebSocketRTT não envia ping quando readyState ≠ OPEN
`P1` · `UNIT`
- **Pré:** FakeWS com readyState=CLOSED
- **Passos:**
  1. renderHook com FakeWS readyState=CLOSED
  2. fakeTimers, advanceTimersByTime(1000)
  3. Verificar ws.sent
- **Esperado:** ws.sent.length === 0 (nada enviado)
- **Cobertura atual:** ui/src/hooks/useWebSocketRTT.test.tsx:62-70

### UI-39 — AppShell usa h-screen para fixar StatusBar na janela (viewport height)
`P1` · `UNIT`
- **Pré:** AppShell estrutura CSS (Tailwind)
- **Passos:**
  1. Montar AppShell
  2. Inspecionar root div className
- **Esperado:** className contém classe 'h-screen' (anchor StatusBar no bottom do viewport)
- **Cobertura atual:** ui/src/app/AppShell.test.tsx:93-101

### UI-46 — HudTopBar formato de CPU: mostra 2 casas decimais máximo (e.g., '12.4%')
`P1` · `UNIT`
- **Pré:** useSystemHealth retorna cpu_pct=12.456
- **Passos:**
  1. Montar HudTopBar com mock health.cpu_pct=12.456
  2. Procurar hud-metric-cpu
- **Esperado:** Valor mostrado como '12.5%' (toFixed(1), não 12.456%)
- **Cobertura atual:** ui/src/components/hud/HudTopBar.test.tsx:65-68

### UI-47 — HudTopBar formato de memória: converte bytes para B/K/M/G humanizado
`P1` · `UNIT`
- **Pré:** useSystemHealth com vários valores de bytes
- **Passos:**
  1. Montar com mem_used_bytes=2147483648 (2GB), mem_total_bytes=34359738368 (32GB)
  2. Procurar hud-metric-mem
- **Esperado:** Mostra '2.0G/32.0G', não '2147483648/34359738368'
- **Cobertura atual:** ui/src/components/hud/HudTopBar.test.tsx:70-74

### UI-48 — HudTopBar formato de uptime: hh mm (horas + minutos zerados)
`P1` · `UNIT`
- **Pré:** useSystemHealth com uptime_seconds=16380 (4h33m)
- **Passos:**
  1. Montar com uptime_seconds=16380
  2. Procurar hud-metric-uptime
- **Esperado:** Mostra '4h33m' (não '4:33' ou '273 min')
- **Cobertura atual:** ui/src/components/hud/HudTopBar.test.tsx:76-80

### UI-50 — StatusSeg renderiza label + value com spacing correto
`P1` · `UNIT`
- **Pré:** StatusSeg montado
- **Passos:**
  1. Montar StatusSeg label='mode', value='ops'
  2. Verificar estrutura inline-flex
- **Esperado:** label 'mode' e value 'ops' ambos presentes, separados com gap-1
- **Cobertura atual:** ui/src/components/status/StatusSeg.test.tsx:6-56

### UI-51 — StatusSeg tones aplicam classes Tailwind corretas (default/warn/error)
`P1` · `UNIT`
- **Pré:** StatusSeg com diferentes tone values
- **Passos:**
  1. Montar 3x com tone='default'/'warn'/'error'
  2. Inspecionar span value de cada
- **Esperado:** default → text-accent-primary (verde), warn → text-semantic-warn (amarelo), error → text-accent-attn (magenta)
- **Cobertura atual:** ui/src/components/status/StatusSeg.test.tsx:18-50

### UI-56 — wsConnection store inicia em state='connecting'
`P1` · `UNIT`
- **Pré:** Store fresh
- **Passos:**
  1. useWsConnectionStore.getState().state
- **Esperado:** Retorna 'connecting' (não null, não undefined)
- **Cobertura atual:** ui/src/stores/wsConnection.test.ts:10-13

### UI-57 — wsConnection store setState transiciona por todos os 4 states
`P1` · `UNIT`
- **Pré:** Store controlável
- **Passos:**
  1. Chamar setState('connected'), setState('reconnecting'), setState('offline'), setState('connecting')
  2. Verificar cada transição
- **Esperado:** Cada setState atualiza state atomicamente
- **Cobertura atual:** ui/src/stores/wsConnection.test.ts:15-37

### UI-40 — useSystemHealth retorna dados vazios inicialmente (placeholder até Go expose HealthAPI)
`P2` · `UNIT` · 🔧recém-mudado
- **Pré:** useSystemHealth hook chamado, sem mock
- **Passos:**
  1. renderHook useSystemHealth
  2. Verificar result.current
- **Esperado:** Retorna {cpu_pct:0, mem_used_bytes:0, mem_total_bytes:0, uptime_seconds:0, active_alerts_count:0} (placeholder F10)
- **Cobertura atual:** none

### UI-49 — HudTopBar OPER badge tem animação de piscar (cipher-blink)
`P2` · `UNIT`
- **Pré:** HudTopBar renderizado
- **Passos:**
  1. Montar HudTopBar
  2. Inspecionar OPER badge (span com before:content-['●'])
- **Esperado:** Elemento tem classe 'before:animate-[cipher-blink_1.2s_steps(1)_infinite]'
- **Cobertura atual:** none

### UI-52 — StatusBar layout overflow-x-auto se houver muitos segmentos
`P2` · `UNIT`
- **Pré:** StatusBar com vários segmentos
- **Passos:**
  1. Montar StatusBar
  2. Inspecionar footer root className
- **Esperado:** Root tem classe 'overflow-x-auto' (scroll horizontal em telas pequenas)
- **Cobertura atual:** none

### UI-53 — HudTopBar layout flex justify-between: metricas esquerda vs direita
`P2` · `UNIT`
- **Pré:** HudTopBar renderizado
- **Passos:**
  1. Montar HudTopBar
  2. Inspecionar root div className
- **Esperado:** Root tem classe 'flex justify-between' (OPER/title/env esquerda, cpu/mem/rtt/uptime/alert direita)
- **Cobertura atual:** none

## OS Integration (Linux systray, D-Bus preflight, CLI flags, single-instance lock, close-to-tray)

_Gerencia comportamentos resident do app no Linux: system tray icon com menu (Mostrar/Quit), detecção de display/D-Bus para gating de features nativas, CLI flag --focus para keybind (Super+J), close-to-tray ao invés de quit, single-instance D-Bus lock com focus na segunda instância._


### OS-01 — Preflight: Display + D-Bus presente → trayAvailable=true
`P0` · `UNIT`
- **Pré:** Ambiente Linux com DISPLAY ou WAYLAND_DISPLAY set e D-Bus session bus disponível
- **Passos:**
  1. Chamar osintegration.PreflightOK() em ambiente válido (CI/dev/desktop)
  2. Verificar que ambas validações (display + dbus) passam
- **Esperado:** PreflightOK() retorna true; main.go ativa HideWindowOnClose=true + SingleInstanceLock
- **Cobertura atual:** internal/osintegration/preflight_test.go TestPreflightOK_WithDisplayAndDBus

### OS-02 — Preflight: Sem DISPLAY e sem WAYLAND_DISPLAY → trayAvailable=false
`P0` · `UNIT`
- **Pré:** Variáveis DISPLAY e WAYLAND_DISPLAY não definidas (headless ou container)
- **Passos:**
  1. Unset DISPLAY e WAYLAND_DISPLAY
  2. Chamar osintegration.PreflightOK()
- **Esperado:** PreflightOK() retorna false; main.go não ativa tray, HideWindowOnClose e SingleInstanceLock desabilitados
- **Cobertura atual:** internal/osintegration/preflight_test.go TestPreflightOK_NoDisplay

### OS-04 — TrayController.Start: Setup correto de icon, tooltip, menu items (Mostrar/Quit)
`P0` · `UNIT`
- **Pré:** NewTrayController instanciado com callbacks onShow/onQuit válidos
- **Passos:**
  1. Chamar trayCtl.Start(ctx)
  2. Aguardar factory.waitStarted() (Start lança start() em goroutine)
  3. Verificar que lib.SetIcon(TrayIconPNG) foi chamado
  4. Verificar que lib.SetTooltip('J-arvis') foi chamado
  5. Verificar que dois menu items foram criados: 'Mostrar janela' e 'Quit'
- **Esperado:** Icon + tooltip + dois menu items presentes; separator inserido entre eles
- **Cobertura atual:** internal/osintegration/tray_test.go TestTrayController_StartWiresMenuItems

### OS-05 — TrayController: Click 'Mostrar janela' invoca onShow callback
`P0` · `UNIT`
- **Pré:** TrayController com Start já executado
- **Passos:**
  1. Simular click no menu item 'Mostrar janela' (send no clickCh do fakeTrayItem)
  2. Aguardar até 500ms para menuLoop processar
  3. Verificar que onShow() foi invocado exatamente 1x
- **Esperado:** onShow callback executado; janela é mostrada/unminimised via wruntime.WindowShow + WindowUnminimise
- **Cobertura atual:** internal/osintegration/tray_test.go TestTrayController_ShowClickInvokesOnShow

### OS-10 — ParseFlags: --focus flag é extraído corretamente
`P0` · `UNIT`
- **Pré:** CLI args contêm --focus
- **Passos:**
  1. Chamar parseArgs(['jarvis', '--focus'])
  2. Verificar retorno CLIFlags
- **Esperado:** CLIFlags{Focus: true}; flag é documentada para futura navegação
- **Cobertura atual:** internal/osintegration/cli_test.go TestParseFlags (--focus case)

### OS-14 — main.go OnStartup: trayAvailable=true → ativa HideWindowOnClose + SingleInstanceLock
`P0` · `GO-INT` · 🔧recém-mudado
- **Pré:** main.go rodando em ambiente com PreflightOK()=true
- **Passos:**
  1. Verificar que trayAvailable := osintegration.PreflightOK()
  2. Verificar que appOpts.HideWindowOnClose = true
  3. Verificar que appOpts.SingleInstanceLock foi configurado com UniqueId='com.marcosdid.jarvis'
  4. Verificar que OnSecondInstanceLaunch handler foi registrado
- **Esperado:** Wails options estão configuradas para behavior nativo (close-to-tray, D-Bus single-instance)
- **Cobertura atual:** none

### OS-16 — main.go OnStartup: TrayController.Start é chamado (lança start() em goroutine)
`P0` · `GO-INT` · 🔧recém-mudado
- **Pré:** trayAvailable=true e OnStartup executando
- **Passos:**
  1. Chamar main.go OnStartup
  2. Verificar que trayCtl.Start(c) é invocado
  3. Verificar que appCtxPtr.Store(&ctxCopy) salva contexto para onShow/onQuit
  4. Aguardar que goroutine start() complete (real factory async nativeStart)
- **Esperado:** TrayController inicializado; tray menu disponível; appCtxPtr visível para goroutines
- **Cobertura atual:** none

### OS-17 — main.go OnShutdown: TrayController.Stop chamado PRIMEIRO (UI ops sumir antes domain ops)
`P0` · `GO-INT` · 🔧recém-mudado
- **Pré:** OnShutdown executando com trayAvailable=true
- **Passos:**
  1. Verificar sequência em OnShutdown: trayCtl.Stop() vem PRIMEIRO
  2. Depois: masterSvc.Stop(), localSrv.Stop()
  3. Verificar que end() callback invoca onExit (muda quitInProgress ou é no-op)
- **Esperado:** Tray é desmontado primeiro; domain services param depois; nenhuma race entre Wails exit e domain operations
- **Cobertura atual:** none

### OS-18 — handleSecondInstance callback: Focus na janela (show + unminimise)
`P0` · `MANUAL` · 🔧recém-mudado
- **Pré:** Segunda instância do binário lançada (SuperKey+J bind ou jarvis --focus); D-Bus SingleInstanceLock ativo
- **Passos:**
  1. Primeira instância rodando normalmente
  2. Pressionar Super+J (ou executar 'jarvis --focus' em novo terminal)
  3. D-Bus detecta segunda instância e invoca OnSecondInstanceLaunch handler
  4. Handler chama wruntime.WindowShow(*appCtxPtr) + WindowUnminimise(*appCtxPtr)
- **Esperado:** Janela é mostrada/unminimizada; usuário vê J-arvis trazido ao foco
- **Cobertura atual:** none

### OS-20 — onShow callback (tray menu 'Mostrar janela'): appCtxPtr permite acesso ao context
`P0` · `UNIT` · 🔧recém-mudado
- **Pré:** TrayController com onShow callback definido
- **Passos:**
  1. Chamar onShow() de tray (ou simular)
  2. Verificar que appCtxPtr.Load() retorna contexto válido
  3. Chamar wruntime.WindowShow(*appCtxPtr) + WindowUnminimise(*appCtxPtr)
- **Esperado:** onShow consegue acessar app context de múltiplas goroutines seguramente via atomic.Pointer
- **Cobertura atual:** none

### OS-21 — onQuit callback (tray menu 'Quit'): invoca wruntime.Quit(*appCtxPtr)
`P0` · `MANUAL` · 🔧recém-mudado
- **Pré:** TrayController com onQuit callback; usuário clica 'Quit' ou Stop() invoca fallback
- **Passos:**
  1. Simular click 'Quit' ou chamar ctl.Stop()
  2. onQuit() é invocado
  3. Verificar que wruntime.Quit(*appCtxPtr) é chamado
- **Esperado:** App encerra gracefully via Wails runtime; OnShutdown dispara
- **Cobertura atual:** none

### OS-22 — Close-to-tray: Fechar janela (X button) → janela se minimiza, não fecha app
`P0` · `MANUAL` · 🔧recém-mudado
- **Pré:** App rodando com HideWindowOnClose=true
- **Passos:**
  1. Abrir J-arvis normalmente
  2. Clicar no botão X da janela
  3. Verificar que janela desaparece
- **Esperado:** Janela é escondida (não fecha o app); app continua rodando; ícone de tray permanece clicável; 'Mostrar janela' funciona
- **Cobertura atual:** none

### OS-03 — Preflight: D-Bus indisponível (DBUS_SESSION_BUS_ADDRESS vazio) → trayAvailable=false
`P1` · `UNIT`
- **Pré:** DISPLAY set mas DBUS_SESSION_BUS_ADDRESS e XDG_RUNTIME_DIR vazios; godbus não consegue autolaunch
- **Passos:**
  1. Set DISPLAY=:0, unset DBUS_SESSION_BUS_ADDRESS e XDG_RUNTIME_DIR
  2. Chamar osintegration.PreflightOK()
  3. Verificar que D-Bus connection falha
- **Esperado:** PreflightOK() retorna false; tray e single-instance lock permanecem desabilitados
- **Cobertura atual:** internal/osintegration/preflight_test.go TestPreflightOK_NoDBus (best-effort)

### OS-06 — TrayController: Click 'Quit' é idempotente sob concorrência (quitInProgress swap)
`P1` · `UNIT`
- **Pré:** TrayController com Start já executado
- **Passos:**
  1. Disparar 10 clicks simultâneos no menu item 'Quit'
  2. Aguardar 500ms para menuLoop processar todos
  3. Verificar que onQuit() foi invocado EXATAMENTE 1x
  4. Verificar que lib.Quit() foi chamado 1x
- **Esperado:** Primeiro click vence swap, subsequentes são no-op; quitInProgress=true previne re-entrada
- **Cobertura atual:** internal/osintegration/tray_test.go TestTrayController_QuitClickIdempotentUnderConcurrency

### OS-07 — TrayController.Stop: Invoca onExit fallback quando usuário não clicou Quit
`P1` · `UNIT`
- **Pré:** TrayController com Start, contexto válido, sem click no Quit
- **Passos:**
  1. Chamar ctl.Stop() diretamente (simula SIGTERM/OnShutdown sem user click)
  2. Aguardar processamento
  3. Verificar que onQuit() foi invocado 1x via onExit fallback
- **Esperado:** Fallback path (onExit) invoca onQuit() porque swap encontra quitInProgress=false
- **Cobertura atual:** internal/osintegration/tray_test.go TestTrayController_OnExitFiresOnQuitWhenSteadyStateDidNot

### OS-08 — TrayController.Stop: onExit é no-op após steady-state Quit
`P1` · `UNIT`
- **Pré:** TrayController com Start e menu item Quit clicado
- **Passos:**
  1. Click 'Quit' (steady-state path vence swap, invoca onQuit)
  2. Aguardar processamento (500ms)
  3. Chamar ctl.Stop() (simula OnShutdown tardio)
  4. Verificar que onQuit() não foi invocado nova vez
- **Esperado:** onQuit() invocado 1x total; onExit encontra quitInProgress=true e é no-op
- **Cobertura atual:** internal/osintegration/tray_test.go TestTrayController_OnExitNoOpAfterSteadyStateQuit

### OS-11 — ParseFlags: Unknown args são ignorados silenciosamente (forward compat)
`P1` · `UNIT`
- **Pré:** CLI args contêm unknown flags
- **Passos:**
  1. Chamar parseArgs(['jarvis', '--xxx', 'yyy', '--focus', '--task=t1'])
  2. Verificar retorno
- **Esperado:** Apenas --focus extraído; --xxx, yyy, --task ignorados (não causa erro)
- **Cobertura atual:** internal/osintegration/cli_test.go TestParseFlags (unknown args case)

### OS-12 — ParseFlags: Sem argumentos → CLIFlags vazio
`P1` · `UNIT`
- **Pré:** Binário chamado sem flags
- **Passos:**
  1. Chamar parseArgs(['jarvis'])
  2. Verificar retorno
- **Esperado:** CLIFlags{Focus: false}
- **Cobertura atual:** internal/osintegration/cli_test.go TestParseFlags (no args case)

### OS-13 — TrayIconPNG asset: PNG válido com magic bytes corretos
`P1` · `UNIT`
- **Pré:** Asset tray-idle.png embedded em osintegration
- **Passos:**
  1. Verificar len(TrayIconPNG) > 100 bytes
  2. Verificar que primeiros 4 bytes são PNG magic: 0x89 'P' 'N' 'G'
- **Esperado:** Asset é PNG válido; SetIcon(TrayIconPNG) não falha
- **Cobertura atual:** internal/osintegration/assets_test.go TestTrayIconPNG_Embedded

### OS-15 — main.go OnStartup: trayAvailable=false → HideWindowOnClose/SingleInstanceLock desabilitados
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** main.go rodando em ambiente headless (sem display/D-Bus)
- **Passos:**
  1. Unset DISPLAY, WAYLAND_DISPLAY, DBUS_SESSION_BUS_ADDRESS
  2. Verificar que trayAvailable := osintegration.PreflightOK() = false
  3. Verificar que appOpts.HideWindowOnClose não é setado (default false)
  4. Verificar que appOpts.SingleInstanceLock é nil
- **Esperado:** Tray features desabilitadas gracefully; app roda em headless mode
- **Cobertura atual:** none

### OS-23 — Close-to-tray + Single-instance: Abrir segunda instância traz janela ao foco
`P1` · `MANUAL` · 🔧recém-mudado
- **Pré:** Primeira instância já rodando (janela minimizada via X button); single-instance lock ativo
- **Passos:**
  1. Segunda instância lançada (terminal, hotkey, menu)
  2. D-Bus detecta lock e invoca OnSecondInstanceLaunch
  3. Handler invoca WindowShow + WindowUnminimise
- **Esperado:** Janela reaparece ao foco; segunda instância é killed gracefully
- **Cobertura atual:** none

### OS-24 — CLI --focus: jarvis --focus → passa Focus=true em CLIFlags
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** Binário chamado com --focus (keybind Super+J)
- **Passos:**
  1. Executar: /usr/bin/jarvis --focus
  2. Verificar que cliFlags := osintegration.ParseFlags() retorna Focus=true
  3. Verificar que handleSecondInstance é invocado via D-Bus (ou simulado)
- **Esperado:** Flag é documentado para futura navegação; hoje handleSecondInstance sempre foca independente da flag
- **Cobertura atual:** none

### OS-26 — TrayController: menuLoop respeita context cancellation (ctx.Done())
`P1` · `UNIT`
- **Pré:** TrayController.Start com contexto cancellable
- **Passos:**
  1. Chamar trayCtl.Start(ctx)
  2. Cancelar contexto (ctx.Cancel() ou deadline exceeded)
  3. Aguardar que menuLoop leia <-ctx.Done()
- **Esperado:** menuLoop retorna e encerra gracefully sem goroutine leak
- **Cobertura atual:** none

### OS-27 — Preflight edge-case: Apenas WAYLAND_DISPLAY set (não DISPLAY) → trayAvailable=true
`P1` · `UNIT`
- **Pré:** Ambiente Wayland puro (WAYLAND_DISPLAY set, DISPLAY vazio)
- **Passos:**
  1. Unset DISPLAY, set WAYLAND_DISPLAY=wayland-0
  2. Chamar PreflightOK()
- **Esperado:** PreflightOK() retorna true (primeira condição: DISPLAY OR WAYLAND_DISPLAY)
- **Cobertura atual:** none

### OS-28 — OnStartup sequence: appCtxPtr.Store() salva contexto ANTES de trayCtl.Start()
`P1` · `GO-INT` · 🔧recém-mudado
- **Pré:** OnStartup rodando
- **Passos:**
  1. Verificar ordem em OnStartup: realBus.Store() → appCtxPtr.Store() → (depois) trayCtl.Start()
  2. Verificar que appCtxPtr é atomic.Pointer[context.Context]
- **Esperado:** appCtxPtr visível para handleSecondInstance (pode ser invocado durante OnStartup) e tray goroutines
- **Cobertura atual:** none

### OS-09 — TrayController.Start: Factory retorna nil → sem panic
`P2` · `UNIT`
- **Pré:** TrayController com factory que retorna (nil, nil, nil)
- **Passos:**
  1. Chamar ctl.Start(ctx) com bad factory
  2. Chamar ctl.Stop()
  3. Verificar que nenhuma panic foi levantada
- **Esperado:** Execução completa sem panic; callbacks não são invocados (lib=nil)
- **Cobertura atual:** internal/osintegration/tray_test.go TestTrayController_StartFailFactoryReturnsNil

### OS-19 — handleSecondInstance: appCtxPtr=nil (segundo launch ANTES de OnStartup completo) → no-op sem panic
`P2` · `GO-INT` · 🔧recém-mudado
- **Pré:** Segunda instância lançada durante OnStartup
- **Passos:**
  1. Segunda instância invoca handleSecondInstance enquanto appCtxPtr.Load()=nil
  2. Verificar que nenhuma panic é levantada
- **Esperado:** Handler é best-effort; nil check permite no-op safety
- **Cobertura atual:** none

### OS-25 — PreflightOK: D-Bus SessionBus connection não é fechada (reutiliza cache godbus)
`P2` · `UNIT`
- **Pré:** Verificação de preflight executada
- **Passos:**
  1. Chamar PreflightOK() múltiplas vezes
  2. Verificar que godbus.SessionBus() retorna cached *Conn
  3. Verificar que nenhum .Close() é chamado em PreflightOK
- **Esperado:** Conexão godbus permanece aberta para sistray.nativeStart usar; sem forced reconnect races
- **Cobertura atual:** none
