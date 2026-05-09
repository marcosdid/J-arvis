# ADR-0008: Sessão de Claude Code abre em terminal nativo do desktop

- **Status:** Accepted
- **Data:** 2026-05-08
- **Decisores:** Marcos

## Contexto

Quando o orquestrador spawna uma sessão Claude Code dentro de uma jaula
`ai-jail`, o processo fica vivo mas **sem janela de terminal** ligada
(o daemon é um servidor web, não tem TTY). Precisamos decidir como o
usuário **conversa** com essa sessão.

Quatro caminhos foram considerados (ver discussão na sessão de
F1-design):

1. tmux detached + `tmux attach` manual.
2. Embed xterm.js no browser via WebSocket + PTY.
3. Spawnar uma janela do terminal emulator nativo do desktop
   (gnome-terminal, Konsole, kitty, etc.).
4. Headless-only: sessão roda sem UX de chat; F2+ hooks fazem
   automação com fila central de aprovações.

Restrições do MVP (per ADR-0001 e CONTEXT.md): single-user, local-only,
Linux-only, daemon roda na mesma máquina onde o usuário trabalha. Há
display gráfico disponível (X11 ou Wayland).

## Decisão

Em F1, o daemon spawna a sessão **dentro de uma janela do terminal
emulator do usuário** (gnome-terminal, Konsole, etc.).

Estratégia de detecção:

1. Se `JARVIS_TERMINAL` (env var) estiver setado, usa esse comando
   exato.
2. Senão, varre `$PATH` na ordem: `gnome-terminal`, `konsole`,
   `xfce4-terminal`, `kitty`, `alacritty`, `foot`, `tilix`,
   `terminator`, `xterm`.
3. Se nada for encontrado, retorna erro estruturado sugerindo setar
   `JARVIS_TERMINAL`.

Cada terminal exige flags diferentes pra "rodar este comando dentro";
o daemon mantém um pequeno mapa por nome:

```python
TERMINAL_LAUNCH = {
    "gnome-terminal": ["--", *cmd],
    "konsole":        ["-e", *cmd],
    "kitty":          [*cmd],
    "alacritty":      ["-e", *cmd],
    # ...
}
```

**Lifecycle:** fechar a janela do terminal **encerra a sessão**
(processo Claude morre junto com a shell que o terminal hospedava).
O daemon detecta via `Process.poll()` e marca `Session.status="done"`.
O botão "Stop" da UI envia SIGTERM ao processo da sessão; o terminal
fecha junto.

## Alternativas consideradas

1. **tmux detached.** Rejeitada para F1: usuário não-Linux-power-user
   precisaria aprender `Ctrl+B D` pra detach. Pode voltar como F1.5
   se a UX nativa virar limitante.
2. **xterm.js embedded.** Rejeitada para F1: ~50-100% de código
   adicional (lib JS + lib PTY no Python + protocolo WS binário +
   resize/focus/copy). Adia o resto do F1 demais. Pode voltar como
   upgrade UX em fase posterior se o terminal nativo virar atrito.
3. **Headless-only.** Rejeitada: F1 perde a demo "vejo o Claude
   trabalhando", o que é o ponto da fase. F2+ hooks complementam
   sem substituir a UX de chat humano.

## Consequências

**Positivas**
- UX "mágica no clique": daemon abre janela já com a sessão rodando.
- Zero código novo de PTY/WebSocket/terminal-em-browser.
- Familiaridade: usuário usa o terminal que já gosta, com cores,
  fontes e atalhos preservados.
- Hooks (F2+) funcionam normalmente em paralelo — são independentes
  do terminal usado.

**Negativas**
- Dependente de display gráfico no host. **Não funciona em SSH puro
  ou servidor headless.** Aceitável: orquestrador é local-only por
  design (ADR-0001 e §1).
- Cada terminal emulator suportado vira código de mapping. Fácil de
  adicionar novos, mas é manutenção contínua se a comunidade pedir.
- Fechar a janela = matar a sessão. Usuário precisa **clicar Stop na
  UI** ou **Ctrl+D** dentro da sessão pra encerrar limpo. Fechar o
  X agressivamente envia SIGHUP, que mata Claude. Documentar.
- Pra observar a sessão em duas telas, o usuário não tem como —
  diferente do que tmux daria. Trade-off aceitável em MVP.

**Neutras**
- Configuração via `JARVIS_TERMINAL` permite usuários com terminais
  exóticos (foot em Sway, wezterm, etc.) sem patch no daemon.
- Quando F2 trouxer hooks autônomos, parte do uso pode migrar pra
  "Claude trabalha sozinho, eu só aprovo via UI", o que reduz a
  pressão sobre a UX de terminal nativo.

## Referências

- `ARCHITECTURE.md` §11 (F1 — Spawn isolado)
- ADR-0001 (sandbox-first, ai-jail)
- ADR-0007 (task-first; sessão é detalhe de execução)
