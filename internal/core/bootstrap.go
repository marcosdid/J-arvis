package core

import (
	"context"
	_ "embed"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/fsnotify/fsnotify"

	"github.com/marcosdid/jarvis/internal/catalog"
	"github.com/marcosdid/jarvis/internal/events"
	"github.com/marcosdid/jarvis/internal/sandbox"
	"github.com/marcosdid/jarvis/internal/store"
)

//go:embed bootstrap_prompt.md
var bootstrapPromptTemplate string

// StartedBootstrap is the Go-internal return type from BootstrapService.Start.
// The WatcherReady channel is closed by the watcher goroutine just before its
// first select iteration — tests use it as a sync barrier to avoid losing
// fsnotify events fired before the watcher began consuming the Events channel.
// The Wails-facing api.BootstrapView strips this field for JSON.
type StartedBootstrap struct {
	SessionID    string
	Cwd          string
	ManifestPath string
	PromptPath   string
	WatcherReady <-chan struct{}
}

// BootstrapProposedPayload is emitted on the "bootstrap.proposed" event when
// the watcher detects .orchestrator/run.yml (valid or not). JSON tags are
// explicit — events.LazyEmitter goes through json.Marshal and field names
// without tags would CamelCase and break the TypeScript payload type.
type BootstrapProposedPayload struct {
	TaskID       string   `json:"task_id"`
	SessionID    string   `json:"session_id"`
	ManifestText string   `json:"manifest_text"`
	Valid        bool     `json:"valid"`
	Errors       []string `json:"errors"`
}

type bootstrapEntry struct {
	sessionID    string
	cwd          string
	handle       sandbox.Handle
	watcher      *fsnotify.Watcher
	cancel       context.CancelFunc
	watcherReady chan struct{}
	startedAt    time.Time
}

// BootstrapService manages ephemeral Claude sessions whose purpose is to
// write a .orchestrator/run.yml manifest. State lives only in memory — no
// DB row (the bootstrap is conceptually a one-shot wizard, not a tracked
// session).
type BootstrapService struct {
	runtime   sandbox.Runtime
	wtSvc     *WorktreesService
	worktrees *store.WorktreesRepo
	tasks     *store.TasksRepo
	catalog   *catalog.Catalog
	bus       events.Emitter

	mu     sync.Mutex
	active map[string]*bootstrapEntry
}

func NewBootstrapService(
	runtime sandbox.Runtime,
	wtSvc *WorktreesService,
	worktrees *store.WorktreesRepo,
	tasks *store.TasksRepo,
	cat *catalog.Catalog,
	bus events.Emitter,
) *BootstrapService {
	return &BootstrapService{
		runtime: runtime, wtSvc: wtSvc, worktrees: worktrees, tasks: tasks,
		catalog: cat, bus: bus,
		active: make(map[string]*bootstrapEntry),
	}
}

func (b *BootstrapService) Start(ctx context.Context, taskID string) (*StartedBootstrap, error) {
	if err := sandbox.SandboxAvailable(); err != nil {
		return nil, fmt.Errorf("%w: %v", ErrSandboxUnavailable, err)
	}
	if _, err := sandbox.DetectTerminal(); err != nil {
		return nil, fmt.Errorf("%w: %v", ErrSandboxUnavailable, err)
	}

	task, err := b.tasks.Get(ctx, taskID)
	if err != nil {
		return nil, err
	}
	if IsTerminal(task.State) {
		return nil, ErrTaskInTerminalState
	}

	cwd, err := b.resolveCwd(ctx, taskID, task)
	if err != nil {
		return nil, err
	}

	manifestPath := filepath.Join(cwd, ".orchestrator", "run.yml")
	if _, err := os.Stat(manifestPath); err == nil {
		return nil, ErrManifestAlreadyExists
	}

	return nil, errors.New("Start: not implemented yet")
}

// resolveCwd mirrors SessionsService (internal/core/sessions.go:87) — if no
// worktree, create one. Uses the separately-injected b.worktrees repo (same
// pattern SessionsService uses for store.WorktreesRepo).
func (b *BootstrapService) resolveCwd(ctx context.Context, taskID string, task *store.Task) (string, error) {
	wts, err := b.worktrees.ListByTask(ctx, taskID)
	if err != nil {
		return "", err
	}
	if len(wts) == 0 {
		branch := taskBranchOrSlug(task)
		wts, err = b.wtSvc.CreateForTask(ctx, taskID, branch)
		if err != nil {
			return "", fmt.Errorf("create worktrees for task: %w", err)
		}
	}
	cwd := wts[0].Path
	if len(wts) > 1 {
		cwd = filepath.Dir(wts[0].Path)
	}
	return cwd, nil
}
