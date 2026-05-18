# J-arvis — Orquestrador local de Claude Code

> **One-liner.** Um painel local que transforma várias abas perdidas de Claude Code em um backlog organizado, com sandbox por sessão e um botão "Run" que sobe a stack inteira do projeto.

---

## 1. O que é o sistema

J-arvis é um **orquestrador local de sessões de Claude Code**. Ele roda como um daemon sob demanda na máquina do desenvolvedor, serve uma UI web no browser (em `localhost`) e gerencia múltiplas sessões de Claude Code rodando em **jaulas isoladas** (sandbox `ai-jail`), uma por worktree.

Em vez de o usuário pular entre várias abas de terminal e perder o fio de cada uma, ele trabalha contra um **kanban unificado de tasks** — cross-project, cross-worktree — e cada task que entra em execução abre sua própria sessão isolada, com status semântico visível em tempo real.

**Forma curta para colocar em pitch:**

> "É o painel de bordo do desenvolvedor que delega para vários agentes ao mesmo tempo. Você não precisa mais lembrar o que cada aba está fazendo — o orquestrador lembra por você, em forma de backlog."

**Stack técnica resumida** (para devs que pegam o repo na mão):

- **App:** binário único Go 1.26 + Wails v2.12 (WebView webkit2gtk-4.1 embedando UI React em produção) + SQLite via `modernc.org/sqlite` + `goose` migrations.
- **UI:** React 19 + Tailwind v4 + shadcn/ui + TanStack Query + Zustand + `@dnd-kit` (drag & drop). Compilada em estático (Vite) e embedada no binário Go via `//go:embed`.
- **Sandbox:** `ai-jail` externo (Fabio Akita) — bwrap + Landlock + seccomp.
- **Comunicação Claude Code ↔ app:** hooks (`Notification`, `Stop`, `PreToolUse`) escritos em `<worktree>/.claude/settings.json` antes do `ai-jail run`; hooks respondem via HTTP loopback `127.0.0.1:N` montado pelo binário.
- **Comunicação UI ↔ app:** Wails bindings in-process (chamadas Go → JS diretas via runtime do WebView; sem HTTP/WS).
- **OS integration:** system tray (`fyne.io/systray`), single-instance D-Bus (Wails `SingleInstanceLock`), close-to-tray lifecycle, CLI `--focus` flag bindável via Super+J no DE.
- **Memória entre sessões:** delegada ao `claude-mem` — o orquestrador não duplica essa responsabilidade.
- **Plataforma:** Linux only no MVP (Ubuntu 22.04+ Wayland ou X11).

---

## 2. O problema que ele resolve

O cenário real do desenvolvedor que usa Claude Code intensivamente hoje:

- Tem **2 a 3 projetos diferentes** abertos ao mesmo tempo.
- Cada projeto tem **várias worktrees** (feature A, bugfix B, refactor C).
- Cada worktree tem uma **aba de Claude Code rodando**.
- Algumas estão **executando**, outras **esperando aprovação**, outras **paradas com erro**, outras **terminaram**.

O que isso causa, na prática:

1. **Perda de contexto.** Você abre uma aba, olha 5 segundos e não sabe se é a do refactor do backend ou a do bugfix no frontend. Erra a pergunta de follow-up e atrapalha o próprio agente.
2. **Aprovações dispersas.** Cada aba pede `[y/n/always]` na hora que pede. Se você está olhando outra, perde minutos parado esperando atenção.
3. **Estado invisível.** Não dá pra olhar todas as abas de uma vez e responder "qual está esperando algo de mim, agora?".
4. **Worktrees desorganizadas.** Você cria worktrees pela CLI, esquece quais existem, vira lixo no disco.
5. **Testar o que o agente fez é trabalhoso.** Pra ver o resultado, precisa entrar na worktree, subir o backend, o banco, o frontend, abrir o navegador. Em projetos com 4-5 serviços isso vira fricção.
6. **Risco real de execução.** Claude Code pode rodar comandos destrutivos no host (`rm`, `git push --force`, etc.). Sem sandbox, qualquer alucinação é incidente.

