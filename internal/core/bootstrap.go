package core

import (
	"context"
	_ "embed"
	"errors"
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
	task, err := b.tasks.Get(ctx, taskID)
	if err != nil {
		return nil, err
	}
	if IsTerminal(task.State) {
		return nil, ErrTaskInTerminalState
	}
	return nil, errors.New("Start: not implemented yet")
}
