package main

import (
	"context"
	"embed"
	"log"
	"os"
	"path/filepath"
	"sync/atomic"

	"github.com/marcosdid/jarvis/internal/api"
	"github.com/marcosdid/jarvis/internal/core"
	"github.com/marcosdid/jarvis/internal/events"
	jgit "github.com/marcosdid/jarvis/internal/git"
	"github.com/marcosdid/jarvis/internal/hooks"
	"github.com/marcosdid/jarvis/internal/sandbox"
	"github.com/marcosdid/jarvis/internal/store"

	"github.com/wailsapp/wails/v2"
	"github.com/wailsapp/wails/v2/pkg/options"
	"github.com/wailsapp/wails/v2/pkg/options/assetserver"
)

//go:embed all:ui/dist
var assets embed.FS

func dbPath() string {
	if explicit := os.Getenv("JARVIS_DB_PATH"); explicit != "" {
		_ = os.MkdirAll(filepath.Dir(explicit), 0o755)
		return explicit
	}
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

	var realBus atomic.Pointer[events.Emitter]
	lazyBus := &events.LazyEmitter{Resolve: func() events.Emitter {
		if p := realBus.Load(); p != nil {
			return *p
		}
		return nil
	}}

	tasksRepo := store.NewTasksRepo(db)
	projectsRepo := store.NewProjectsRepo(db)
	repositoriesRepo := store.NewRepositoriesRepo(db)
	worktreesRepo := store.NewWorktreesRepo(db)
	sessionsRepo := store.NewSessionsRepo(db)

	tokenRegistry := hooks.NewTokenRegistry()
	hookUpdater := store.NewSessionsHookAdapter(sessionsRepo)
	hookServer := hooks.NewServer(tokenRegistry, lazyBus, hookUpdater)

	sandboxOK := true
	var sandboxReason string
	if port, err := hookServer.Start(); err != nil {
		log.Printf("hook server bind failed: %v", err)
		sandboxOK = false
		sandboxReason = "hook server failed to bind: " + err.Error()
	} else {
		log.Printf("hook server listening on 127.0.0.1:%d", port)
	}
	if err := sandbox.SandboxAvailable(); err != nil {
		sandboxOK = false
		if sandboxReason == "" {
			sandboxReason = sandbox.DiagnoseSandbox()
		}
	}

	gitOps := jgit.NewSubprocessOps()
	projectsSvc := core.NewProjectsService(projectsRepo, repositoriesRepo, tasksRepo, lazyBus)
	worktreesSvc := core.NewWorktreesService(worktreesRepo, repositoriesRepo, projectsRepo, gitOps, lazyBus)

	claudeHome := os.Getenv("JARVIS_CLAUDE_HOME")
	if claudeHome == "" {
		claudeHome = filepath.Join(os.Getenv("HOME"), ".claude")
	}

	runtime := sandbox.NewAijailRuntime()
	sessionsSvc := core.NewSessionsService(
		sessionsRepo, tasksRepo, worktreesRepo, projectsRepo, worktreesSvc,
		runtime, tokenRegistry, hookServer, lazyBus, claudeHome,
	)

	tasksSvc := core.NewTasksService(tasksRepo, lazyBus, worktreesSvc.CleanupForTask, sessionsSvc.CleanupForTask)
	tasksAPI := api.NewTasksAPI(tasksSvc)
	projectsAPI := api.NewProjectsAPI(projectsSvc)
	worktreesAPI := api.NewWorktreesAPI(worktreesSvc)
	sessionsAPI := api.NewSessionsAPI(sessionsSvc)
	masterAPI := api.NewMasterAPI(lazyBus, api.DefaultSessionFactory, os.Getenv("JARVIS_CLAUDE_BIN"))
	healthAPI := api.NewHealthAPI(func() (bool, string) {
		return sandboxOK, sandboxReason
	})

	startE2EServer(tasksAPI, projectsAPI, worktreesAPI, sessionsAPI, masterAPI)

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
			emitter := events.Emitter(events.NewWailsEmitter(c))
			realBus.Store(&emitter)
		},
		OnShutdown: func(_ context.Context) {
			if err := hookServer.Stop(); err != nil {
				log.Printf("hook server shutdown: %v", err)
			}
		},
		Bind: []any{
			app,
			healthAPI,
			tasksAPI,
			projectsAPI,
			masterAPI,
			worktreesAPI,
			sessionsAPI,
		},
	})
	if wailsErr != nil {
		// OnShutdown does not fire if Run fails before the window opens.
		_ = hookServer.Stop()
		log.Fatalf("wails.Run: %v", wailsErr)
	}
}
