//go:build e2e_http

// jarvis-e2e-http exposes the same Wails-bound APIs (Tasks/Projects/Master)
// over HTTP, without the Wails runtime. Used by the Playwright E2E suite
// — Playwright loads vite preview in regular Chromium and the e2e-shim
// fetches this HTTP server in place of window.go.
//
// Build: go build -tags e2e_http -o build/bin/jarvis-e2e-http ./cmd/jarvis-e2e-http
//
// At runtime, prints `E2E_HTTP_PORT=<n>` to stdout and blocks on SIGTERM.
package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"

	"github.com/marcosdid/jarvis/internal/api"
	"github.com/marcosdid/jarvis/internal/events"
	"github.com/marcosdid/jarvis/internal/store"
)

func dbPath() string {
	if explicit := os.Getenv("JARVIS_DB_PATH"); explicit != "" {
		_ = os.MkdirAll(filepath.Dir(explicit), 0o755)
		return explicit
	}
	tmp := os.TempDir()
	dir := filepath.Join(tmp, "jarvis-e2e")
	_ = os.MkdirAll(dir, 0o755)
	return filepath.Join(dir, "jarvis.db")
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

	// LazyEmitter resolves to an in-memory FakeEmitter — events fire but
	// nothing surfaces to JS (the shim's runtime.EventsOn keeps them
	// in-memory either way). Sufficient for current E2E coverage.
	fake := &events.FakeEmitter{}
	lazyBus := &events.LazyEmitter{Resolve: func() events.Emitter { return fake }}

	tasksRepo := store.NewTasksRepo(db)
	projectsRepo := store.NewProjectsRepo(db)

	tasksAPI := api.NewTasksAPI(tasksRepo, lazyBus, nil)
	projectsAPI := api.NewProjectsAPI(projectsRepo, lazyBus)
	masterAPI := api.NewMasterAPI(lazyBus, api.DefaultSessionFactory, os.Getenv("JARVIS_CLAUDE_BIN"))

	srv := api.NewE2EServer(tasksAPI, projectsAPI, masterAPI)
	if _, err := srv.Start(); err != nil {
		log.Fatalf("e2e server start: %v", err)
	}
	defer srv.Stop()

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
	<-sig
}
