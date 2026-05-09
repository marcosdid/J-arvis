# Gotchas

Aprendizados convertidos em regras. Reler no início de cada sessão.

## 1. `uv sync` precisa do pacote já existindo

**Regra:** crie a estrutura de diretórios do pacote (`orchestrator/__init__.py`)
**antes** do primeiro `uv sync`. Se rodar antes, o `dist-info` é gerado mas
sem `.pth`, e o pacote não fica importável.

**Como detectar:** `uv pip list` mostra o pacote como instalado, mas
`pytest` falha com `ModuleNotFoundError: No module named '<pkg>'`.

**Como aplicar:** se você esquecer e cair nesse buraco, rode
`uv sync --reinstall-package <pkg>` para regenerar o editable. Aparece um
arquivo `_editable_impl_<pkg>.pth` em `.venv/lib/.../site-packages/`.

## 2. pnpm 11 guarda aprovação de build em `pnpm-workspace.yaml`

**Regra:** ao precisar de build script (caso típico: `esbuild`), rode
`pnpm approve-builds <pkg>` e **commite** o `pnpm-workspace.yaml`
gerado. Em Dockerfile, o `COPY ui/` precisa incluir esse arquivo.

**Como detectar:** `[ERR_PNPM_IGNORED_BUILDS] Ignored build scripts:
esbuild@x.y.z` durante `pnpm install`. Configurações em
`package.json#pnpm.allowBuilds` ou `package.json#pnpm.onlyBuiltDependencies`
**não são suficientes** sozinhas.

**Como aplicar:** Dockerfile multi-stage com UI usar `ENV CI=true` no
stage de build (evita prompt de purge de `node_modules`) e copiar
`ui/pnpm-workspace.yaml` junto com `package.json` e `pnpm-lock.yaml`.

## 3. Stub TDD-mínimo pode mascarar testes não-escritos

**Regra:** quando o stub mínimo aceita um parâmetro mas devolve valor
fixo (ex: `formatStatus(_status) → "Em execução"`), **o próximo ciclo
TDD precisa começar por um teste para um input diferente** que force a
ramificação. Senão, futuras chamadas com strings diferentes passarão
silenciosamente devolvendo o valor errado.

**Como detectar:** se `_status` ainda tem underscore após F0,
qualquer chamada nova precisa de teste novo antes de remover o
underscore.

**Como aplicar:** ao estender uma função stub, antes de tocar a
implementação, escreva o teste para o NOVO input e confirme RED. Só
depois adicione a ramificação.

## 4. Vitest 2 e Vite 6 têm conflito de tipos

**Regra:** se o `vite.config.ts` exporta config com chave `test:`, use
Vitest 3 com Vite 6. Vitest 2 traz tipos de Vite 5 e quebra em
`defineConfig({ plugins: [...], test: {...} })`.

**Como detectar:** erro TS `Object literal may only specify known
properties, and 'test' does not exist in type 'UserConfigExport'`,
ou conflitos de tipo entre `Plugin<any>` de versões diferentes.

**Como aplicar:** ao montar UI nova com Vite ≥6, fixar
`@vitest/coverage-v8` e `vitest` em `^3` no `package.json`. Importar
`defineConfig` de `'vitest/config'`, não de `'vite'`.
