# ADR-0005: Run from Panel — manifesto explícito com bootstrap por Claude

- **Status:** Accepted
- **Data:** 2026-05-08
- **Decisores:** Marcos

## Contexto

A feature "Run from Panel" sobe `db + seed + backend + frontend` de uma
worktree e abre a URL no browser. Cada projeto tem stack diferente:
node + python + go, com vários scripts em `package.json`,
`docker-compose.yml`, `Procfile`, etc. Como o orquestrador descobre
**como** subir o ambiente?

Duas escolhas: detectar tudo automaticamente (heurística), ou exigir
declaração explícita do projeto (manifesto).

## Decisão

**Manifesto explícito** em `.orchestrator/run.yml` na raiz do projeto.
Esse arquivo é commitado e vira parte do projeto.

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

**Bootstrap por Claude:** se o manifesto não existe na 1ª execução, o
orquestrador dispara uma sessão Claude efêmera com o prompt "leia o
repo e proponha um manifesto". O usuário revisa, salva, commita.

Portas dinâmicas em `31000-31999` por execução, exportadas como
`PORT_FRONTEND`, `PORT_BACKEND`, `PORT_DB`. O manifesto referencia via
`${PORT_*}`.

## Alternativas consideradas

1. **Heurística pura** (detectar `docker-compose.yml`, `Procfile`,
   scripts do `package.json`). Rejeitada: frágil sempre que o projeto
   foge do padrão. Cada exceção vira branch de código no orquestrador.
2. **Híbrido (heurística com fallback manifesto).** Rejeitada por
   complicar o modelo mental: dois caminhos pra entender o que vai
   subir. Manifesto único é mais previsível.

## Consequências

**Positivas**
- Reproduzibilidade: o que sobe é exatamente o que está commitado.
- Novos contribuidores têm uma fonte única de verdade pra subir o
  projeto local.
- O bootstrap por Claude resolve o "atrito da 1ª execução" sem
  inflar o orquestrador com heurísticas.

**Negativas**
- Cada projeto novo precisa de um `.orchestrator/run.yml`. O
  bootstrap mitiga, mas é um arquivo extra.
- Forma do manifesto vira parte do contrato do orquestrador. Mudanças
  breaking exigem migração ou superseder este ADR.

**Neutras**
- Seed com rede externa (caso do `npm install` em seed) precisa de
  flag explícita no manifesto pra abrir egress da jaula.

## Referências

- `ARCHITECTURE.md` §6 (Run from Panel)
- `CONTEXT.md` §6