O J-arvis ataca esses seis pontos juntos, com **um orquestrador único** em vez de seis ferramentas separadas.

---

## 3. Como resolve — as duas apostas de diferenciação

Já existem ferramentas concorrentes (Crystal/Nimbalyst, Conductor, Claude Squad, ccmanager). O que **diferencia** o J-arvis:

### 3.1. Sandbox-first de verdade

Isolamento via `ai-jail` é **integrado desde o dia 1**, não um afterthought. Cada sessão de Claude Code roda dentro de uma jaula com:

- 1 worktree montada (apenas).
- Rede isolada (só localhost da jaula).
- Perfil de permissão específico da task (ex: "frontend" libera npm e file edits no diretório `ui/`; "refactor" libera ferramentas de manipulação de AST).
- Blocklist de comandos perigosos.

O orquestrador roda **fora** da jaula, supervisiona, mas não compartilha contexto com a sessão. Resultado: **concorrência segura na própria máquina do dev**, sem precisar de VM ou cloud.

### 3.2. Task-first em vez de session-first

Esse é o ponto **estruturante**. Em todas as ferramentas concorrentes, o objeto primário é a "sessão" (uma aba do agente). O usuário pensa "vou abrir uma sessão pra fazer X". O J-arvis inverte:

- **Task** é o objeto primário. O usuário pensa "vou adicionar X ao backlog" e arrasta no kanban.
- **Sessão** é só uma **execução** de uma task. Pode até ter várias sessões na história da mesma task (ex: pausou, retomou).
- **Worktree** é um recurso compartilhável entre tasks ao longo do tempo.

A UI gira em torno do **kanban unificado cross-project**, com colunas `idea → ready → in_progress → review → done` (mais `discarded`). O usuário arrasta cards entre colunas; o resto (criar worktree, abrir sessão isolada, propagar status) é orquestração que acontece embaixo.

Resultado prático: você fecha o laptop no fim do dia e abre amanhã com **a memória do que está fazendo intacta** — não como abas perdidas, mas como cards posicionados.

---

## 4. Personas de uso

### Persona principal — "Solo Senior Dev"

- Trabalha sozinho ou em time pequeno (até 5 devs).
- Mantém **2 a 4 projetos paralelos** (lateral, side-project, freelance, principal).
- Já é heavy-user de Claude Code — não precisa ser convencido do agente, precisa de **organização**.
- Linux como SO principal (Ubuntu/Pop!_OS/Arch).
- Confortável com terminal, git worktree, Docker.
- Frustração principal: "eu confio no agente; o que eu não confio é em mim lembrando o que pedi pra ele".

### Persona secundária — "Tech Lead delegador"

- Coordena 1-2 juniors + agentes.
- Quer ver o estado de **todas as frentes** rapidamente, sem fazer 1-on-1 a cada hora.
- Usa templates pré-aprovados pra que juniors disparem tasks "frontend"/"bugfix" com perfil de permissão certo já configurado.
- Valor que extrai: **dashboard mental** do trabalho em curso.

### Persona terciária (v2) — "Time pequeno"

- Múltiplos devs compartilhando backlog (via importação de GitHub Issues / Azure DevOps).
- Fora do MVP, mas a arquitetura task-first já antecipa isso.

### Anti-persona

- Quem trabalha **monorepo sem worktrees**, sessão única, em 1 projeto só. Pra esse perfil o J-arvis adiciona overhead sem retorno.
- Quem usa **macOS/Windows** como SO principal (sem WSL2 nativo de Linux com `ai-jail`). MVP é Linux.

---

## 5. Fluxos de uso

### 5.1. Fluxo "manhã do dev" (golden path)

1. Dev abre o terminal, roda `make up`.
2. Daemon sobe (porta local), browser abre em `localhost:<porta>`.
3. UI exibe **kanban unificado** com tasks de todos os projetos. Chip de cor identifica o projeto de cada card.
4. Dev vê 3 cards em `in_progress` da noite anterior. Status em tempo real: 1 `awaiting_response` (precisa de atenção), 1 `idle` (terminou de mexer em algo), 1 `executing` (ainda processando).
5. Clica no `awaiting_response` → drawer lateral mostra a worktree, o transcript resumido em 1 linha, e o botão "Abrir terminal" que joga a janela do Claude Code em foco.
6. Dev responde, fecha a aba, status do card volta a `executing`. Volta pro kanban.

