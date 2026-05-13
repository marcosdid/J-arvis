# F10 Block A — Wails Bootstrap + Store + Tasks Vertical Slice (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bootstrap a Wails v2 desktop app for J-arvis that opens a native window rendering the existing F9 React UI, ports the SQLite store + Alembic migrations to Go (sqlite-modernc + goose), and ships a working end-to-end vertical slice for Tasks (create, list, move between kanban columns, discard) — replacing `fetch('/api/tasks')` with `await TasksAPI.X()` Wails bindings and `new WebSocket('/ws')` with `runtime.EventsOn('task.*', cb)`.

**Architecture:** A single Go binary embeds the React UI via Wails (`webkit2gtk` on Linux). The frontend (`ui/`) is unchanged visually; only `ui/src/lib/api.ts` and `ui/src/lib/ws.ts` are rewritten. Go domain lives in `internal/{api,core,store,events}` following the layout locked in the design spec §5. TDD per ADR-0004 — every step in this plan is RED → GREEN → COMMIT with table-driven Go tests, `httptest` for HTTP boundaries, and Vitest for the front.

**Tech Stack:**
- Go 1.22+
- Wails v2 (`github.com/wailsapp/wails/v2`)
- SQLite via `modernc.org/sqlite` (pure Go, no cgo)
- Migrations via `github.com/pressly/goose/v3`
- Test: `testing` stdlib + `-race` flag; coverage via `go test -coverprofile`
- Lint: `gofmt`, `go vet`, `staticcheck`, `golangci-lint`
- Frontend untouched: React 19 + Tailwind v4 + shadcn (F9 baseline)

**Reference docs (read before starting):**
- `docs/superpowers/specs/2026-05-12-pivot-go-wails-native-design.md` — the spec this plan implements
- `ARCHITECTURE.md` §3 (data model), §10 (test seams) — port targets
- `alembic/versions/*.py` — migrations to convert
- `orchestrator/store/*.py`, `orchestrator/core/*.py`, `orchestrator/api/tasks.py` — Python reference impl

**Branch:** `feat/f10-native-app` (created from `feat/f9-ui-redesign` in Task 0)

---

## Pre-flight

### Task 0: Branch, environment, and tooling

**Files:**
- Create: `feat/f10-native-app` branch
- Verify: `go`, `wails`, `golangci-lint`, `goose` available on `PATH`

- [ ] **Step 1: Verify Go toolchain**

```bash
go version
```
Expected: `go version go1.22.x linux/amd64` or newer.
If missing: install via `wget https://go.dev/dl/go1.22.X.linux-amd64.tar.gz && sudo tar -C /usr/local -xzf ...` then add `/usr/local/go/bin` to PATH.

- [ ] **Step 2: Install Wails v2 CLI**

```bash
go install github.com/wailsapp/wails/v2/cmd/wails@latest
wails doctor
```
Expected: `wails doctor` reports all dependencies green (webkit2gtk-4.0-dev, libgtk-3-dev). If red, run `sudo apt install libwebkit2gtk-4.0-dev libgtk-3-dev pkg-config build-essential`.

- [ ] **Step 3: Install linters and migration tool**

```bash
go install honnef.co/go/tools/cmd/staticcheck@latest
go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
go install github.com/pressly/goose/v3/cmd/goose@latest
```
Verify each: `staticcheck --version`, `golangci-lint --version`, `goose --version`.

- [ ] **Step 4: Create branch from F9**

```bash
cd /home/marcoslima/Documentos/projetos/J-arvs
git checkout feat/f9-ui-redesign
git pull --ff-only origin feat/f9-ui-redesign 2>/dev/null || true
git checkout -b feat/f10-native-app
git tag v0.9-python-final
git push -u origin feat/f10-native-app
git push origin v0.9-python-final
```
Expected: new branch `feat/f10-native-app` exists locally + remote; tag `v0.9-python-final` marks the last Python version.

- [ ] **Step 5: Commit pre-flight notes**

Create `F10-PORT-NOTES.md` at repo root with the branch creation date and tooling versions. This is operational metadata, not a permanent doc — it's deleted in F10.8.

```bash
cat > F10-PORT-NOTES.md <<EOF
# F10 Port Notes (temporary — deleted in F10.8)

- Branch created: $(date -I) from feat/f9-ui-redesign
- Python reference tag: v0.9-python-final
- Go: $(go version)
- Wails: $(wails version 2>/dev/null || echo unknown)

This file is a scratchpad for port-time decisions that don't deserve an ADR.
Delete in F10.8 cleanup.
EOF
git add F10-PORT-NOTES.md
git commit -m "chore(F10.0): branch from F9, tag v0.9-python-final, capture toolchain"
```

---

## Phase F10.0 — Wails skeleton

**Goal of this phase:** `wails dev` opens a window showing the F9 UI unchanged. `wails build` produces `build/bin/jarvis`. CI runs Go tests + UI tests + a Wails dev smoke. One stub binding (`HealthAPI.Snapshot`) proves the IPC channel works end-to-end.

### Task F10.0.1: Initialize Go module

**Files:**
- Create: `go.mod`, `go.sum`

- [ ] **Step 1: Init module**

```bash
go mod init github.com/marcosdid/jarvis
```
Expected: `go.mod` created with `module github.com/marcosdid/jarvis` + `go 1.22`.

- [ ] **Step 2: Verify build path**

```bash
go build ./...
```
Expected: no error (nothing to build yet, but the module is valid).

- [ ] **Step 3: Commit**

```bash
git add go.mod
git commit -m "feat(F10.0.1): init go module"
```

### Task F10.0.2: Wails project bootstrap

**Files:**
- Create: `wails.json`, `main.go`, `app.go`, `build/appicon.png`

- [ ] **Step 1: Bootstrap via Wails CLI**

Wails has a scaffolder that produces a working skeleton. Use it, but redirect the frontend to our existing `ui/`.

```bash
# In a temp dir to avoid clobbering ui/
mkdir -p /tmp/wails-skeleton && cd /tmp/wails-skeleton
wails init -n jarvis -t vanilla -q
# Copy only the files we want:
cp jarvis/wails.json /home/marcoslima/Documentos/projetos/J-arvs/wails.json
cp jarvis/main.go /home/marcoslima/Documentos/projetos/J-arvs/main.go
cp jarvis/app.go /home/marcoslima/Documentos/projetos/J-arvs/app.go
cp -r jarvis/build/appicon.png /home/marcoslima/Documentos/projetos/J-arvs/build/
cd /home/marcoslima/Documentos/projetos/J-arvs
rm -rf /tmp/wails-skeleton
```

