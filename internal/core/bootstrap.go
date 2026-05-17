package core

import (
	"context"
	_ "embed"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/fsnotify/fsnotify"
	"github.com/google/uuid"

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
	terminal, err := sandbox.DetectTerminal()
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrSandboxUnavailable, err)
	}

	task, err := b.tasks.Get(ctx, taskID)
	if err != nil {
		return nil, err
	}
	if IsTerminal(task.State) {
		return nil, ErrTaskInTerminalState
	}

	b.mu.Lock()
	if existing, ok := b.active[taskID]; ok {
		b.mu.Unlock()
		return b.viewFromEntry(existing), nil
	}
	b.mu.Unlock()

	cwd, err := b.resolveCwd(ctx, taskID, task)
	if err != nil {
		return nil, err
	}

	manifestPath := filepath.Join(cwd, ".orchestrator", "run.yml")
	if _, err := os.Stat(manifestPath); err == nil {
		return nil, ErrManifestAlreadyExists
	}

	profile, err := b.catalog.ResolveProfile(b.catalog.FallbackPermissionProfile)
	if err != nil {
		return nil, fmt.Errorf("resolve fallback profile: %w", err)
	}

	orchDir := filepath.Join(cwd, ".orchestrator")
	if err := os.MkdirAll(orchDir, 0o755); err != nil {
		return nil, fmt.Errorf("mkdir .orchestrator: %w", err)
	}
	promptPath := filepath.Join(orchDir, "BOOTSTRAP_PROMPT.md")
	if err := os.WriteFile(promptPath, []byte(bootstrapPromptTemplate), 0o644); err != nil {
		return nil, fmt.Errorf("write BOOTSTRAP_PROMPT.md: %w", err)
	}
	if err := sandbox.WriteAijailConfig(cwd, profile.ClaudeArgs, nil); err != nil {
		_ = os.Remove(promptPath)
		return nil, fmt.Errorf("write .ai-jail: %w", err)
	}

	watcher, err := fsnotify.NewWatcher()
	if err != nil {
		_ = sandbox.RemoveAijailConfig(cwd)
		_ = os.Remove(promptPath)
		return nil, fmt.Errorf("new fsnotify watcher: %w", err)
	}
	if err := watcher.Add(orchDir); err != nil {
		_ = watcher.Close()
		_ = sandbox.RemoveAijailConfig(cwd)
		_ = os.Remove(promptPath)
		return nil, fmt.Errorf("watcher.Add: %w", err)
	}

	handle, err := b.runtime.Spawn(ctx, sandbox.RuntimeSpec{Cwd: cwd, Terminal: terminal})
	if err != nil {
		_ = watcher.Close()
		_ = sandbox.RemoveAijailConfig(cwd)
		_ = os.Remove(promptPath)
		return nil, fmt.Errorf("spawn bootstrap claude: %w", err)
	}

	watcherCtx, cancel := context.WithCancel(context.Background())
	ready := make(chan struct{})
	entry := &bootstrapEntry{
		sessionID:    uuid.NewString(),
		cwd:          cwd,
		handle:       handle,
		watcher:      watcher,
		cancel:       cancel,
		watcherReady: ready,
		startedAt:    time.Now(),
	}

	b.mu.Lock()
	// Double-check under lock — caller raced us.
	if existing, ok := b.active[taskID]; ok {
		b.mu.Unlock()
		_ = b.runtime.Kill(ctx, handle)
		cancel()
		_ = watcher.Close()
		_ = sandbox.RemoveAijailConfig(cwd)
		_ = os.Remove(promptPath)
		return b.viewFromEntry(existing), nil
	}
	b.active[taskID] = entry
	b.mu.Unlock()

	// Stage 5 wires the watcher goroutine. For now, close ready immediately
	// so happy-path tests don't block on it.
	close(ready)
	_ = watcherCtx // used by Stage 5

	return b.viewFromEntry(entry), nil
}

func (b *BootstrapService) viewFromEntry(e *bootstrapEntry) *StartedBootstrap {
	return &StartedBootstrap{
		SessionID:    e.sessionID,
		Cwd:          e.cwd,
		ManifestPath: filepath.Join(e.cwd, ".orchestrator", "run.yml"),
		PromptPath:   filepath.Join(e.cwd, ".orchestrator", "BOOTSTRAP_PROMPT.md"),
		WatcherReady: e.watcherReady,
	}
}

// Cancel kills the bootstrap runtime, closes the watcher, removes the prompt
// file, and drops the entry from active. Idempotent — no-op if the entry
// doesn't exist. Tolerant — runtime.Kill failures are logged, not propagated.
func (b *BootstrapService) Cancel(ctx context.Context, taskID string) error {
	b.mu.Lock()
	entry, ok := b.active[taskID]
	if !ok {
		b.mu.Unlock()
		return nil
	}
	delete(b.active, taskID)
	b.mu.Unlock()

	entry.cancel()
	_ = entry.watcher.Close()
	if err := b.runtime.Kill(ctx, entry.handle); err != nil {
		log.Printf("bootstrap cancel: kill pid %d: %v", entry.handle.PID, err)
	}
	_ = os.Remove(filepath.Join(entry.cwd, ".orchestrator", "BOOTSTRAP_PROMPT.md"))
	return nil
}

// CleanupForTask is the signature TasksService expects for terminal-state
// cleanup. Delegates to Cancel.
func (b *BootstrapService) CleanupForTask(ctx context.Context, taskID string) error {
	return b.Cancel(ctx, taskID)
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
