# ADR-0007: Modelo de domínio — task-first em vez de session-first

- **Status:** Accepted
- **Data:** 2026-05-08
- **Decisores:** Marcos

## Contexto

Ferramentas similares (Crystal, Conductor, ccmanager) tratam **sessão**
como objeto primário: você abre uma sessão, conversa com ela, fecha.
A UI gira em torno de "abas de sessão".

A dor real do usuário não é "estou perdendo abas" — é
"estou perdendo o **trabalho**". Várias abas viram orfãs porque ele
esquece o que cada sessão estava fazendo, em qual worktree, em qual
estado. A unidade de trabalho é a *intenção* (refatorar X, adicionar
feature Y), não o processo Claude que está executando.

## Decisão

**`Task` é o objeto primário** do sistema. Sessão é detalhe de
implementação de uma task.

- UI gira em torno de tasks: kanban com `idea → ready → in_progress →
  review → done`.
- Cada task pode ter zero, uma ou várias sessões (retry, continuação,
  bifurcação).
- Templates de task (frontend/backend/refactor/bugfix) carregam perfil
  de permissão pré-aprovado.
- Métricas, custo, histórico tudo agrupa por task primeiro, sessão
  depois.

```
Task ─┬─ Session (active)
      ├─ Session (failed, replaced)
      └─ Session (resumed)
```

Sessão sem task é considerada "rascunho/ad-hoc" e pode existir, mas
não aparece no backlog principal.

## Alternativas consideradas

1. **Session-first (igual aos competidores).** Rejeitado: replica a
   mesma dor que motivou o projeto.
2. **Issue-first** (importar GitHub Issues como tasks). Adiada para
   v2 — é uma fonte de tasks, não o modelo central.

## Consequências

**Positivas**
- O painel de aprovações pode agrupar por task: "esta task tem 3
  pedidos de tool em fila" vira informação navegável.
- Continuar trabalho amanhã é trivial: abrir a task, criar nova
  sessão a partir dela, contexto preservado via `claude-mem`.
- Custo/tempo por **objetivo** (task), não por "ferramenta de chat".

**Negativas**
- UX inicial mais cerimoniosa: precisa criar a task antes de spawnar
  sessão. Mitigado por templates rápidos e atalho "criar task vazia
  + iniciar sessão".
- Mais código de modelo: precisa lidar com Task↔Session 1:N e estados
  de transição.

**Neutras**
- Importação futura de GitHub Issues / Azure DevOps encaixa
  naturalmente: cada issue vira uma task.

## Referências

- `ARCHITECTURE.md` §1 (Princípios) e §3 (Modelo de dados)
- `CONTEXT.md` §3 (Diferenciação)
