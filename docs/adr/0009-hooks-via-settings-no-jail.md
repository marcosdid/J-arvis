# ADR-0009: Registro de hooks via `settings.json` injetado dentro do jail

- **Status:** Accepted
- **Data:** 2026-05-09
- **Decisores:** Marcos

## Contexto

F2 precisa que o `claude` rodando dentro da jaula `ai-jail` chame
endpoints HTTP do daemon a cada evento de hook (`Notification`,
`PreToolUse`, `Stop`). O Claude Code lê configuração de hooks de
`<projeto>/.claude/settings.json` (entre outros caminhos), e cada hook
é definido como um comando shell — não uma URL diretamente. Pra apontar
pro daemon, o comando precisa ser tipo `curl -X POST http://localhost:<port>/api/hooks/<event>/<token>`
lendo o payload do stdin.

Quatro alternativas foram consideradas:

1. **Settings global em `~/.claude/settings.json`**: usuário configura
   uma vez. Vantagem: zero código no daemon. Desvantagem: vaza pra
   Claude Code rodando **fora** do J-arvis (sessões manuais, scripts);
   o daemon precisaria lidar com tokens "desconhecidos" pra qualquer
   hook que não veio dele.
2. **Wrapper shim `j-arvis-claude`**: binário próprio que escreve
   settings.json temp em `$TMPDIR`, exporta `CLAUDE_CONFIG_DIR` e
   `execve("claude")`. Limpo, mas adiciona binário extra e checagem de
   versão a cada release do Claude Code.
3. **Settings por worktree**: daemon escreve `<worktree>/.claude/settings.json`
   antes de invocar `ai-jail run`. Worktree é bind-montada dentro da
   jaula no mesmo path absoluto, então o Claude lê `./.claude/settings.json`
   relativo ao `cwd`.
4. **Config dentro do `.ai-jail`**: daemon configura a invocação do
   ai-jail (env var, mount adicional) pra injetar settings.json dentro
   da jaula.

## Decisão

Adotamos a alternativa **3** (settings por worktree, escrito antes do
spawn) com semântica "dentro da jaula": como ai-jail bind-monta a
worktree no mesmo path absoluto, escrever em `<worktree>/.claude/settings.json`
no host equivale a escrever dentro da jaula sob a perspectiva do Claude.

Implementação concreta:

- `orchestrator/sandbox/settings_writer.py` expõe:
  - `build_settings_json(token, base_url)` — JSON com 3 hooks
    (`Notification`, `PreToolUse`, `Stop`) cujo `command` é
    `curl -sS -X POST '<base_url>/api/hooks/<event>/<token>' --data-binary @-`.
    `PreToolUse` usa `; exit 0` no fim pra **nunca bloquear** Claude
    durante F2 (F3 traz a fila de aprovações).
  - `write_settings_into_jail(worktree, token, base_url)` — escreve com
    chmod 0o644.
  - `remove_settings_from_jail(worktree)` — `unlink(missing_ok=True)`.
  - `ensure_gitignore_entry(worktree)` — adiciona idempotente a linha
    `.claude/settings.json` ao `<worktree>/.gitignore`.
- `AiJailRuntime.spawn(worktree, *, token, base_url)`: quando ambos
  `token` e `base_url` são fornecidos, escreve settings + atualiza
  gitignore antes do spawn.
- `AiJailRuntime.kill(handle, *, worktree=None)`: quando `worktree`
  fornecida, remove settings após o kill (idempotente em
  `ProcessLookupError`).
- `start_session` / `stop_session` em `core/sessions.py` recebem
  `token_registry` opcional; quando presente, geram/registram/revogam
  tokens automaticamente.

## Alternativas consideradas

1. **Settings global (`~/.claude/`)**: rejeitada — vaza pra usos do
   Claude fora do J-arvis e força lógica de "token desconhecido" no
   handler.
2. **Wrapper shim**: rejeitada — adiciona um binário/checksum a manter
   e quebra se o Claude Code mudar a interface de config.
3. **Config no `.ai-jail`**: rejeitada — amarra a estratégia ao formato
   do ai-jail, e nosso ADR-0001 prevê substituir o `ai-jail` por wrapper
   próprio no futuro. A solução por worktree é independente do backend
   de sandbox.

## Consequências

**Positivas**

- Zero pegada em `~/.claude/` do usuário.
- Sessões fora do J-arvis não são afetadas — settings.json vive na
  worktree daquela sessão específica.
- `.gitignore` automático evita commit acidental do token.
- Compatível com o ADR-0001 (`SessionRuntime` Protocol): se trocarmos
  ai-jail por outra coisa, basta a nova implementação chamar o mesmo
  `settings_writer`.

**Negativas**

- Cada `start_session` faz 2 escritas em disco (settings.json + gitignore).
  Trivial em volume.
- O ai-jail precisa permitir egress pra `localhost:<port>` (validado
  na fase de impl). Se não permitir, precisa ADR-0011 com workaround.
- Settings.json sobrevive a crashes (cleanup só roda em `stop_session`
  ou detecção de processo morto). Aceitável: na próxima `start_session`
  o arquivo é sobrescrito.

**Neutras**

- Caminho idêntico dentro/fora da jaula (`<worktree>/.claude/settings.json`)
  facilita debugging — o usuário pode inspecionar o arquivo no host.

## Referências

- Spec: `docs/superpowers/specs/2026-05-09-f2-hooks-status-semantico-design.md` §4.3
- ADR-0001 (Sandbox via ai-jail externo)
- ADR-0008 (Terminal nativo do desktop)
