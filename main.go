package main

import (
	"context"
	"embed"
	"log"
	"os"
	"path/filepath"
	"sync/atomic"

	"github.com/marcosdid/jarvis/internal/api"
	"github.com/marcosdid/jarvis/internal/catalog"
	"github.com/marcosdid/jarvis/internal/core"
	"github.com/marcosdid/jarvis/internal/events"
	jgit "github.com/marcosdid/jarvis/internal/git"
	"github.com/marcosdid/jarvis/internal/hooks"
	"github.com/marcosdid/jarvis/internal/localhttp"
	"github.com/marcosdid/jarvis/internal/master"
	"github.com/marcosdid/jarvis/internal/mcp"
	"github.com/marcosdid/jarvis/internal/osintegration"
	"github.com/marcosdid/jarvis/internal/sandbox"
	"github.com/marcosdid/jarvis/internal/store"

	"github.com/wailsapp/wails/v2"
	"github.com/wailsapp/wails/v2/pkg/options"
	"github.com/wailsapp/wails/v2/pkg/options/assetserver"
	wruntime "github.com/wailsapp/wails/v2/pkg/runtime" // alias avoids shadowing the local `runtime` var declared inside main()
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

func masterCwdDefault() string {
	if v := os.Getenv("JARVIS_MASTER_CWD"); v != "" {
		return v
	}
	return filepath.Join(os.Getenv("HOME"), ".local", "share", "j-arvis", "master")
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
	hookHandler := hooks.NewHandler(tokenRegistry, lazyBus, hookUpdater)

	gitOps := jgit.NewSubprocessOps()
	projectsSvc := core.NewProjectsService(projectsRepo, repositoriesRepo, tasksRepo, lazyBus)
	worktreesSvc := core.NewWorktreesService(worktreesRepo, repositoriesRepo, projectsRepo, gitOps, lazyBus)

	claudeHome := os.Getenv("JARVIS_CLAUDE_HOME")
	if claudeHome == "" {
		claudeHome = filepath.Join(os.Getenv("HOME"), ".claude")
	}

	catalogRoot := catalog.MustLoad()

	// Build the shared listener but DON'T start it yet — mcp.NewServer needs
	// tasksSvc and projectsSvc, and sessionsSvc needs the listener (for
	// BaseURL, called lazily inside Start). All Mount calls happen before
	// Start to avoid the data race we hit in F10.4.20.
	localSrv := localhttp.New()
	if err := localSrv.Mount("/api/hooks/", hookHandler); err != nil {
		log.Fatalf("mount hooks: %v", err)
	}

	runtime := sandbox.NewAijailRuntime()
	sessionsSvc := core.NewSessionsService(
		sessionsRepo, tasksRepo, worktreesRepo, projectsRepo, worktreesSvc,
		runtime, tokenRegistry, localSrv, catalogRoot, lazyBus, claudeHome,
	)

	dockerOps := sandbox.NewSubprocessDockerOps()
	portAlloc := core.NewPortAllocator()
	runsRepo := store.NewRunsRepo(db)
	runsSvc := core.NewRunsService(
		runsRepo, dockerOps, portAlloc,
		tasksRepo, worktreesRepo, projectsRepo,
		lazyBus,
	)

	bootstrapSvc := core.NewBootstrapService(
		runtime, worktreesSvc, worktreesRepo, tasksRepo, catalogRoot, lazyBus,
	)

	tasksSvc := core.NewTasksService(tasksRepo, catalogRoot, lazyBus,
		worktreesSvc.CleanupForTask,
		sessionsSvc.CleanupForTask,
		runsSvc.CleanupForTask,
		bootstrapSvc.CleanupForTask,
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

	sandboxOK := true
	var sandboxReason string
	if port, err := localSrv.Start(); err != nil {
		log.Printf("local http bind failed: %v", err)
		sandboxOK = false
		sandboxReason = "local http server failed to bind: " + err.Error()
	} else {
		log.Printf("local http listening on 127.0.0.1:%d", port)
		// Boot-time orphan cleanup (best-effort) — kills containers/networks
		// that survived a previous crash. Skipped silently if docker is gone.
		if err := runsSvc.CleanupOrphans(context.Background()); err != nil {
			log.Printf("orphan run cleanup: %v", err)
		}
		// Defensive port reserve from any surviving rows so we don't hand the
		// same host port to a new run while an old one is still bound.
		if active, err := runsRepo.ListActive(context.Background()); err == nil {
			for _, run := range active {
				for _, port := range run.Ports() {
					portAlloc.Reserve(port)
				}
			}
		} else {
			log.Printf("list active runs: %v", err)
		}
	}
	if err := sandbox.SandboxAvailable(); err != nil {
		sandboxOK = false
		if sandboxReason == "" {
			sandboxReason = sandbox.DiagnoseSandbox()
		}
	}

	tasksAPI := api.NewTasksAPI(tasksSvc)
	catalogAPI := api.NewCatalogAPI(catalogRoot)
	projectsAPI := api.NewProjectsAPI(projectsSvc)
	worktreesAPI := api.NewWorktreesAPI(worktreesSvc)
	sessionsAPI := api.NewSessionsAPI(sessionsSvc)
	bootstrapAPI := api.NewBootstrapAPI(bootstrapSvc)

	masterRepo := store.NewMasterSessionRepo(db)
	masterSvc := core.NewMasterService(
		masterRepo,
		master.New(),
		func() string { return localSrv.BaseURL() },
		mcpToken.Value(),
		masterCwdDefault(),
		lazyBus,
	)
	masterAPI := api.NewMasterAPI(masterSvc, lazyBus)
	healthAPI := api.NewHealthAPI(func() (bool, string) {
		return sandboxOK, sandboxReason
	})

	startE2EServer(tasksAPI, projectsAPI, worktreesAPI, sessionsAPI, masterAPI)

	cliFlags := osintegration.ParseFlags()
	_ = cliFlags // Focus flag is informational; handler always focuses regardless
	trayAvailable := osintegration.PreflightOK()

	// appCtxPtr is written once from Wails main thread (OnStartup), read from
	// multiple goroutines (tray menuLoop + Wails D-Bus listener for
	// handleSecondInstance). atomic.Pointer matches the existing realBus
	// pattern in this file (line 65).
	var appCtxPtr atomic.Pointer[context.Context]

	onShow := func() {
		if p := appCtxPtr.Load(); p != nil {
			wruntime.WindowShow(*p)
			wruntime.WindowUnminimise(*p)
		}
	}
	onQuit := func() {
		if p := appCtxPtr.Load(); p != nil {
			wruntime.Quit(*p)
		}
	}

	handleSecondInstance := func(_ options.SecondInstanceData) {
		// Always focus, regardless of args. --focus is documented intent only today.
		// Note: this callback may fire BEFORE OnStartup completes if a second
		// instance launches immediately. In that case appCtxPtr.Load() returns
		// nil and we skip the focus — best-effort, no panic.
		if p := appCtxPtr.Load(); p != nil {
			wruntime.WindowShow(*p)
			wruntime.WindowUnminimise(*p)
		}
	}

	trayCtl := osintegration.NewTrayController(onShow, onQuit)

	appOpts := &options.App{
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
			ctxCopy := c
			appCtxPtr.Store(&ctxCopy) // make ctx visible to other goroutines
			if trayAvailable {
				// Start runs synchronously (assigns t.lib/start/end) and then
				// launches the lib's start function in its own goroutine internally.
				// This sequences the field writes before OnShutdown can read them.
				trayCtl.Start(c)
			}
		},
		OnShutdown: func(_ context.Context) {
			// Stop tray FIRST — UI ops sumir antes das domain ops. This
			// cascades through end() → nativeEnd → onExit → swap (no-op if
			// user already clicked Quit, else triggers onQuit).
			if trayAvailable {
				trayCtl.Stop()
			}
			// Stop master FIRST (of the domain ops) — its subprocess writes
			// to .claude/settings.json which references localSrv's URL.
			// Stopping localSrv first would leave the master claude process
			// making requests against a closed listener.
			if err := masterSvc.Stop(context.Background()); err != nil {
				log.Printf("master shutdown: %v", err)
			}
			if err := localSrv.Stop(); err != nil {
				log.Printf("local http shutdown: %v", err)
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
			catalogAPI,
			runsAPI,
			bootstrapAPI,
		},
		// mcpSrv is mounted on localSrv directly — not bound to Wails (it's
		// consumed by master-claude over HTTP, not by the UI).
	}

	if trayAvailable {
		appOpts.HideWindowOnClose = true
		appOpts.SingleInstanceLock = &options.SingleInstanceLock{
			UniqueId:               "com.marcosdid.jarvis",
			OnSecondInstanceLaunch: handleSecondInstance,
		}
	}

	wailsErr := wails.Run(appOpts)
	if wailsErr != nil {
		// OnShutdown does not fire if Run fails before the window opens.
		_ = localSrv.Stop()
		log.Fatalf("wails.Run: %v", wailsErr)
	}
}
