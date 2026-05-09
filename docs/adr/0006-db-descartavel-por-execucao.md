# ADR-0006: DB do Run from Panel — container Docker descartável por execução

- **Status:** Accepted
- **Data:** 2026-05-08
- **Decisores:** Marcos

## Contexto

Ao rodar uma worktree pelo "Run from Panel", o ambiente típico inclui
um banco (Postgres na maioria dos projetos do usuário). Uma das
dores explícitas é "estado vazado entre execuções": iniciar uma
sessão de teste e encontrar dados de uma execução anterior, ou
schema inconsistente após migration falhada.

O Docker já está instalado na máquina alvo. uv, ai-jail e Node
também. Não há restrição operacional para usar Docker.

## Decisão

Cada execução de Run from Panel sobe um **container Docker
descartável** (`docker run --rm`) para o DB, com cache de imagem.
Seed roda **após** o health check passar.

O ciclo de vida do DB é amarrado ao `RunInstance`:

- **Start:** container sobe com nome único, porta dinâmica, env vars
  isolados.
- **Health:** orquestrador espera porta + query trivial responder.
- **Seed:** script declarado no manifesto roda contra o container.
- **Stop:** quando `RunInstance` termina (task done, usuário clicou
  Stop, TTL idle), container é removido. `--rm` garante cleanup
  mesmo em crash.

A imagem é cacheada no host pra reuso entre execuções (segundo Run
não baixa Postgres de novo).

## Alternativas consideradas

1. **Postgres local persistente compartilhado** com vários DBs
   nomeados por worktree. Rejeitado: estado vaza entre runs e seed
   precisa de cleanup manual; um DB corrompido contamina os outros.
2. **Configurável por projeto via manifesto** (`docker | local |
   externo`). Adiada: se o usuário tiver projetos com DB legado já
   rodando externamente, abrimos isso depois como extensão do
   manifesto. MVP fica em "docker descartável".

## Consequências

**Positivas**
- Estado limpo determinístico a cada Run. Nenhum efeito colateral
  entre execuções da mesma worktree ou entre worktrees diferentes.
- Cache de imagem amortiza o custo do `docker pull`.
- Seed sempre roda contra DB virgem — bugs de seed aparecem cedo, não
  na 7ª execução.

**Negativas**
- Cold start do DB toda vez. Mitigado pelo cache + healthcheck rápido
  para Postgres (~2-3s).
- Dados criados em uma sessão **somem** ao parar — esperado para
  ambiente de dev/teste, mas exige educação inicial.
- Dependência hard de Docker no host para qualquer worktree que tenha
  DB declarado no manifesto.

**Neutras**
- Quando F1+ trouxer projetos sem DB (apenas backend in-memory), o
  manifesto pode omitir `services.db` e Run from Panel funciona sem
  Docker.

## Referências

- `ARCHITECTURE.md` §6.3 (Banco)
- `CONTEXT.md` §6.3
- ADR-0005 (manifesto explícito)
