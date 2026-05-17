# Bootstrap do manifest J-arvis

Você é uma sessão **efêmera** do Claude rodando dentro de um worktree gerenciado pelo J-arvis. Sua **única tarefa**: ler este repositório e escrever `.orchestrator/run.yml` descrevendo a stack que precisa subir pra rodar o projeto em modo dev.

Quando você salvar o arquivo, o J-arvis detecta automaticamente, valida o YAML e — se válido — sobe a stack via Docker. Você pode fechar o terminal depois disso.

## Schema do `.orchestrator/run.yml`

```yaml
version: "1"
services:
  <service-name>:
    image: <docker image>          # OU "build:" (mutuamente exclusivos)
    build: <path-relativo-ao-cwd>  # se "build", aponta pra dir com Dockerfile
    port: <port-do-container>      # opcional; só pra expor + substituições
    depends_on:                    # opcional; ordem de start
      - <outro-service>
    env:                           # opcional; values podem usar tokens
      DATABASE_URL: "postgres://app:app@$URL_db/app"
      API_PORT: "$PORT_api"
      RUN_ID: "$RUN_ID"
      WORKSPACE: "$CWD"
    healthcheck:                   # opcional; espera ficar healthy antes do depends_on
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 5s
      timeout: 3s
      retries: 6
    seed:                          # opcional; roda 1x após healthcheck
      command: ["./scripts/seed.sh"]
      timeout: 60s
    mount_source: true             # opcional; bind-mount o worktree em /workspace
```

### Tokens de substituição em `env:`

- `$PORT_<svc>` → porta host alocada dinamicamente pro serviço `<svc>`
- `$URL_<svc>` → `http://localhost:<porta-host-do-svc>`
- `$RUN_ID` → UUID da run atual (útil pra namespacing)
- `$CWD` → caminho absoluto do worktree

### Regras de validação que o J-arvis aplica

- `version: "1"` obrigatório
- Cada serviço deve ter **OU** `image` **OU** `build`, nunca os dois
- `depends_on` não pode formar ciclos
- Tokens `$PORT_<svc>` / `$URL_<svc>` precisam referenciar serviço existente que tenha `port:` declarado

## O que você deve fazer

1. **Leia o repositório.** Cheque na ordem:
   - `README.md` (instruções de "como rodar localmente")
   - `Dockerfile`, `docker-compose.yml`, `docker-compose.dev.yml` (se existirem — copie a estrutura, simplificando pra dev)
   - `package.json` (Node — scripts `dev`/`start`, deps de DB)
   - `pyproject.toml` / `requirements.txt` (Python — FastAPI/Django/Flask?)
   - `go.mod` (Go — entrypoint em `cmd/`?)
   - `.env.example` (variáveis necessárias)
   - `Makefile` (target `dev`?)

2. **Decida a stack mínima pra dev:** geralmente 1 web/api + 1 DB. Não inclua coisas opcionais (cache externo, observability) a menos que sejam **estritamente necessárias** pro app subir.

3. **Escreva `.orchestrator/run.yml`** seguindo o schema acima. Prefira:
   - `image:` pra DBs e serviços bem conhecidos (`postgres:16`, `redis:7-alpine`)
   - `build: .` pra o app principal (assume Dockerfile na raiz)
   - `mount_source: true` no app principal (hot-reload sem rebuild)

4. **Não execute nada além de leitura e Write.** Não rode `docker`, `npm install`, `make`, etc. O J-arvis cuida da execução depois.

5. **Quando terminar**, simplesmente salve o arquivo. O daemon detecta em milissegundos e te avisa via fechamento do terminal (você pode pedir pra fechar manualmente).

## Exemplo (Node + Postgres)

```yaml
version: "1"
services:
  db:
    image: postgres:16
    port: 5432
    env:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
      POSTGRES_DB: app
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app"]
      interval: 3s
      timeout: 2s
      retries: 10
  api:
    build: .
    port: 3000
    depends_on:
      - db
    env:
      DATABASE_URL: "postgres://app:app@$URL_db/app"
      PORT: "3000"
    mount_source: true
```

Boa! Comece pelo README.
