# ADR-0004: TDD como regra de ferro com 100% de cobertura em três camadas

- **Status:** Accepted
- **Data:** 2026-05-08
- **Decisores:** Marcos

## Contexto

O orquestrador é uma ferramenta crítica para o usuário (gerencia
sessões com permissões e capacidade de mexer em código de produção).
Um bug de regressão no painel de aprovações ou no spawn de sessões
pode causar dano real. Single-user e local não muda isso.

Sem testes automatizados completos, qualquer mudança vira potencial
regressão silenciosa, e o ciclo de "Claude Code edita, manualmente
clica e confere" não escala com a quantidade de features planejadas.

## Decisão

**Disciplina TDD estrita** em todo o projeto:

1. **RED:** escrever o teste primeiro, vê-lo falhar pelo motivo certo.
2. **GREEN:** código mínimo que faz passar.
3. **REFACTOR:** limpar mantendo verde.

Sem exceção: código de produção sem teste falhando antes é apagado e
refeito. Configuração e scaffold são exceções (não há lógica).

**Três camadas de cobertura, todas com alvo de 100%:**

| Camada | Stack | Escopo |
|---|---|---|
| Unit | `pytest` + `pytest-asyncio` + `coverage.py` | Lógica de domínio sem I/O |
| Integration (rotas) | `pytest` + `httpx.AsyncClient` + `testcontainers-python` | FastAPI real + DB real |
| E2E (fluxos UI) | `Playwright` + `testcontainers` | Stack inteira em container |
| Frontend unit | Vitest + RTL | **Apenas** `src/lib/` e `src/hooks/` |

`# pragma: no cover` admitido para linhas defensivas inalcançáveis
(`raise NotImplementedError` em Protocol, branches `match _:`
exaustivos, blocos guard de plataforma). O alvo de 100% é literal
sobre o conjunto **não-excluído**.

## Alternativas consideradas

1. **TDD pragmático ("escreve teste depois quando for crítico").**
   Rejeitada: testes-depois confirmam o que existe, não o que
   *deveria* existir. Sem ver o RED, não sabemos se o teste de fato
   testa.
2. **Cobertura 80% + test pyramid clássica.** Rejeitada: limites
   arbitrários geram negociação por linha. 100% literal força
   conversa sobre o que excluir, não sobre que linha "vale a pena".
3. **E2E only / sem unit.** Rejeitada: E2E é caro e lento; unit pega
   regressão de lógica em milissegundos.

## Consequências

**Positivas**
- Cada feature termina demonstrável + verde nas 3 camadas. Definition
  of Done explícito.
- Refatoração agressiva fica segura — testes catch regressão.
- Documentação viva: tests mostram como usar cada componente.

**Negativas**
- Setup inicial pesado (F0 dedicado a harness). Já pago.
- Coverage 100% obriga design testável — toda I/O via `Protocol` ou
  fica não-coberta. Custo é positivo no longo prazo.
- E2E com testcontainers é lento (~30s por teste após cache, ~3min
  rebuild). Compensa com `make test-unit` e `make test-int` durante o
  loop de dev, e `make test-all` antes de fechar feature.

**Neutras**
- Frontend unit cobre só lógica pura. Componentes de apresentação são
  validados via E2E. Decisão consciente para evitar testar
  re-render trivial.

## Referências

- `ARCHITECTURE.md` §8 (Disciplina) e §9 (Camadas de cobertura)
- `pyproject.toml` (`tool.coverage.report`)
- `Makefile` (`coverage`, `test-all`)
