# Orquestrador Claude Code — contexto da sessão

Este documento consolida tudo que foi decidido em uma sessão de brainstorm
no Claude Code (web). A próxima sessão (CLI local) deve ler este arquivo
primeiro e continuar daqui.

## 1. Visão

Construir um **orquestrador local de Claude Code** que rode como daemon
sob demanda, sirva uma UI web no browser, e gerencie múltiplas sessões
do Claude Code rodando em jaulas isoladas (estilo `ai-jail`).

## 2. Problema

O usuário trabalha com várias abas de Claude Code abertas, em 2-3 projetos
diferentes, com worktrees diferentes em cada projeto. Resultado:

- Esquece o que cada aba está fazendo
- Dá informação errada porque perde contexto de qual sessão é qual
- Não sabe em qual estado está cada sessão (esperando resposta? terminou?)
- Precisa entrar manualmente em cada worktree pra rodar e testar o que o
  agente fez

## 3. Diferenciação

Não é "mais um Crystal/Nimbalyst/Conductor". As duas apostas que diferenciam:

1. **Sandbox-first de verdade** — isolamento estilo ai-jail integrado, não
   afterthought. Concorrência roda direto na máquina do usuário.
2. **Backlog/task-first em vez de session-first** — sessão é detalhe de
   implementação. O objeto primário é a task.

## 4. Decisões de infra (fechadas)

| Decisão | Escolha |
|---|---|
| Plataforma | Linux only (MVP) |
| UI | Web local (browser) |
| Daemon | On-demand (usuário inicia quando quer) |
| Multiusuário | Single-user |
| Sandbox | Estilo `ai-jail` (bwrap + Landlock + seccomp) — orquestrador roda **fora** da jaula, spawna sessões **dentro** |
| Permissões nas sessões | Bypass com blocklist (ex: `rm`) — sandbox é a defesa real |
| Notificações | Nativas do Ubuntu (`notify-send`/libnotify) |
| Comunicação com Claude Code | Hooks (`Notification`, `Stop`, `PreToolUse`) + leitura de transcript |
| Memória entre sessões | Já resolvido por `claude-mem` — não reimplementar |
| Audit log | Não fazer |
| Session replay | Não fazer |
| Mobile | Não no MVP |
| Agent Teams (Anthropic) | Não usar — 100% controle manual do usuário |
| Importação GitHub Issues | v2 |
| Integração Azure DevOps | Futuro (resolverá multi-user) |

## 5. Features no MVP

1. Daemon local + UI web
2. Spawn de sessões Claude Code, uma jaula por sessão
3. Detecção de status semântico via hooks: `aguardando aprovação`,
   `aguardando resposta`, `executando`, `idle`, `erro`, `done`
4. Notificações Ubuntu via `notify-send`
5. **Backlog kanban** com estados: `idea` → `ready` → `in_progress` →
   `review` → `done`
6. **Task como objeto primário** (sessão é só uma execução da task)
7. Templates de task (frontend/backend/refactor/bugfix) com perfil de
   permissão pré-aprovado
8. **Fila central de aprovações** — todas as solicitações de permissão
   caem em uma fila única, em vez de o usuário pular entre abas
9. **Mapa de worktrees** por projeto (árvore visual)
10. **Run from Panel** (ver seção 6)
11. **Bootstrap do manifesto** via Claude na 1ª vez que um projeto roda

## 6. Feature "Run from Panel" — design

Botão no card da worktree que sobe `db + seed + backend + frontend` e
abre URL no browser.

### 6.1 Manifesto por projeto

Arquivo `.orchestrator/run.yml` na raiz do projeto. Exemplo:

```yaml
services:
  db:
    type: postgres
    seed: ./scripts/seed.sh
  backend:
    cmd: npm run dev
    port: ${PORT_BACKEND}
    health: http://localhost:${PORT_BACKEND}/health
    depends_on: [db]
  frontend:
    cmd: npm run dev
    port: ${PORT_FRONTEND}
    open_in_browser: true
    depends_on: [backend]
```

