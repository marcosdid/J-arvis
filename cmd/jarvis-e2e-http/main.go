//go:build e2e_http

// jarvis-e2e-http exposes the same Wails-bound APIs (Tasks/Projects/Master/
// Worktrees/Sessions) over HTTP, without the Wails runtime. Used by the
// Playwright E2E suite — Playwright loads vite preview in regular Chromium
// and the e2e-shim fetches this HTTP server in place of window.go.
//
// Build: go build -tags e2e_http -o build/bin/jarvis-e2e-http ./cmd/jarvis-e2e-http
//
// At runtime, prints `E2E_HTTP_PORT=<n>` to stdout and blocks on SIGTERM.
//
// Runtime selection:
//
//	JARVIS_E2E_RUNTIME=fake → in-process fake (no fork). Default → AijailRuntime.
package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"

	"github.com/marcosdid/jarvis/internal/api"
	"github.com/marcosdid/jarvis/internal/catalog"
	"github.com/marcosdid/jarvis/internal/core"
	"github.com/marcosdid/jarvis/internal/events"
	jgit "github.com/marcosdid/jarvis/internal/git"
	"github.com/marcosdid/jarvis/internal/hooks"
	"github.com/marcosdid/jarvis/internal/localhttp"
	"github.com/marcosdid/jarvis/internal/master"
	"github.com/marcosdid/jarvis/internal/mcp"
	"github.com/marcosdid/jarvis/internal/sandbox"
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
	repositoriesRepo := store.NewRepositoriesRepo(db)
	worktreesRepo := store.NewWorktreesRepo(db)
	sessionsRepo := store.NewSessionsRepo(db)

	tokenRegistry := hooks.NewTokenRegistry()
	hookUpdater := store.NewSessionsHookAdapter(sessionsRepo)
	hookHandler := hooks.NewHandler(tokenRegistry, lazyBus, hookUpdater)

	gitOps := jgit.NewSubprocessOps()
	projectsSvc := core.NewProjectsService(projectsRepo, repositoriesRepo, tasksRepo, lazyBus)
	worktreesSvc := core.NewWorktreesService(worktreesRepo, repositoriesRepo, projectsRepo, gitOps, lazyBus)

	claudeHome := os.Getenv("JARVIS_CLAUDE_HOME")
	if claudeHome == "" {
		claudeHome = filepath.Join(os.Getenv("HOME"), ".claude")
	}

	var rt sandbox.Runtime = sandbox.NewAijailRuntime()
	if os.Getenv("JARVIS_E2E_RUNTIME") == "fake" {
		rt = newE2EFakeRuntime()
	}

	catalogRoot := catalog.MustLoad()

	// Build the shared listener but don't start yet — mcp.NewServer needs
	// tasksSvc and projectsSvc; sessionsSvc needs localSrv (for BaseURL,
	// called lazily inside Start). All Mount calls happen before Start.
	localSrv := localhttp.New()
	if err := localSrv.Mount("/api/hooks/", hookHandler); err != nil {
		log.Fatalf("mount hooks: %v", err)
	}

	sessionsSvc := core.NewSessionsService(
		sessionsRepo, tasksRepo, worktreesRepo, projectsRepo, worktreesSvc,
		rt, tokenRegistry, localSrv, catalogRoot, lazyBus, claudeHome,
	)

	dockerOps := sandbox.NewSubprocessDockerOps()
	portAlloc := core.NewPortAllocator()
	runsRepo := store.NewRunsRepo(db)
	runsSvc := core.NewRunsService(
		runsRepo, dockerOps, portAlloc,
		tasksRepo, worktreesRepo, projectsRepo,
		lazyBus,
	)

	tasksSvc := core.NewTasksService(tasksRepo, catalogRoot, lazyBus,
		worktreesSvc.CleanupForTask,
		sessionsSvc.CleanupForTask,
		runsSvc.CleanupForTask,
	)

	mcpToken := mcp.NewBearerToken()
	mcpSrv := mcp.NewServer(tasksSvc, projectsSvc, catalogRoot, mcpToken)
	if err := localSrv.Mount("/api/mcp", mcpSrv.Handler()); err != nil {
		log.Fatalf("mount mcp: %v", err)
	}

	runsAPI := api.NewRunsAPI(runsSvc, func() string { return localSrv.BaseURL() })
	if err := localSrv.Mount("/api/runs/", runsAPI.LogsHandler()); err != nil {
		log.Fatalf("mount runs logs: %v", err)
	}

	hookPort, err := localSrv.Start()
	if err != nil {
		log.Fatalf("local http: %v", err)
	}
	log.Printf("local http listening on 127.0.0.1:%d", hookPort)
	defer func() { _ = localSrv.Stop() }()

	// Skip orphan cleanup if Docker is unavailable in CI (e.g. set
	// JARVIS_E2E_NO_DOCKER=1 in the harness).
	if os.Getenv("JARVIS_E2E_NO_DOCKER") != "1" {
		if err := runsSvc.CleanupOrphans(context.Background()); err != nil {
			log.Printf("orphan run cleanup: %v", err)
		}
	}
	tasksAPI := api.NewTasksAPI(tasksSvc)
	projectsAPI := api.NewProjectsAPI(projectsSvc)
	worktreesAPI := api.NewWorktreesAPI(worktreesSvc)
	sessionsAPI := api.NewSessionsAPI(sessionsSvc)

	masterRepo := store.NewMasterSessionRepo(db)
	masterSvc := core.NewMasterService(
		masterRepo,
		master.New(),
		func() string { return localSrv.BaseURL() },
		mcpToken.Value(),
		filepath.Join(os.TempDir(), "jarvis-e2e-master"),
		lazyBus,
	)
	masterAPI := api.NewMasterAPI(masterSvc, lazyBus)
	defer func() { _ = masterSvc.Stop(context.Background()) }()

	srv := api.NewE2EServer(tasksAPI, projectsAPI, worktreesAPI, sessionsAPI, masterAPI)
	// Wire the hook proxy + token reverse-lookup for /e2e/sessions/simulate_hook
	// and /e2e/sessions/__token BEFORE Start: Start spawns the serving goroutine,
	// so these writes must happen-before it to avoid a data race.
	srv.SetHookBase(localSrv.BaseURL())
	srv.SetTokenRegistry(tokenRegistry)
	if _, err := srv.Start(); err != nil {
		log.Fatalf("e2e server start: %v", err)
	}
	defer srv.Stop()

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
	<-sig
}

// e2eFakeRuntime returns a fixed PID without forking — used by Playwright
// tests that don't need a real subprocess. Kill is a no-op.
type e2eFakeRuntime struct{}

func (e2eFakeRuntime) Spawn(_ context.Context, _ sandbox.RuntimeSpec) (sandbox.Handle, error) {
	return sandbox.Handle{PID: 99999}, nil
}

func (e2eFakeRuntime) Kill(_ context.Context, _ sandbox.Handle) error { return nil }

func newE2EFakeRuntime() sandbox.Runtime { return e2eFakeRuntime{} }