### 5.2. Fluxo "quick session"

Caso: dev quer perguntar algo rápido pro Claude no contexto de um projeto, sem criar task formal.

1. Botão "Nova sessão rápida" no projeto.
2. UI cria uma **task implícita** (`Session.task_id` é NOT NULL — ADR-0012), com título auto-gerado e estado `in_progress`.
3. Spawn da sessão dentro de ai-jail.
4. Quando a sessão termina, a task pode ser promovida para `done` ou descartada.

A intenção do task-first não cria fricção pra perguntas pontuais.

### 5.3. Fluxo "sessão mestra" — conversar com o J-arvis (v1.5)

Em vez de o Planner ser um fluxo isolado de "cole épico → preview de subtasks", o J-arvis expõe uma **sessão mestra**: uma sessão de Claude Code rodando **no nível do orquestrador** (não dentro de uma worktree específica), equipada com **skills/tools** que dão acesso à API do daemon.

A sessão mestra é a **superfície de controle conversacional** do J-arvis. O kanban continua sendo a superfície visual; a sessão mestra vira a superfície verbal. O dev pode pedir em linguagem natural qualquer coisa que envolva manipular o backlog, refinar tasks, ou consultar o estado do orquestrador.

#### Casos de uso típicos da sessão mestra

- "Quero adicionar 5 tarefas relacionadas a OAuth Google em todos os serviços." (caso "novo épico")
- "Refina a descrição da task #42 explicando que precisa de testes E2E."
- "Quais tasks estão paradas em `review` há mais de 2 dias?"
- "Mescla as tasks #5 e #7, são o mesmo escopo."
- "Cria 1 task pra cada ADR pendente em `docs/adr/`."
- "Move pra `discarded` qualquer task em `idea` há mais de 30 dias."
- "Resume o que cada sessão em `executing` está fazendo agora."

Tudo isso, antes, exigiria telas dedicadas. Aqui é uma conversa.

#### Skills disponíveis na sessão mestra

Skills/tools registradas que cobrem a API pública do daemon:

| Skill | Operação |
|---|---|
| `create_task` | Cria nova task (estado, projeto, template, perfil opcionais) |
| `refine_task` | Atualiza título, descrição, template, perfil de permissão |
| `move_task` | Move entre estados do kanban |
| `merge_tasks` | Mescla N tasks em uma |
| `list_tasks` | Query com filtros (projeto, estado, idade, tag) |
| `read_project` | Lê estrutura de um projeto (sem entrar em worktree) |
| `read_backlog` | Lê backlog inteiro pra contexto |
| `propose_breakdown` | Recebe um épico em texto, devolve subtasks propostas — substitui o "Planner" como fluxo dedicado |
| `start_session` | Dispara sessão de execução de uma task (apenas com confirmação explícita) |

**Invariante mantida:** a sessão mestra **propõe**, não **executa** sozinha. `start_session`, `move_task` e qualquer skill mutativa passam pelo prompt `[y/n/always]` do Claude no terminal nativo (consistente com ADR-0011 — decisão de permissão fica fora da UI). Isso preserva a regra original do §7 do CONTEXT ("o planner nunca inicia sessões sozinho"), agora generalizada: nenhuma skill mutativa age sem aprovação humana.

#### Caso "novo épico" — antes vs depois

**Antes** (Planner como fluxo dedicado):

1. Botão "Novo épico" → modal.
2. Cola texto → spinner.
3. Tela de preview com subtasks editáveis.
4. Aprovar → bulk insert.

**Depois** (via sessão mestra):

1. Abre a sessão mestra (ou ela já está aberta — é persistente).
2. Cola: *"Adicionar OAuth Google em todos os serviços. Lê o repo, vê o backlog atual, e propõe subtasks."*
3. Sessão mestra usa `read_project` + `read_backlog` + `propose_breakdown`, devolve proposta no chat.
4. Dev responde no chat: *"remove a #3, mescla #4 com #5, troca o template da #1 pra refactor"*. Iteração natural.
5. *"Manda pras `ready`."* → sessão mestra chama `create_task` em batch (com confirmação).