Se o manifesto não existe, na 1ª execução o orquestrador pede ao Claude
pra ler o repo e propor um. Usuário revisa, salva, commita. Manifesto
vira parte do projeto.

### 6.2 Portas

- Orquestrador aloca portas dinâmicas (ex: 31000-31999) por execução
- Exporta como env: `PORT_FRONTEND`, `PORT_BACKEND`, `PORT_DB`
- Manifesto referencia `${PORT_*}`
- Painel mostra URL exata clicável

### 6.3 Banco

Container descartável por execução (`docker run --rm`), com cache de
imagem. Seed roda após health check passar.

### 6.4 Lifecycle

Estados: `building` → `seeding` → `ready` → `failed` / `stopped`.

UI por worktree:
- Botão ▶ Run / ■ Stop
- Status colorido por serviço
- Stream de logs colapsável
- URL grande quando `ready`
- Botão "Restart só backend" (e similares)

Auto-cleanup quando task vira `done`/`discarded`, ao fechar orquestrador,
ou TTL de idle.

### 6.5 Sandbox + rede

Ambiente roda dentro da mesma jaula da worktree:
- Rede só pra `localhost` da jaula
- Porta exposta pro host só pra UI
- Sem rede externa por padrão (libera no manifesto se seed precisar)

## 7. Planner meta-agente — design

Usuário joga um épico (ex: "adicionar OAuth Google em todos os serviços").
O planner:

1. Lê contexto (repo + backlog atual, evita duplicar)
2. Propõe plano: subtasks com título, descrição, arquivos afetados,
   dependências, template sugerido, estimativa S/M/L
3. Usuário revisa em tela "preview" — pode editar/remover/reordenar/mesclar
4. Aprovado → vai pro backlog em `ready` (ou `idea` se conservador)

**Importante:** o planner **nunca inicia** sessões sozinho. Só popula
backlog. O usuário continua sendo o gatilho.

v2: planner sugere ordem de execução considerando dependências e marca
o que dá pra paralelizar.

## 8. Features pós-MVP

**v1.5:**
- Detecção de conflitos entre worktrees (mesmo arquivo modificado em duas)
- Diff agregado (todos os in-flight em um lugar, agrupado por projeto)
- Auto-resumo da sessão (1 linha do que está fazendo agora)
- Custo por sessão / projeto / dia
- Planner meta-agente

**v2:**
- Importação GitHub Issues
- Integração Azure DevOps
- Mobile thin client (se voltar a fazer sentido)

## 9. Decisões pendentes (responder antes de codar)

1. **`Run from Panel`: manifesto explícito vs heurística pura** (detectar
   `docker-compose.yml`, scripts do `package.json`, `Procfile`).
   Recomendação: **manifesto + bootstrap por Claude**.
2. **DB strategy:** container descartável é OK? Usuário tem Docker no Ubuntu?
3. **Stack do daemon e UI:**
   - Python (FastAPI) + React/Vite
   - Node/TS (Fastify) + React
   - Rust (Axum) + React
   - Go + React
4. **Sandbox:** `bwrap` direto (estilo ai-jail) ou containers Docker como
   jaula? Recomendação: **bwrap** (mais leve, mais seguro).

## 10. Estado atual

- Repo: `marcosdid/teest`
- Branch: `claude/fresh-start-cleanup-XDaHV`
- Nenhum código escrito ainda. Só este documento.

## 11. Próximo passo (na próxima sessão)

1. Ler este documento por inteiro.
2. Pedir ao usuário pra responder as 4 perguntas pendentes da seção 9.
3. Com as respostas, escrever um documento curto de **arquitetura
   técnica** + **roadmap em fases** (ainda sem código).
4. Só começar a codar depois de aprovação explícita.

## 12. Referências úteis

- `ai-jail` (Akita): https://github.com/akitaonrails/ai-jail
- Crystal/Nimbalyst: https://github.com/stravu/crystal
- Conductor: https://conductor.build
- Claude Squad: wrapper tmux para multi-agente
- ccmanager: TUI multi-agente (Claude/Gemini/Codex/Cursor)
- `claude-mem`: plugin que o usuário já usa pra memória compartilhada