- [ ] **Step 2: Configure wails.json to point at existing ui/**

Replace `wails.json` content:

```json
{
  "$schema": "https://wails.io/schemas/config.v2.json",
  "name": "jarvis",
  "outputfilename": "jarvis",
  "frontend:install": "npm install",
  "frontend:build": "npm run build",
  "frontend:dev:watcher": "npm run dev",
  "frontend:dev:serverUrl": "auto",
  "frontend:dir": "ui",
  "wailsjsdir": "./ui/src/wailsjs",
  "author": {
    "name": "marcosdid"
  }
}
```

Key points: `frontend:dir` is `ui` (not the Wails default `frontend`). `wailsjsdir` writes the auto-generated TS bindings into `ui/src/wailsjs/` so the front can import them as `../../wailsjs/...`.

- [ ] **Step 3: Replace main.go**

Write `main.go`:

```go
package main

import (
	"embed"

	"github.com/wailsapp/wails/v2"
	"github.com/wailsapp/wails/v2/pkg/options"
	"github.com/wailsapp/wails/v2/pkg/options/assetserver"
)

//go:embed all:ui/dist
var assets embed.FS

func main() {
	app := NewApp()

	err := wails.Run(&options.App{
		Title:  "J-arvis",
		Width:  1400,
		Height: 900,
		AssetServer: &assetserver.Options{
			Assets: assets,
		},
		BackgroundColour: &options.RGBA{R: 3, G: 5, B: 3, A: 1},
		OnStartup:        app.startup,
		Bind: []any{
			app,
		},
	})

	if err != nil {
		println("Error:", err.Error())
	}
}
```

- [ ] **Step 4: Replace app.go with minimal struct**

```go
package main

import "context"

type App struct {
	ctx context.Context
}

func NewApp() *App {
	return &App{}
}

func (a *App) startup(ctx context.Context) {
	a.ctx = ctx
}
```

- [ ] **Step 5: Pull deps**

```bash
go mod tidy
```
Expected: `go.sum` populated with Wails and its deps.

- [ ] **Step 6: Build smoke test**

```bash
cd ui && npm install && npm run build && cd ..
wails build -platform linux/amd64
```
Expected: `build/bin/jarvis` exists.

- [ ] **Step 7: Run smoke test**

```bash
./build/bin/jarvis &
sleep 2
pgrep -f "build/bin/jarvis" && echo "OK: window is running" || echo "FAIL"
killall jarvis
```
Expected: `OK: window is running` (and visually a Wails window with the F9 UI rendered — manual check).

- [ ] **Step 8: Commit**

```bash
git add wails.json main.go app.go go.mod go.sum build/appicon.png
git commit -m "feat(F10.0.2): Wails v2 skeleton with F9 UI embedded"
```

### Task F10.0.3: Stub HealthAPI binding (prove IPC works)

**Files:**
- Create: `internal/api/health.go`, `internal/api/health_test.go`
- Modify: `main.go`

- [ ] **Step 1: Write the failing test**

Create `internal/api/health_test.go`:

```go
package api

import (
	"context"
	"testing"
)

func TestHealthAPI_Snapshot(t *testing.T) {
	api := NewHealthAPI()
	snap, err := api.Snapshot(context.Background())
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if snap.AppVersion == "" {
		t.Error("AppVersion should not be empty")
	}
	if snap.Uptime < 0 {
		t.Errorf("Uptime should be >= 0, got %d", snap.Uptime)
	}
}
```

- [ ] **Step 2: Run test, verify it fails**

```bash
go test ./internal/api/...
```
Expected: FAIL with `package internal/api: build failed` (file doesn't exist).

- [ ] **Step 3: Write minimal HealthAPI**

Create `internal/api/health.go`:

```go
package api

import (
	"context"
	"time"
)

type HealthSnapshot struct {
	AppVersion string `json:"appVersion"`
	Uptime     int64  `json:"uptime"`
}

type HealthAPI struct {
	startedAt time.Time
}

func NewHealthAPI() *HealthAPI {
	return &HealthAPI{startedAt: time.Now()}
}

func (h *HealthAPI) Snapshot(_ context.Context) (HealthSnapshot, error) {
	return HealthSnapshot{
		AppVersion: "0.10.0-f10-dev",
		Uptime:     int64(time.Since(h.startedAt).Seconds()),
	}, nil
}
```

- [ ] **Step 4: Run test, verify it passes**

```bash
go test -race ./internal/api/...
```
Expected: `PASS`.

- [ ] **Step 5: Bind HealthAPI in main.go**

Edit `main.go`:

```go
import (
    // existing imports...
    "github.com/marcosdid/jarvis/internal/api"
)

func main() {
    app := NewApp()
    health := api.NewHealthAPI()

    err := wails.Run(&options.App{
        // ... unchanged ...
        Bind: []any{
            app,
            health,  // NEW
        },
    })
    // ...
}
```

- [ ] **Step 6: Verify Wails generates TS bindings**

```bash
wails generate module
ls ui/src/wailsjs/go/api/
```
Expected: `HealthAPI.d.ts`, `HealthAPI.js` present.

- [ ] **Step 7: Smoke test — wire up the UI**

First, find where the HUD version is rendered today:

```bash
grep -rn "version\|appVersion\|0.9" ui/src/app/ ui/src/components/hud/ 2>/dev/null | head -10
```

Edit that file (commonly `ui/src/app/AppShell.tsx` or `ui/src/components/hud/HudVersion.tsx`) and temporarily replace hardcoded version with:

```ts
import { useEffect, useState } from 'react';
import { Snapshot } from '../../wailsjs/go/api/HealthAPI';

const [version, setVersion] = useState('?');
useEffect(() => {
  Snapshot().then(s => setVersion(s.appVersion));
}, []);
```

- [ ] **Step 8: Visual verification**

```bash
wails dev
```
Expected: window opens, after a moment the HUD shows `0.10.0-f10-dev` instead of `?`. This proves Go → JS binding works.

- [ ] **Step 9: Revert the UI temp wiring (it'll come back properly in F10.2)**

Revert the file you edited in Step 7 with `git checkout -- <file>`. The point was to *prove the channel*, not commit a half-cooked HUD integration.

- [ ] **Step 10: Commit**

```bash
git add internal/api/health.go internal/api/health_test.go main.go ui/src/wailsjs/
git commit -m "feat(F10.0.3): HealthAPI stub binding — proves Go↔JS IPC channel"
```

### Task F10.0.4: Linter + test infrastructure

**Files:**
- Create: `.golangci.yml`, `Makefile.f10` (temporary, merges into Makefile in F10.8)

- [ ] **Step 1: Write `.golangci.yml`**

```yaml
run:
  timeout: 3m
  tests: true

linters:
  enable:
    - gofmt
    - govet
    - staticcheck
    - errcheck
    - ineffassign
    - unused
    - gosec
    - gocritic

linters-settings:
  gosec:
    excludes:
      - G104  # errcheck handles this

issues:
  exclude-dirs:
    - ui/dist
    - ui/node_modules
    - build
```

- [ ] **Step 2: Run linter, verify clean**

```bash
golangci-lint run
```
Expected: no issues.

- [ ] **Step 3: Write `Makefile.f10`**

```makefile
.PHONY: dev build test test-unit lint clean f10-help

f10-help:
	@echo "F10 port targets (will replace top-level Makefile in F10.8):"
	@echo "  make -f Makefile.f10 dev        - wails dev (window with HMR)"
	@echo "  make -f Makefile.f10 build      - wails build (binary in build/bin/)"
	@echo "  make -f Makefile.f10 test       - all tests + lint"
	@echo "  make -f Makefile.f10 test-unit  - go test + ui vitest"
	@echo "  make -f Makefile.f10 lint       - gofmt + go vet + golangci-lint"
	@echo "  make -f Makefile.f10 clean      - rm build/bin"

dev:
	wails dev

build:
	wails build -platform linux/amd64

test: lint test-unit

test-unit:
	go test -race -coverprofile=coverage.out ./internal/...
	cd ui && npm test -- --run

lint:
	gofmt -l . | grep -v vendor | grep -v ui/node_modules | { ! read; }
	go vet ./...
	golangci-lint run

clean:
	rm -rf build/bin coverage.out
```

- [ ] **Step 4: Run `make test`**

```bash
make -f Makefile.f10 test
```
Expected: all green. Coverage on `internal/api` should be ~100%.

- [ ] **Step 5: Commit**

```bash
git add .golangci.yml Makefile.f10
git commit -m "feat(F10.0.4): golangci-lint config + Makefile.f10 with dev/build/test/lint"
```

### Task F10.0.5: F10.0 close — demonstrable milestone

- [ ] **Step 1: Smoke run end-to-end**

```bash
make -f Makefile.f10 build
./build/bin/jarvis &
sleep 3
pgrep -f jarvis && echo "OK"
killall jarvis
```
Expected: `OK`.

- [ ] **Step 2: Manual visual check**

Run `wails dev`. Confirm: (a) Wails window opens with the F9 CIPHER design intact, (b) UI loads but most API calls fail (no Tasks/Sessions backend yet — expected), (c) no console errors related to Wails runtime.

- [ ] **Step 3: F10.0 tag**

```bash
git tag f10.0-skeleton
git push origin f10.0-skeleton
```

- [ ] **Step 4: Pause for review**

Stop here. Confirm with the user that F10.0 is green before proceeding to F10.1 (Store). The leader (or user) decides whether to continue immediately or commit + close session.

---

## Phase F10.1 — Store + migrations

**Goal of this phase:** SQLite opens, goose runs migrations 0001-0006 (translated from Alembic), `internal/store` has functional `TasksRepo` with 100% unit coverage, no UI wired yet.

### Task F10.1.1: DB connection + pragmas

**Files:**
- Create: `internal/store/db.go`, `internal/store/db_test.go`

- [ ] **Step 1: Write the failing test**

```go
package store

import (
	"context"
	"os"
	"path/filepath"
	"testing"
)

func TestOpenDB_AppliesPragmas(t *testing.T) {
	tmpDir := t.TempDir()
	dbPath := filepath.Join(tmpDir, "test.db")

	db, err := Open(context.Background(), dbPath)
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	defer db.Close()

	var fk int
	row := db.QueryRow("PRAGMA foreign_keys")
	if err := row.Scan(&fk); err != nil {
		t.Fatalf("Scan foreign_keys: %v", err)
	}
	if fk != 1 {
		t.Errorf("foreign_keys: got %d, want 1", fk)
	}

	var mode string
	row = db.QueryRow("PRAGMA journal_mode")
	if err := row.Scan(&mode); err != nil {
		t.Fatalf("Scan journal_mode: %v", err)
	}
	if mode != "wal" {
		t.Errorf("journal_mode: got %q, want %q", mode, "wal")
	}

	if _, err := os.Stat(dbPath); err != nil {
		t.Errorf("db file not created: %v", err)
	}
}
```

- [ ] **Step 2: Run test, verify it fails**

```bash
go test ./internal/store/...
```
Expected: FAIL with build error.

- [ ] **Step 3: Write Open()**

```go
package store

import (
	"context"
	"database/sql"
	"fmt"

	_ "modernc.org/sqlite"
)

func Open(ctx context.Context, dbPath string) (*sql.DB, error) {
	dsn := fmt.Sprintf("file:%s?_pragma=foreign_keys(1)&_pragma=journal_mode(WAL)&_pragma=busy_timeout(5000)", dbPath)
	db, err := sql.Open("sqlite", dsn)
	if err != nil {
		return nil, fmt.Errorf("sql.Open: %w", err)
	}
	if err := db.PingContext(ctx); err != nil {
		_ = db.Close()
		return nil, fmt.Errorf("ping: %w", err)
	}
	return db, nil
}
```

- [ ] **Step 4: Run test, verify it passes**

```bash
go mod tidy
go test -race ./internal/store/...
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add internal/store/db.go internal/store/db_test.go go.mod go.sum
git commit -m "feat(F10.1.1): SQLite Open() with WAL + foreign_keys pragmas"
```

### Task F10.1.2: Goose migrations infrastructure

**Files:**
- Create: `internal/store/migrate.go`, `internal/store/migrate_test.go`, `internal/store/migrations/` (directory)

- [ ] **Step 1: Write the failing test**

```go
package store

import (
	"context"
	"path/filepath"
	"testing"
)

func TestMigrate_AppliesAllUp(t *testing.T) {
	tmpDir := t.TempDir()
	dbPath := filepath.Join(tmpDir, "test.db")

	db, err := Open(context.Background(), dbPath)
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	defer db.Close()

	if err := Migrate(context.Background(), db); err != nil {
		t.Fatalf("Migrate: %v", err)
	}

	// Verify the latest expected version is applied (will tighten as we add migrations)
	var name string
	row := db.QueryRow(`SELECT name FROM sqlite_master WHERE type='table' AND name='goose_db_version'`)
	if err := row.Scan(&name); err != nil {
		t.Errorf("goose_db_version table not created: %v", err)
	}
}
```

- [ ] **Step 2: Run test, verify it fails**

```bash
go test ./internal/store/...
```
Expected: FAIL.

- [ ] **Step 3: Create migrate.go using `goose` library**

```go
package store

import (
	"context"
	"database/sql"
	"embed"
	"fmt"

	"github.com/pressly/goose/v3"
)

//go:embed migrations/*.sql
var migrationsFS embed.FS

func Migrate(ctx context.Context, db *sql.DB) error {
	goose.SetBaseFS(migrationsFS)
	if err := goose.SetDialect("sqlite3"); err != nil {
		return fmt.Errorf("set dialect: %w", err)
	}
	if err := goose.UpContext(ctx, db, "migrations"); err != nil {
		return fmt.Errorf("up: %w", err)
	}
	return nil
}
```

- [ ] **Step 4: Create at least one placeholder migration so embed works**

`internal/store/migrations/00000000000000_placeholder.sql`:

```sql
-- +goose Up
SELECT 1;

-- +goose Down
SELECT 1;
```

- [ ] **Step 5: Run test, verify it passes**

```bash
go mod tidy
go test -race ./internal/store/...
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add internal/store/migrate.go internal/store/migrate_test.go internal/store/migrations/00000000000000_placeholder.sql go.mod go.sum
git commit -m "feat(F10.1.2): goose migrations infrastructure + embed.FS"
```

### Task F10.1.3: Port Alembic 0001 (init schema)

**Files:**
- Read: `alembic/versions/0001_*.py` (Python reference)
- Create: `internal/store/migrations/20260101000001_init.sql`
- Delete: `internal/store/migrations/00000000000000_placeholder.sql`

- [ ] **Step 1: Read the Alembic source migration**

```bash
ls alembic/versions/
cat alembic/versions/0001_*.py
```
Note: copy the `CREATE TABLE` statements (Project, Task, ClaudeSession, etc.) verbatim, adapting SQLAlchemy types to SQLite-native types.

- [ ] **Step 2: Write `20260101000001_init.sql`**

(Exact content depends on what's in 0001 — port faithfully. Example skeleton, adapt to actual:)

```sql
-- +goose Up
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    path TEXT NOT NULL UNIQUE,
    created_at DATETIME NOT NULL
);

CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    state TEXT NOT NULL CHECK(state IN ('idea','ready','in_progress','review','done','discarded')),
    branch TEXT,
    template TEXT,
    permission_profile TEXT,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);

CREATE INDEX idx_tasks_project_state ON tasks(project_id, state);

-- (continue with sessions, etc., based on actual alembic 0001 content)

-- +goose Down
DROP INDEX IF EXISTS idx_tasks_project_state;
DROP TABLE IF EXISTS tasks;
DROP TABLE IF EXISTS projects;
```

- [ ] **Step 3: Remove placeholder migration**

```bash
git rm internal/store/migrations/00000000000000_placeholder.sql
```

- [ ] **Step 4: Tighten the test**

Update `migrate_test.go` `TestMigrate_AppliesAllUp` to verify the tables exist:

```go
// Add at end of TestMigrate_AppliesAllUp:
for _, table := range []string{"projects", "tasks"} {
    var name string
    err := db.QueryRow(
        `SELECT name FROM sqlite_master WHERE type='table' AND name=?`, table,
    ).Scan(&name)
    if err != nil {
        t.Errorf("table %q not created: %v", table, err)
    }
}
```

- [ ] **Step 5: Run test, verify it passes**

```bash
go test -race ./internal/store/...
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add internal/store/migrations/20260101000001_init.sql internal/store/migrate_test.go
git rm internal/store/migrations/00000000000000_placeholder.sql
git commit -m "feat(F10.1.3): port Alembic 0001 init schema → goose 20260101000001"
```

### Task F10.1.4: Port Alembic migrations 0002-0006

**Files:**
- Read: `alembic/versions/0002_*.py` through `0006_*.py`
- Create: `internal/store/migrations/20260101000002_*.sql` through `20260101000006_*.sql`

- [ ] **Step 1-N: For each Alembic file 0002..0006, do the same as Task F10.1.3:**
  - Read the Python source
  - Translate to SQL `-- +goose Up` / `-- +goose Down` blocks
  - Add new asserts to `migrate_test.go` for tables/columns/indexes the migration creates
  - Run `go test -race ./internal/store/...` and verify green
  - Commit each as `feat(F10.1.4.X): port Alembic 000X migration`

This step is **mechanical translation** — there are no design decisions here. Just faithful reproduction of the schema in SQLite-flavored SQL.

**Type-mapping notes (read before translating):**
- SQLAlchemy `DateTime` → SQLite `DATETIME` (stored as ISO-8601 text by `modernc.org/sqlite`; Go's `time.Time` round-trips automatically)
- SQLAlchemy `JSON` → SQLite `TEXT` (store JSON-as-string; parse in Go with `encoding/json`)
- Nullable FK (e.g. `Worktree.task_id`): use `... REFERENCES tasks(id) ON DELETE SET NULL` to match Python behavior
- Migration 0003 (`tasks_and_session_task_link`) and 0005 (`run_instances`) have non-trivial CHECK constraints and partial unique indexes — re-read both Python files carefully before translating; partial unique syntax is `CREATE UNIQUE INDEX ... WHERE ended_at IS NULL`

- [ ] **Step Final: Smoke-test the cumulative schema**

```bash
go test -race ./internal/store/... -v -run TestMigrate
```
Expected: all migrations apply cleanly, all tables/indexes from Python schema exist.

### Task F10.1.5: TasksRepo skeleton

**Files:**
- Create: `internal/store/tasks.go`, `internal/store/tasks_test.go`

- [ ] **Step 1: Write the failing test for List**

```go
package store

import (
	"context"
	"path/filepath"
	"testing"
)

func newTestDB(t *testing.T) *sql.DB {
	t.Helper()
	tmpDir := t.TempDir()
	db, err := Open(context.Background(), filepath.Join(tmpDir, "test.db"))
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	if err := Migrate(context.Background(), db); err != nil {
		t.Fatalf("Migrate: %v", err)
	}
	t.Cleanup(func() { _ = db.Close() })
	return db
}

func TestTasksRepo_List_EmptyDB(t *testing.T) {
	db := newTestDB(t)
	repo := NewTasksRepo(db)
	tasks, err := repo.List(context.Background(), TaskFilters{})
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	if len(tasks) != 0 {
		t.Errorf("expected 0 tasks, got %d", len(tasks))
	}
}
```

- [ ] **Step 2: Run, verify fail**

```bash
go test ./internal/store/...
```
Expected: FAIL — `TasksRepo`, `TaskFilters` not defined.

- [ ] **Step 3: Define structs and minimal impl**

`internal/store/tasks.go`:

```go
package store

import (
	"context"
	"database/sql"
	"time"
)

type Task struct {
	ID                string
	ProjectID         string
	Title             string
	Description       string
	State             string
	Branch            *string
	Template          *string
	PermissionProfile *string
	CreatedAt         time.Time
	UpdatedAt         time.Time
}

type TaskFilters struct {
	ProjectIDs []string
	States     []string
}

type TasksRepo struct {
	db *sql.DB
}

func NewTasksRepo(db *sql.DB) *TasksRepo {
	return &TasksRepo{db: db}
}

func (r *TasksRepo) List(ctx context.Context, f TaskFilters) ([]Task, error) {
	query := `SELECT id, project_id, title, description, state, branch, template, permission_profile, created_at, updated_at FROM tasks`
	rows, err := r.db.QueryContext(ctx, query)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var out []Task
	for rows.Next() {
		var t Task
		if err := rows.Scan(&t.ID, &t.ProjectID, &t.Title, &t.Description, &t.State,
			&t.Branch, &t.Template, &t.PermissionProfile, &t.CreatedAt, &t.UpdatedAt); err != nil {
			return nil, err
		}
		out = append(out, t)
	}
	return out, rows.Err()
}
```

- [ ] **Step 4: Run, verify pass**

```bash
go test -race ./internal/store/...
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add internal/store/tasks.go internal/store/tasks_test.go
git commit -m "feat(F10.1.5): TasksRepo.List on empty DB"
```

### Task F10.1.6: TasksRepo.Create + Update + Discard

**Files:**
- Modify: `internal/store/tasks.go`, `internal/store/tasks_test.go`

- [ ] **Step 1: Test for Create**

Append to `tasks_test.go`:

```go
func TestTasksRepo_Create_AndListReflectsIt(t *testing.T) {
	db := newTestDB(t)
	repo := NewTasksRepo(db)

	// Seed a project (FK requirement)
	_, err := db.Exec(`INSERT INTO projects(id, name, path, created_at) VALUES (?, ?, ?, ?)`,
		"prj-1", "demo", "/tmp/demo", time.Now())
	if err != nil {
		t.Fatalf("seed project: %v", err)
	}

	input := CreateTaskInput{
		ProjectID:   "prj-1",
		Title:       "do the thing",
		Description: "details",
		State:       "idea",
	}
	created, err := repo.Create(context.Background(), input)
	if err != nil {
		t.Fatalf("Create: %v", err)
	}
	if created.ID == "" {
		t.Error("expected ID populated")
	}
	if created.Title != "do the thing" {
		t.Errorf("Title: got %q, want %q", created.Title, "do the thing")
	}

	list, _ := repo.List(context.Background(), TaskFilters{})
	if len(list) != 1 {
		t.Fatalf("expected 1 task, got %d", len(list))
	}
}
```

- [ ] **Step 2: Run, verify FAIL**

```bash
go test ./internal/store/...
```
Expected: FAIL — `CreateTaskInput`, `repo.Create` not defined.

- [ ] **Step 3: Implement Create**

In `tasks.go`:

```go
import "github.com/google/uuid"

type CreateTaskInput struct {
	ProjectID   string
	Title       string
	Description string
	State       string
	Template    *string
	Branch      *string
}

func (r *TasksRepo) Create(ctx context.Context, in CreateTaskInput) (*Task, error) {
	id := uuid.NewString()
	now := time.Now().UTC()
	state := in.State
	if state == "" {
		state = "idea"
	}
	_, err := r.db.ExecContext(ctx, `INSERT INTO tasks
		(id, project_id, title, description, state, branch, template, permission_profile, created_at, updated_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)`,
		id, in.ProjectID, in.Title, in.Description, state, in.Branch, in.Template, now, now)
	if err != nil {
		return nil, err
	}
	return &Task{
		ID:          id,
		ProjectID:   in.ProjectID,
		Title:       in.Title,
		Description: in.Description,
		State:       state,
		Branch:      in.Branch,
		Template:    in.Template,
		CreatedAt:   now,
		UpdatedAt:   now,
	}, nil
}
```

- [ ] **Step 4: Add UUID dep**

```bash
go get github.com/google/uuid
go mod tidy
```

- [ ] **Step 5: Run, verify PASS**

```bash
go test -race ./internal/store/...
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add internal/store/tasks.go internal/store/tasks_test.go go.mod go.sum
git commit -m "feat(F10.1.6a): TasksRepo.Create"
```

- [ ] **Step 7: Tests + impl for Move (state transition)**

Add test:

```go
func TestTasksRepo_Move_ValidTransition(t *testing.T) {
	db := newTestDB(t)
	repo := NewTasksRepo(db)
	_, _ = db.Exec(`INSERT INTO projects(id, name, path, created_at) VALUES ('p','x','/t', ?)`, time.Now())
	created, _ := repo.Create(context.Background(), CreateTaskInput{ProjectID: "p", Title: "t", State: "idea"})

	if err := repo.Move(context.Background(), created.ID, "ready"); err != nil {
		t.Fatalf("Move: %v", err)
	}
	list, _ := repo.List(context.Background(), TaskFilters{})
	if list[0].State != "ready" {
		t.Errorf("state: got %q, want %q", list[0].State, "ready")
	}
}
```

Run → FAIL → implement:

```go
func (r *TasksRepo) Move(ctx context.Context, id, newState string) error {
	res, err := r.db.ExecContext(ctx, `UPDATE tasks SET state = ?, updated_at = ? WHERE id = ?`,
		newState, time.Now().UTC(), id)
	if err != nil {
		return err
	}
	n, _ := res.RowsAffected()
	if n == 0 {
		return fmt.Errorf("task %q not found", id)
	}
	return nil
}
```

Run → PASS → commit `feat(F10.1.6b): TasksRepo.Move`.

- [ ] **Step 8: Tests + impl for Discard (alias for Move to 'discarded')**

Add test, run, implement, commit `feat(F10.1.6c): TasksRepo.Discard`.

```go
func (r *TasksRepo) Discard(ctx context.Context, id string) error {
	return r.Move(ctx, id, "discarded")
}
```

- [ ] **Step 9: Verify coverage**

```bash
go test -race -coverprofile=cov.out ./internal/store/...
go tool cover -func=cov.out | grep -E "tasks.go"
```
Expected: each function `100.0%`. If anything < 100%, write the missing test.

### Task F10.1.7: F10.1 close

- [ ] **Step 1: Run all tests + linter**

```bash
make -f Makefile.f10 test
```
Expected: all green.

- [ ] **Step 2: Tag**

```bash
git tag f10.1-store
git push origin f10.1-store
```

- [ ] **Step 3: Pause for review.** Leader (or user) confirms F10.1 is green.

---

## Phase F10.2 — Tasks vertical slice (UI works against new Go backend)

**Goal:** Open `wails dev`, see the F9 kanban, create a task in the UI, see it persist in SQLite, see it reflect across the kanban via Wails events. WebSocket and `fetch` are deleted.

### Task F10.2.1: `core/task.go` — entity + state machine

**Files:**
- Create: `internal/core/task.go`, `internal/core/task_test.go`

- [ ] **Step 1: Write tests for valid + invalid transitions**

```go
package core

import "testing"

func TestTask_ValidTransition(t *testing.T) {
	tests := []struct {
		from, to string
		ok       bool
	}{
		{"idea", "ready", true},
		{"ready", "in_progress", true},
		{"in_progress", "review", true},
		{"review", "done", true},
		{"idea", "discarded", true},
		{"done", "in_progress", false}, // backward not allowed
		{"discarded", "idea", false},   // can't un-discard
	}
	for _, tc := range tests {
		t.Run(tc.from+"→"+tc.to, func(t *testing.T) {
			ok := IsValidTransition(tc.from, tc.to)
			if ok != tc.ok {
				t.Errorf("%s→%s: got %v, want %v", tc.from, tc.to, ok, tc.ok)
			}
		})
	}
}
```

- [ ] **Step 2: Run, verify FAIL**, then implement:

```go
package core

var validTransitions = map[string]map[string]bool{
	"idea":        {"ready": true, "discarded": true},
	"ready":       {"in_progress": true, "idea": true, "discarded": true},
	"in_progress": {"review": true, "ready": true, "discarded": true},
	"review":      {"done": true, "in_progress": true, "discarded": true},
	"done":        {"discarded": true},
	"discarded":   {},
}

func IsValidTransition(from, to string) bool {
	if from == to {
		return true
	}
	return validTransitions[from][to]
}
```

Run → PASS → commit `feat(F10.2.1): Task state machine`.

### Task F10.2.2: `internal/api/tasks.go` — TasksAPI binding

**Files:**
- Create: `internal/api/tasks.go`, `internal/api/tasks_test.go`
- Modify: `main.go` to bind TasksAPI

- [ ] **Step 1: Test for TasksAPI.Create (using a fake repo)**

```go
package api

import (
	"context"
	"testing"

	"github.com/marcosdid/jarvis/internal/store"
)

type fakeRepo struct {
	created *store.Task
}

func (f *fakeRepo) List(_ context.Context, _ store.TaskFilters) ([]store.Task, error) {
	if f.created != nil {
		return []store.Task{*f.created}, nil
	}
	return nil, nil
}
func (f *fakeRepo) Create(_ context.Context, in store.CreateTaskInput) (*store.Task, error) {
	f.created = &store.Task{ID: "fake-1", Title: in.Title, State: "idea"}
	return f.created, nil
}
func (f *fakeRepo) Move(_ context.Context, _, _ string) error    { return nil }
func (f *fakeRepo) Discard(_ context.Context, _ string) error    { return nil }

func TestTasksAPI_Create_EmitsEvent(t *testing.T) {
	emitted := false
	bus := &fakeBus{onEmit: func(string, any) { emitted = true }}
	api := NewTasksAPI(&fakeRepo{}, bus)
	_, err := api.Create(context.Background(), CreateInput{ProjectID: "p", Title: "x"})
	if err != nil {
		t.Fatalf("Create: %v", err)
	}
	if !emitted {
		t.Error("expected event to be emitted")
	}
}
```

Add a small `fakeBus` helper in `internal/api/api_test_helpers.go`:

```go
package api

type fakeBus struct {
	onEmit func(name string, payload any)
}

func (f *fakeBus) Emit(name string, payload any) {
	if f.onEmit != nil {
		f.onEmit(name, payload)
	}
}
```

- [ ] **Step 2: Run, verify FAIL** (TasksAPI doesn't exist) → implement:

```go
package api

import (
	"context"

	"github.com/marcosdid/jarvis/internal/core"
	"github.com/marcosdid/jarvis/internal/store"
)

// TasksRepo isolates the store; allows fake in tests.
type TasksRepo interface {
	List(context.Context, store.TaskFilters) ([]store.Task, error)
	Create(context.Context, store.CreateTaskInput) (*store.Task, error)
	Move(context.Context, string, string) error
	Discard(context.Context, string) error
}

type EventBus interface {
	Emit(name string, payload any)
}

type TasksAPI struct {
	repo TasksRepo
	bus  EventBus
}

func NewTasksAPI(repo TasksRepo, bus EventBus) *TasksAPI {
	return &TasksAPI{repo: repo, bus: bus}
}

type CreateInput struct {
	ProjectID   string  `json:"projectId"`
	Title       string  `json:"title"`
	Description string  `json:"description"`
	Branch      *string `json:"branch,omitempty"`
	Template    *string `json:"template,omitempty"`
}

func (a *TasksAPI) List(ctx context.Context) ([]store.Task, error) {
	return a.repo.List(ctx, store.TaskFilters{})
}

func (a *TasksAPI) Create(ctx context.Context, in CreateInput) (*store.Task, error) {
	created, err := a.repo.Create(ctx, store.CreateTaskInput{
		ProjectID: in.ProjectID, Title: in.Title, Description: in.Description,
		State: "idea", Branch: in.Branch, Template: in.Template,
	})
	if err != nil {
		return nil, err
	}
	a.bus.Emit("task.created", created)
	return created, nil
}

func (a *TasksAPI) Move(ctx context.Context, id, newState string) error {
	// State-machine validation lives in core.IsValidTransition; called from
	// the repo layer once we wire current-state fetch in F10.2.X (defer if not needed for kanban).
	if err := a.repo.Move(ctx, id, newState); err != nil {
		return err
	}
	a.bus.Emit("task.updated", map[string]string{"id": id, "state": newState})
	return nil
}

func (a *TasksAPI) Discard(ctx context.Context, id string) error {
	if err := a.repo.Discard(ctx, id); err != nil {
		return err
	}
	a.bus.Emit("task.discarded", map[string]string{"id": id})
	return nil
}
```

Run → PASS → commit `feat(F10.2.2): TasksAPI with Create/List/Move/Discard + event emission`.

### Task F10.2.3: `internal/events/bus.go` — Wails event bus wrapper

**Files:**
- Create: `internal/events/bus.go`, `internal/events/bus_test.go`

The bus is a thin wrapper around Wails runtime so we can test via fakes.

- [ ] **Step 1: Define interface, fake, and real impl**

```go
// internal/events/bus.go
package events

import (
	"context"

	"github.com/wailsapp/wails/v2/pkg/runtime"
)

type Emitter interface {
	Emit(name string, payload any)
}

// WailsEmitter uses the live Wails runtime. Excluded from coverage by build tag.
type WailsEmitter struct {
	ctx context.Context
}

func NewWailsEmitter(ctx context.Context) *WailsEmitter {
	return &WailsEmitter{ctx: ctx}
}

func (e *WailsEmitter) Emit(name string, payload any) {
	runtime.EventsEmit(e.ctx, name, payload)
}
```

- [ ] **Step 2: Exclude from coverage via build tag**

Split `WailsEmitter` into its own file `internal/events/wails_runtime.go` with `//go:build !test` at the top, and provide a fake stub in `internal/events/wails_runtime_test_stub.go` with `//go:build test`. This matches the spec §9.4 approach (build-tag exclusion, not golangci-config exclusion — keeps coverage report honest about what's tested vs what's intentionally untestable).

```go
// internal/events/wails_runtime.go
//go:build !test

package events

import (
	"context"

	"github.com/wailsapp/wails/v2/pkg/runtime"
)

type WailsEmitter struct {
	ctx context.Context
}

func NewWailsEmitter(ctx context.Context) *WailsEmitter {
	return &WailsEmitter{ctx: ctx}
}

func (e *WailsEmitter) Emit(name string, payload any) {
	runtime.EventsEmit(e.ctx, name, payload)
}
```

```go
// internal/events/wails_runtime_test_stub.go
//go:build test

package events

import "context"

type WailsEmitter struct {
	calls []emitCall
}
type emitCall struct{ name string; payload any }

func NewWailsEmitter(_ context.Context) *WailsEmitter { return &WailsEmitter{} }
func (e *WailsEmitter) Emit(name string, payload any) {
	e.calls = append(e.calls, emitCall{name, payload})
}
```

Test runs with `go test -tags=test ./internal/events/...` to use the stub. Production build uses default (no `-tags`) and gets the real Wails impl.

- [ ] **Step 3: Commit**

```bash
git add internal/events/bus.go
git commit -m "feat(F10.2.3): events bus interface + WailsEmitter wrapper"
```

### Task F10.2.4: Wire TasksAPI in main.go

**Files:**
- Modify: `main.go`

- [ ] **Step 1: Update startup to create DB + run migrations + bind TasksAPI**

```go
package main

import (
	"context"
	"embed"
	"log"
	"os"
	"path/filepath"

	"github.com/marcosdid/jarvis/internal/api"
	"github.com/marcosdid/jarvis/internal/events"
	"github.com/marcosdid/jarvis/internal/store"

	"github.com/wailsapp/wails/v2"
	"github.com/wailsapp/wails/v2/pkg/options"
	"github.com/wailsapp/wails/v2/pkg/options/assetserver"
)

//go:embed all:ui/dist
var assets embed.FS

func dbPath() string {
	dir := os.Getenv("XDG_DATA_HOME")
	if dir == "" {
		dir = filepath.Join(os.Getenv("HOME"), ".local/share")
	}
	full := filepath.Join(dir, "jarvis")
	_ = os.MkdirAll(full, 0o755)
	return filepath.Join(full, "jarvis.db")
}

func main() {
	ctx := context.Background()

	db, err := store.Open(ctx, dbPath())
	if err != nil {
		log.Fatalf("store.Open: %v", err)
	}
	if err := store.Migrate(ctx, db); err != nil {
		log.Fatalf("store.Migrate: %v", err)
	}

	app := NewApp()
	health := api.NewHealthAPI()

	var bus events.Emitter
	tasksRepo := store.NewTasksRepo(db)

	wailsErr := wails.Run(&options.App{
		Title:  "J-arvis",
		Width:  1400,
		Height: 900,
		AssetServer: &assetserver.Options{
			Assets: assets,
		},
		BackgroundColour: &options.RGBA{R: 3, G: 5, B: 3, A: 1},
		OnStartup: func(c context.Context) {
			app.startup(c)
			bus = events.NewWailsEmitter(c)
		},
		Bind: []any{
			app,
			health,
			api.NewTasksAPI(tasksRepo, &lazyBus{getEmitter: func() events.Emitter { return bus }}),
		},
	})
	if wailsErr != nil {
		log.Fatalf("wails.Run: %v", wailsErr)
	}
}

// lazyBus defers reaching the Wails ctx until OnStartup has run.
type lazyBus struct {
	getEmitter func() events.Emitter
}

func (l *lazyBus) Emit(name string, payload any) {
	if e := l.getEmitter(); e != nil {
		e.Emit(name, payload)
	}
}
```

- [ ] **Step 2: `go build` + smoke test**

```bash
make -f Makefile.f10 build
./build/bin/jarvis &
sleep 2
killall jarvis
```
Expected: binary runs, DB file created at `~/.local/share/jarvis/jarvis.db`.

- [ ] **Step 3: Verify DB has migrations applied**

```bash
sqlite3 ~/.local/share/jarvis/jarvis.db "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
```
Expected: includes `tasks`, `projects`, `goose_db_version`.

- [ ] **Step 4: Commit**

```bash
git add main.go
git commit -m "feat(F10.2.4): wire SQLite + migrations + TasksAPI in main.go"
```

### Task F10.2.5: Frontend — rewrite `ui/src/lib/api.ts` to use Wails bindings

**Files:**
- Modify: `ui/src/lib/api.ts`
- Reference: `ui/src/wailsjs/go/api/TasksAPI.{d.ts,js}` (auto-generated by `wails generate module`)

- [ ] **Step 1: Generate fresh bindings**

```bash
wails generate module
```

Expected: `ui/src/wailsjs/go/api/TasksAPI.d.ts` lists `List`, `Create`, `Move`, `Discard` with TS types derived from Go structs.

- [ ] **Step 2: Rewrite `ui/src/lib/api.ts` to delegate to Wails**

Read the current `api.ts` to understand what the front consumers expect. **Check the actual export shape** of `ui/src/wailsjs/go/api/TasksAPI.d.ts` — Wails CLI versions differ in whether they export named functions (`export function List(...): Promise<...>`) or attach them to a default class. The import form below assumes named exports; adjust to `import { List, Create, Move, Discard }` if that's what got generated.

```ts
// Adjust the import form to match the generated .d.ts (see step 2 note above)
import * as TasksAPI from '../../wailsjs/go/api/TasksAPI';

export type Task = {
  id: string;
  projectId: string;
  title: string;
  description: string;
  state: string;
  branch?: string | null;
  template?: string | null;
  createdAt: string;
  updatedAt: string;
};

export const api = {
  // ... preserve other endpoint placeholders (will be filled in F10.3+)
  listTasks: () => TasksAPI.List(),
  createTask: (input: { projectId: string; title: string; description?: string }) =>
    TasksAPI.Create(input),
  moveTask: (id: string, newState: string) => TasksAPI.Move(id, newState),
  discardTask: (id: string) => TasksAPI.Discard(id),
};
```

- [ ] **Step 3: Update Vitest mocks**

Wherever the existing tests mock `fetch`, replace with mocks of `TasksAPI.*` (vitest's `vi.mock('../../wailsjs/go/api/TasksAPI', ...)`). Run `cd ui && npm test` and fix until green.

- [ ] **Step 4: Commit**

```bash
git add ui/src/lib/api.ts ui/src/wailsjs/
# Plus any test files updated to mock Wails bindings instead of fetch:
git add $(git diff --name-only ui/src | grep test)
git commit -m "feat(F10.2.5): UI api.ts uses Wails TasksAPI bindings (fetch removed for tasks)"
```

### Task F10.2.6: Frontend — replace `ws.ts` with `events.ts`

**Files:**
- Create: `ui/src/lib/events.ts`
- Modify: `ui/src/hooks/useSessionEvents.ts` to consume `events.ts`
- Delete: `ui/src/lib/ws.ts`, `ui/src/stores/wsConnection.ts`

- [ ] **Step 1: Write `events.ts`** (as in spec §6.2):

```ts
import { EventsOn, EventsOff } from '../../wailsjs/runtime';
import type { WsEvent } from './events.types';

const EVENT_NAMES = [
  'task.created', 'task.updated', 'task.discarded',
  'session.status', 'session.tool_use', 'session.stopped',
  'run.status', 'master.system', 'hud.events_per_sec',
] as const;

export function subscribeEvents(onEvent: (event: WsEvent) => void): () => void {
  const offFns = EVENT_NAMES.map((name) => {
    EventsOn(name, (payload) => onEvent({ type: name, payload } as WsEvent));
    return () => EventsOff(name);
  });
  return () => offFns.forEach((fn) => fn());
}
```

- [ ] **Step 2: Rewrite `useSessionEvents` to use `subscribeEvents`**

```ts
import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { subscribeEvents } from '../lib/events';
import { queryKeys } from '../lib/query-keys';

export function useSessionEvents(qc: ReturnType<typeof useQueryClient>) {
  useEffect(() => {
    return subscribeEvents((event) => {
      switch (event.type) {
        case 'task.created':
        case 'task.updated':
        case 'task.discarded':
          qc.invalidateQueries({ queryKey: queryKeys.tasks });
          break;
        // session.*, run.*, master.* will be wired in later F10.x phases
      }
    });
  }, [qc]);
}
```

- [ ] **Step 3: Delete `ws.ts` and `wsConnection.ts`**

```bash
git rm ui/src/lib/ws.ts ui/src/stores/wsConnection.ts
```

- [ ] **Step 4: Fix any imports** (`grep -r "from '.*lib/ws'" ui/src`) and run typecheck:

```bash
cd ui && npm run typecheck && npm test -- --run
```
Expected: zero TS errors, all green tests.

- [ ] **Step 5: Commit**

```bash
git add ui/src/lib/events.ts ui/src/hooks/useSessionEvents.ts
git rm ui/src/lib/ws.ts ui/src/stores/wsConnection.ts
git commit -m "feat(F10.2.6): events.ts replaces ws.ts; useSessionEvents uses Wails EventsOn"
```

### Task F10.2.7: End-to-end smoke

**Files:** no edits — verification step.

- [ ] **Step 1: Wire up dev**

```bash
wails dev
```

- [ ] **Step 2: Manual test**

1. Window opens with F9 design intact.
2. Open the "+ New task" sheet → fill title → submit.
3. Task appears in `idea` column.
4. Drag the task to `ready` (DnD).
5. Refresh window (Ctrl+R) — task persists.
6. Discard the task — column updates.
7. Close window, reopen — task with state `discarded` not visible in kanban (depending on filters).

- [ ] **Step 3: Check DB**

```bash
sqlite3 ~/.local/share/jarvis/jarvis.db "SELECT id, title, state FROM tasks;"
```
Expected: matches what you did in the UI.

- [ ] **Step 4: Console errors check**

In dev tools console: no errors related to `fetch` (should be zero `fetch` to `/api/tasks`), no WebSocket errors (should be zero `ws://` attempts).

### Task F10.2.8: F10.2 close

- [ ] **Step 1: Tests + lint**

```bash
make -f Makefile.f10 test
```
Expected: all green.

- [ ] **Step 2: Coverage check**

```bash
go test -race -coverprofile=cov.out ./internal/...
go tool cover -func=cov.out | grep -E "(api|core|store)" | sort
```
Expected: each function 100.0%, except deliberate exclusions in `events/bus.go` (Wails wrapper).

- [ ] **Step 3: Tag**

```bash
git tag f10.2-tasks-slice
git push origin f10.2-tasks-slice
```

- [ ] **Step 4: Document learnings**

Append to `F10-PORT-NOTES.md`:

```markdown
## F10.2 close — learnings

- Wails bindings UX: <how it felt>
- Performance: <cold start, response time>
- Gotchas: <anything surprising>
- For F10.3 planning: <issues to address>
```

- [ ] **Step 5: Commit notes**

```bash
git add F10-PORT-NOTES.md
git commit -m "docs(F10.2): close notes — kanban vertical slice green"
```

---

## Completion criteria for Block A

When all the following are true, Block A is done and we move to Block B planning:

- [ ] `wails dev` opens window with F9 UI intact (no visual regressions)
- [ ] `wails build` produces `build/bin/jarvis` that runs standalone
- [ ] Kanban end-to-end works: create task, list, move between columns, discard — all via Wails bindings, no fetch, no WebSocket
- [ ] `make -f Makefile.f10 test` green (Go unit tests + Vitest, both 100% coverage on touched files)
- [ ] `golangci-lint run` clean
- [ ] DB at `~/.local/share/jarvis/jarvis.db` persists tasks across restarts
- [ ] Tags `f10.0-skeleton`, `f10.1-store`, `f10.2-tasks-slice` pushed
- [ ] `F10-PORT-NOTES.md` updated with close notes per phase

---

## Follow-up: Block B preview (NOT in this plan)

Block B (`docs/superpowers/plans/2026-MM-DD-f10-block-b-projects-sandbox-master.md`) will cover:
- F10.3 — Projects + Worktrees + multi-repo
- F10.4 — Sandbox + Sessions + Hooks (HTTP hook server, settings.json writer, token-per-session)
- F10.5 — Master session + Catalog + MCP

Block B is written **after** Block A closes green, applying learnings from `F10-PORT-NOTES.md`.

Block C (cleanup phases F10.6-F10.8) is written after Block B closes.