A força do modelo: o passo 4 (refinar a proposta) era a parte mais frágil do fluxo de modal — agora é só conversar.

#### Como o J-arvis hospeda a sessão mestra

- **Sandbox especial:** ai-jail com perfil `orchestrator` — sem acesso a worktrees individuais, mas com permissão pra falar com `localhost:<port>/api/*` do daemon.
- **Persistência:** uma sessão mestra por instância do orquestrador. Sobe junto com `make up`, transcript persistido, retomável após restart.
- **UI:** painel dedicado no topo (ao lado do kanban) com chat visível, transcript scrollável, e botões de "ações sugeridas" extraídas do output (ex: "aplicar 5 tasks propostas" como botão one-click).
- **Memória:** integra com `claude-mem` pra lembrar contexto entre sessões mestras de dias diferentes.

#### Decisões pendentes (a resolver antes de implementar)

1. **Bridge para a API: MCP server ou skills HTTP cruas?** MCP tem benefício de interop com outros clientes (Cursor, Codex), mas adiciona um servidor a manter. HTTP cru via tools nativas do Claude é mais simples, menos descoberto.
2. **Uma sessão mestra global ou uma por projeto?** Global permite cross-project ("lista órfãs em todos os projetos"). Por projeto é mais focada e evita contexto vazando.
3. **Auto-arranca ou spawn-on-demand?** Sobe junto com `make up` (custo idle baixo, latência zero) ou só na primeira pergunta (cold-start, mas zero custo se o dev não usar).
4. **Como expor as "ações sugeridas" na UI?** Parsing do output (frágil) ou skill explícita `propose_ui_action()` que a sessão mestra chama (acoplado mas determinístico).

### 5.4. Fluxo "Run from Panel"

Caso: dev acabou de receber uma feature pronta do agente. Quer ver no browser.

1. Card da task tem botão ▶ Run.
2. Orquestrador lê o manifesto `.orchestrator/run.yml` do projeto.
3. Se não existe, abre uma sessão Claude efêmera com prompt "leia o repo, proponha um manifesto" — dev revisa, salva, commita. Manifesto vira parte do projeto.
4. Aloca portas dinâmicas no range `31000-31999`. Exporta como `PORT_FRONTEND`, `PORT_BACKEND`, `PORT_DB`.
5. Sobe DB em `docker run --rm` (descartável por execução), seed após health check.
6. Sobe backend → health check → sobe frontend.
7. Quando `ready`, UI mostra **URL grande clicável**. Dev clica, browser abre, vê a feature.
8. Botão "Restart só backend" pra iterar rápido.
9. Auto-cleanup quando task vira `done`/`discarded`, ao fechar orquestrador, ou por TTL de idle.

---

## 6. Modelo mental — para Design

A UI tem **duas superfícies complementares**, cada uma com seu verbo dominante:

| Superfície | Verbo dominante | Quando o dev usa |
|---|---|---|
| **Kanban** | arrastar | Visualizar estado, mover tasks, abrir detalhes |
| **Sessão mestra** | conversar | Criar/refinar tasks em lote, perguntar coisas, planejar épicos |

As duas dividem a tela (kanban como área principal, sessão mestra como painel persistente no topo ou na lateral) e operam sobre **o mesmo modelo de dados** — qualquer ação numa reflete na outra em tempo real.

### 6.1. Objetos visuais do kanban

1. **Card de task.** Unidade básica. Mostra: título, projeto (chip colorido), estado, último status de sessão se houver, template/perfil aplicado.
2. **Coluna do kanban.** Estados `idea`, `ready`, `in_progress`, `review`, `done` (`discarded` é filtro, não coluna).
3. **Drawer de projeto/worktree.** Painel lateral que abre por demanda. Não compete com o kanban, complementa.
4. **Detalhe da task (modal).** Aberto ao clicar no card. Mostra histórico de sessões, transcript resumido, botões de ação (Run, abrir terminal, mudar perfil de permissão).

### 6.2. Objetos visuais da sessão mestra

