# ADR-0001: Sandbox via ai-jail externo, com `SessionRuntime` abstrato

- **Status:** Accepted
- **Data:** 2026-05-08
- **Decisores:** Marcos

## Contexto

O orquestrador precisa rodar múltiplas sessões do Claude Code concorrentes
na mesma máquina, com isolamento real (FS, rede, processos, capacidades).
Essa é uma das duas apostas que diferenciam o produto de soluções
existentes (Crystal/Conductor): "sandbox-first de verdade".

Construir um wrapper kernel-level próprio (bwrap + Landlock + seccomp) é
caro: exige expertise de segurança de sistema operacional, testes
extensos contra escapes, manutenção contínua. O `ai-jail` (Fabio Akita)
já entrega exatamente esse stack, é open-source, leve, e está
**instalado na máquina de desenvolvimento** (`/usr/local/bin/ai-jail`).

## Decisão

Usar `ai-jail` como **dependência externa do host** para criar a jaula
de cada sessão. O orquestrador roda **fora** da jaula e invoca
`ai-jail run -- claude-code <args>` para spawnar sessões.

A integração é mediada por uma abstração `SessionRuntime`:

```python
class SessionRuntime(Protocol):
    async def spawn(self, worktree: Path, profile: PermissionProfile) -> JailHandle: ...
    async def kill(self, handle: JailHandle) -> None: ...
```

A implementação default (`AiJailRuntime`) shell-out para o binário. Se
no futuro o `ai-jail` se mostrar limitante (perf, configurabilidade,
bugs), trocamos por uma implementação própria por trás da mesma
interface — zero ripple no resto do código.

## Alternativas consideradas

1. **Construir nosso próprio wrapper bwrap+Landlock+seccomp.** Rejeitada
   por YAGNI: caro de fazer e manter; `ai-jail` já é exatamente isso.
2. **Containers Docker como jaula.** Rejeitada: mais pesado, depende do
   daemon Docker, e o isolamento de FS/processo é menos granular que
   Landlock para o caso "rodar binário arbitrário com acesso restrito".
3. **Misto: bwrap pra sessão + Docker pro Run from Panel.** Rejeitada
   pra MVP: dois mecanismos de isolamento dobram código de orquestração.
   Run from Panel já roda *dentro* da mesma jaula da worktree.

## Consequências

**Positivas**
- Zero código de baixo nível no MVP.
- Bug fixes do `ai-jail` chegam de graça via `apt`/`brew`/release.
- Linux-only é uma decisão alinhada com a plataforma escolhida (não
  perdemos cross-platform por isso).

**Negativas**
- Dependência externa instalada no host. Onboarding precisa documentar
  como instalar `ai-jail`.
- Configuração do `ai-jail` é via TOML-ish (`.ai-jail`), não Python.
  Geramos o arquivo programaticamente quando spawnar a sessão.

**Neutras**
- A abstração `SessionRuntime` é leve (~3 métodos) e mesmo se a
  substituição nunca acontecer, o custo da abstração é desprezível.

## Referências

- `ARCHITECTURE.md` §5 (Sandbox)
- `CONTEXT.md` §4 (decisões de infra) e §9.4
- ai-jail: https://github.com/akitaonrails/ai-jail
