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
	// F10.4.15 wires the real probe; placeholder defaults to false until then.
	health := api.NewHealthAPI(nil)

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

	gitOps := jgit.NewSubprocessOps()
	projectsSvc := core.NewProjectsService(projectsRepo, repositoriesRepo, tasksRepo, lazyBus)
	worktreesSvc := core.NewWorktreesService(worktreesRepo, repositoriesRepo, projectsRepo, gitOps, lazyBus)

	tasksAPI := api.NewTasksAPI(tasksRepo, lazyBus, worktreesSvc.CleanupForTask, nil)
	projectsAPI := api.NewProjectsAPI(projectsSvc)
	worktreesAPI := api.NewWorktreesAPI(worktreesSvc)
	masterAPI := api.NewMasterAPI(lazyBus, api.DefaultSessionFactory, os.Getenv("JARVIS_CLAUDE_BIN"))

	startE2EServer(tasksAPI, projectsAPI, worktreesAPI, masterAPI)

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
		Bind: []any{
			app,
			health,
			tasksAPI,
			projectsAPI,
			masterAPI,
			worktreesAPI,
		},
	})
	if wailsErr != nil {
		log.Fatalf("wails.Run: %v", wailsErr)
	}
}