1. **Painel de chat.** Persistente, sempre visível. Transcript scrollável da conversa em curso com a sessão mestra.
2. **Input conversacional.** Multi-linha, com paste de épicos longos sem fricção.
3. **Cartões de "ação sugerida".** Quando a sessão mestra propõe uma operação mutativa (ex: "criar 5 tasks", "mesclar #4 e #5"), aparecem botões one-click pra confirmar — em vez de o dev ter que digitar "sim, faz isso".
4. **Indicador de skills em uso.** Badge sutil mostrando qual skill está sendo executada agora (ex: `read_backlog`, `propose_breakdown`) — dá transparência sem virar ruído.

### 6.3. Princípios de design implícitos

Aparecem no código (`ui/src/components/`) e nas ADRs:

- **Cross-project é o caso real** (ADR-0013). Kanban é unificado, não um por projeto. Filtros multi-select permitem isolar quando preciso. A sessão mestra também opera cross-project por padrão.
- **Status em tempo real, não polling.** Toda mudança de estado de sessão chega via WebSocket (envelope tipado, ADR-0010) e atualiza o card sem reload. A sessão mestra também recebe esse stream — pode ser perguntada "o que mudou nos últimos 5 minutos?".
- **Permissão fica no terminal nativo.** Nem kanban nem sessão mestra duplicam o prompt `[y/n/always]` do Claude Code. Decisão de permissão é responsabilidade do terminal nativo + `settings.json` (ADR-0011). Isso evita caminho paralelo de aprovação.
- **Drag & drop como verbo principal do kanban** (`@dnd-kit`). Mover card entre colunas é a ação mais frequente — fluida, sem lag, sem confirmação modal.
- **Conversa como verbo principal da sessão mestra.** Operações em lote, refinamento iterativo e consultas ad-hoc sempre custam menos como conversa do que como sequência de cliques. A sessão mestra existe pra absorver tudo que viraria "abrir modal → preencher form → confirmar".
- **Duas superfícies, um modelo.** Toda ação na sessão mestra reflete imediatamente no kanban (e vice-versa). Sem "modo edição" separado, sem confirmação de sincronização.

### 6.4. Estética

Em consolidação: minimalista, alta densidade de informação, dark mode-first (por ser ferramenta de dev), tipografia mono em campos técnicos (transcripts, paths, comandos) e sans em campos editoriais (descrição de task, chat). O painel da sessão mestra deve ser visualmente distinto do kanban — talvez fundo levemente diferenciado — pra deixar claro que são duas modalidades, não duas seções da mesma coisa.

---

## 7. Modelo mental — para Marketing

### 7.1. Posicionamento

> **"Não é mais um wrapper de Claude Code. É o seu Trello acoplado à sandbox."**

- **Não competimos** com Cursor/Continue (esses são editores). Competimos com **Crystal, Conductor, Claude Squad, ccmanager** — orquestradores multi-agente.
- **Diferenciação dupla:** sandbox-first integrado + task-first em vez de session-first.
- **Não é cloud.** Tudo local, single-user, zero auth, zero rede externa por padrão. Isso é uma vantagem de marketing real numa era de paranoia com prompt injection e exfil.

### 7.2. Mensagens-chave

- **Para quem está cansado de perder contexto:** "Você não precisa lembrar de qual aba é qual. O kanban lembra."
- **Para quem tem medo de o agente fazer besteira no host:** "Cada sessão num sandbox, com perfil de permissão por tipo de task. O dia que algo der ruim, fica contido."
- **Para quem testa o que o agente fez:** "Botão Run. Sobe banco, backend e front em portas dinâmicas. URL clicável."
- **Para quem usa Claude Code intensivamente:** "Backlog é o trabalho. Sessão é só uma execução."

### 7.3. O que NÃO somos (importante para evitar promessa errada)

- ❌ **Não somos** uma alternativa ao Claude Code — somos um orquestrador **por cima** dele.
- ❌ **Não somos** uma plataforma cloud / SaaS. Tudo roda na máquina do dev. (Reduz custo de venda, aumenta confiança.)
- ❌ **Não somos** multi-user no MVP. Time vem em v2.
- ❌ **Não rodamos** em macOS/Windows ainda. Linux only no MVP.
- ❌ **Não fazemos** memória entre sessões — `claude-mem` faz, e fazemos referência a ele.

