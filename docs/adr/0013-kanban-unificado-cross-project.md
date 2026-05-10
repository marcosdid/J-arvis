# ADR-0013: Kanban unificado cross-project com filtros

- **Status:** Accepted
- **Data:** 2026-05-09
- **Decisores:** Marcos

## Contexto

Layout original do brainstorming F4 era kanban POR projeto (project
picker no topo, swap entre kanbans). Ao discutir, ficou claro que
trabalhar em múltiplos projetos simultaneamente é o caso real;
context-switching entre kanbans desorganiza fluxo.

## Decisão

Kanban único cross-project. Cada card mostra **chip colorido** com
nome do projeto (cor por hash determinístico do `project_id` em
paleta fixa de 8). Filtros multi-select no header (chips clicáveis)
permitem incluir/excluir projetos. Estado de filtros persiste em
`localStorage["jarvis.kanban.filters"]`. IDs ausentes silenciosamente
filtrados ao ler (sem cleanup explícito).

Projetos e worktrees ficam num **drawer lateral** acionado por
botão "Projetos ▾" — mantém UX existente de F1 sem ocupar tela.

## Alternativas

1. Kanban por projeto (rejeitada): força swap, perde contexto.
2. Kanban híbrido (badge global + per-project): scope creep.

## Consequências

- Schema/API independente de projeto (Task carrega `project_id`).
- Cor do chip não persiste no DB (derivada do id via hash).
- Drawer encapsula complexidade de project/worktree mgmt.
- Filtros são single-user / local — não há server-side state.

## Referências

- Spec F4 §6.1, decisões #3, #11, #15, #17
- ADR-0001 (single-user / local-only)