### 7.4. Caminhos de aquisição plausíveis

- Conteúdo técnico (blog/Twitter/Bluesky) demonstrando o workflow.
- GIF de 30 segundos: 3 cards em `executing`, um vira `awaiting_response`, dev resolve, segue. (Esse GIF vende sozinho.)
- Demo num projeto real open-source — mostrar o "Run from Panel" funcionando.
- Comunidades alvo: Reddit r/ClaudeAI, HN, Twitter dev pt-BR, Discord do Claude Code.

---

## 8. Modelo mental — para Negócio

### 8.1. Modelo atual (MVP)

- **Open-source local-first.** Sem cobrar nada no MVP.
- Stack 100% rodando no host do usuário. **Custo operacional para o produto: zero.**
- Custo de Claude Code (API/subscription) fica com o usuário, não com o produto. **Não somos um intermediário de billing.**

### 8.2. Caminhos de monetização realistas (pós-MVP)

Não há decisão tomada, mas as opções no horizonte:

| Caminho | Como funciona | Risco |
|---|---|---|
| **Pro local features** | Versão paga com features avançadas (planner meta-agente, custo por sessão, diff agregado) | Comoditização — competidores open-source copiam |
| **Time tier (v2)** | Multi-user via Azure DevOps / GitHub Issues — vende pra times pequenos | Salto grande de complexidade (auth, sync, conflitos) |
| **Marketplace de templates** | Templates de task curados (e.g. "feature SaaS completa") com perfil de permissão e prompts otimizados | Depende de adoção crítica antes |
| **Suporte / consultoria** | Setup pra empresas que querem on-prem com `ai-jail` configurado certo | Não escala, mas valida ICP |

### 8.3. Métricas que importam (early)

- **DAU local.** Quantos devs rodam `make up` por dia.
- **Tasks criadas/dia/usuário.** Proxy de engajamento.
- **Sessões por task.** Se for >1 consistentemente, valida o modelo task-first.
- **Run from Panel — clicks.** Proxy de quanto o usuário fecha o loop "agente fez → testei".

(Como tudo é local, telemetria depende de o usuário **optar por enviar** — coerente com a postura local-first. Isso limita métricas, mas é uma promessa de marca.)

### 8.4. Custos / dependências críticas

- **`ai-jail`** é dependência externa (Fabio Akita). Se o projeto morrer, há plano B: substituir por wrapper próprio (bwrap + Landlock + seccomp) **mantendo a mesma interface `SessionRuntime`** — zero ripple. Está documentado no ARCHITECTURE.md §5.
- **Claude Code** é dependência da Anthropic. Mudança de schema de hooks ou de transcript pode quebrar — risco gerenciável, evolui rápido.
- **`claude-mem`** é plugin terceiro — risco baixo, fácil substituir.

---

## 9. Modelo mental — para Desenvolvimento

### 9.1. Arquitetura em uma frase

> "Binário Wails (Go) com WebView embedando UI React; sessões Claude isoladas via ai-jail; SQLite local; Claude → app via hooks HTTP loopback; UI ↔ app via Wails bindings in-process."

Diagrama detalhado em `ARCHITECTURE.md §2`.

### 9.2. Modelo de dados (SQLite)

```
Project
  └── Worktree
        ├── current_task_id?  → Task
        └── (RunInstance ativa do Run from Panel)

Task
  ├── state ∈ {idea, ready, in_progress, review, done, discarded}
  ├── template? (preenchido em F7)
  └── permission_profile? (preenchido em F7)

Session  (tabela `sessions`; struct `store.Session`)
  ├── task_id      NOT NULL  (ADR-0012)
  ├── worktree_id  NOT NULL
  ├── jail_id, pid, status, transcript_path
  └── status ∈ {executing, awaiting_response, idle, error, done}

RunInstance
  ├── worktree_id
  ├── manifest_path → .orchestrator/run.yml
  ├── ports_json
  └── status ∈ {building, seeding, ready, failed, stopped}
```

### 9.3. Decisões arquiteturais relevantes (ADRs)

Todos os ADRs ficam em `docs/adr/`. Os mais estruturantes:

- **ADR-0001 — Sandbox via ai-jail externo.** Não reinventamos kernel-isolation. Trocável por wrapper próprio se necessário, mesma interface `SessionRuntime`.
- **ADR-0004 — TDD discipline.** Camadas: unit + integration Go (`go test`), UI vitest, E2E Playwright contra `cmd/jarvis-e2e-http`. Coverage 100% rigoroso (pré-F10) deprecado durante o pivot; alvo é cobertura saudável sem metric-gaming.
- **ADR-0007 / ADR-0012 — Task-first.** `Session.task_id` é NOT NULL. Quick session cria task implícita. Sem isso, viramos session-first como os concorrentes.
- **ADR-0009 — Hooks via settings.json no jail.** Daemon escreve `<worktree>/.claude/settings.json` antes de `ai-jail run`. Zero pegada em `~/.claude` do host. Sandbox-clean.
- **ADR-0010 — WebSocket canal único, envelope tipado.** `/ws` único, payload `{type, session_id, payload, at}`. Escala pra F4/F6 sem multiplicar canais.
- **ADR-0011 — F3 cancelada / fundida em F2.** Sem fila ativa de aprovações. Decisão de permissão fica no terminal nativo do Claude + `settings.json`. Evita caminho paralelo concorrente.
- **ADR-0013 — Kanban unificado cross-project.** Single board com chip de projeto + filtros multi-select. Trabalho cross-project é o caso real.

### 9.4. Roadmap em fases

Cada fase termina **demonstrável + verde nas três camadas de teste**.

| Fase | Status | Entrega |
|---|---|---|
| **F0** | ✅ | Esqueleto + harness: `make up` sobe daemon + UI, `make test-all` verde com sentinelas |
| **F1** | ✅ | Spawn isolado: listar projetos/worktrees, botão "Nova sessão" abre Claude Code dentro de ai-jail |
| **F2** | ✅ | Status semântico via hooks: cards mostram `awaiting_response` / `idle` em tempo real |
| ~~F3~~ | ❌ cancelada | Fundida em F2 (ADR-0011) |
| **F4** | ✅ | Backlog kanban cross-project |
| **F5** | ✅ | Mapa de worktrees + multi-repo |
| **F6** | ✅ | Run from Panel: ▶ Run sobe stack via manifesto |
| **F7** | ✅ | Templates + perfis via catálogo curado |
| **F8** | ✅ | Sessão master Claude no sidebar (xterm + PTY + MCP) |
| **F9** | ✅ | UI redesign CIPHER (Tailwind v4 + shadcn/ui) |
| **F10** | ✅ | Pivot Go+Wails native: stack inteira migrada de Python+FastAPI pra Go 1.26 + Wails v2.12 com WebView embedando a UI React |
| **F10.6** | ✅ | Re-implementação de F6 em Go (RunsService + bootstrap por sessão Claude efêmera) |
| **F10.7** | ✅ | OS integration: system tray + single-instance D-Bus + close-to-tray + CLI `--focus` |
| **F10.8** | 🚧 em andamento | Cleanup (Python deletado) + packaging (.deb + .AppImage) |

**MVP = F0 → F10.8.**

### 9.5. Disciplina de qualidade

- **TDD obrigatório.** RED → GREEN → REFACTOR. Sem teste falhando antes, não escreve código de produção.
- **Costuras explícitas via interfaces Go** (`sandbox.Runtime`, `sandbox.DockerOps`, `events.Emitter`, `git.Ops`) — permite fake determinístico no unit, real no integration/E2E.
- **Pre-commit code review** via subagent — disciplina documentada em `~/.claude/CLAUDE.md` global.

### 9.6. Estrutura do repo

```
J-arvis/
├── go.mod
├── go.sum
├── Makefile
├── wails.json
├── main.go                       # Wails entry: options, OnStartup, OnShutdown
├── app.go                        # App struct + Wails bindings ctx
├── internal/
│   ├── api/                      # Wails-bound APIs (Tasks/Projects/Sessions/Runs/Master/Bootstrap/Catalog/Worktrees/Health)
│   ├── catalog/                  # YAML curado (templates + perfis) embedado
│   ├── core/                     # domínio: tasks, sessions, runs, bootstrap, master, port allocator, manifest
│   ├── events/                   # Wails emitter + FakeEmitter pra testes
│   ├── git/                      # WorktreeOps (subprocess git)
│   ├── hooks/                    # HTTP handler /api/hooks/<event>/<token>
│   ├── localhttp/                # 127.0.0.1:0 listener pra hooks + run logs SSE
│   ├── master/                   # PTY pra master Claude session
│   ├── mcp/                      # MCP server (JSON-RPC 2.0) pro master Claude
│   ├── osintegration/            # system tray + D-Bus single-instance + --focus CLI
│   ├── sandbox/                  # Runtime (ai-jail), DockerOps, settings.json, .ai-jail
│   └── store/                    # SQLite via modernc.org/sqlite + goose migrations
├── cmd/
│   └── jarvis-e2e-http/          # HTTP shim build (-tags e2e_http) pra Playwright
├── ui/                           # React + Tailwind v4 + shadcn/ui (compilado via Vite; embedado via //go:embed em main.go)
│   └── src/
└── docs/
    ├── adr/                      # decisões arquiteturais
    ├── os-integration/           # hotkey-binding.md, tray-setup.md
    └── superpowers/              # specs + plans históricos do roadmap
```

### 9.7. Bibliotecas-chave da UI

- **TanStack Query** — cache fino de requests, refetch automático em mutations.
- **Zustand** — estado local sem provider hell.
- **@dnd-kit/core + @dnd-kit/sortable** — drag & drop do kanban.
- **React 19 + Vite 6** — stack moderna, sem CRA legado.

### 9.8. Documentos de apoio para devs novos no projeto

| Arquivo | Quando ler |
|---|---|
| `ARCHITECTURE.md` | Antes de tocar qualquer código de domínio |
| `CONTEXT.md` | Pra entender as decisões originais (brainstorm) |
| `gotchas.md` | Antes de cair nos mesmos buracos do passado |
| `docs/adr/*.md` | Pra entender o **porquê** de cada decisão estruturante |
| `.orchestrator/run.yml` | Quando for mexer no Run from Panel |

---

## 10. Resumo executivo (TL;DR por audiência)

- **Negócio:** ferramenta local-first para dev solo/lead que opera múltiplos agentes Claude Code em paralelo. Modelo open-source agora; monetização provável via tier "time" em v2 ou marketplace de templates. Custo operacional do produto = zero (roda na máquina do usuário). Risco principal = dependência externa do `ai-jail`, com plano B desenhado.
- **Marketing:** posicionamento "Trello acoplado à sandbox para devs Claude Code". Diferenciação: sandbox-first + task-first. Não competimos com editores, competimos com orquestradores multi-agente (Crystal, Conductor, Claude Squad). Mensagem-âncora: "você não precisa lembrar de qual aba é qual — o kanban lembra".
- **Design:** UI tem **duas superfícies complementares** — o **kanban** (visual, drag & drop, status em tempo real via WebSocket) e a **sessão mestra** (conversacional, com skills que manipulam o backlog via linguagem natural). Os 4 objetos visuais do kanban (card, coluna, drawer de projeto/worktree, modal de detalhe) e o painel persistente da sessão mestra dividem a tela. Drag & drop é o verbo principal do kanban; conversa é o verbo principal da sessão mestra. Permissões ficam no terminal nativo do Claude — nem kanban nem sessão mestra duplicam esse caminho. Cross-project é caso default, single-project é filtro.
- **Desenvolvimento:** binário único Wails (Go 1.26) + UI React 19 + Tailwind v4 + SQLite via modernc.org/sqlite. TDD com interfaces Go (`sandbox.Runtime`, `sandbox.DockerOps`, `events.Emitter`) pra costuras. Sandbox via ai-jail externo, com `sandbox.Runtime` substituível. MVP em 10 fases (F0 → F10.8 em andamento — cleanup + packaging .deb/.AppImage).
