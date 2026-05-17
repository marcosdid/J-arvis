package core

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"

	"github.com/marcosdid/jarvis/internal/catalog"
	"github.com/marcosdid/jarvis/internal/events"
	"github.com/marcosdid/jarvis/internal/sandbox"
	"github.com/marcosdid/jarvis/internal/store"
)

func TestBootstrapPromptEmbedded(t *testing.T) {
	if len(bootstrapPromptTemplate) < 500 {
		t.Fatalf("bootstrap prompt seems empty or truncated: %d bytes", len(bootstrapPromptTemplate))
	}
	if !strings.Contains(bootstrapPromptTemplate, "version: \"1\"") {
		t.Error("prompt missing version: \"1\" example")
	}
	if !strings.Contains(bootstrapPromptTemplate, ".orchestrator/run.yml") {
		t.Error("prompt missing target path reference")
	}
}

// bootstrapFakeRuntime: noop spawn that records calls + supports an injected
// error. Mirrors sessions_test.go's fakeRuntime.
type bootstrapFakeRuntime struct {
	mu        sync.Mutex
	spawnErr  error
	spawnArgs []sandbox.RuntimeSpec
	killArgs  []sandbox.Handle
	killErr   error
	nextPID   int
}

func (r *bootstrapFakeRuntime) Spawn(_ context.Context, spec sandbox.RuntimeSpec) (sandbox.Handle, error) {
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.spawnErr != nil {
		return sandbox.Handle{}, r.spawnErr
	}
	r.spawnArgs = append(r.spawnArgs, spec)
	r.nextPID++
	return sandbox.Handle{PID: 10000 + r.nextPID}, nil
}

func (r *bootstrapFakeRuntime) Kill(_ context.Context, h sandbox.Handle) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.killArgs = append(r.killArgs, h)
	return r.killErr
}

func (r *bootstrapFakeRuntime) SpawnCount() int {
	r.mu.Lock()
	defer r.mu.Unlock()
	return len(r.spawnArgs)
}

func (r *bootstrapFakeRuntime) KillCount() int {
	r.mu.Lock()
	defer r.mu.Unlock()
	return len(r.killArgs)
}

// bootstrapEnvOpt lets tests inject overrides (e.g., a fakeGit that fails Add).
type bootstrapEnvOpt func(*bootstrapEnvConfig)
type bootstrapEnvConfig struct {
	gitAddWorktreeErr error
}

func withGitAddWorktreeErr(err error) bootstrapEnvOpt {
	return func(c *bootstrapEnvConfig) { c.gitAddWorktreeErr = err }
}

// bootstrapTestEnv bundles all the dependencies a bootstrap test needs.
type bootstrapTestEnv struct {
	svc          *BootstrapService
	runtime      *bootstrapFakeRuntime
	emitter      *events.FakeEmitter
	tasksRepo    *store.TasksRepo
	projectsRepo *store.ProjectsRepo
	reposRepo    *store.RepositoriesRepo
	wtsRepo      *store.WorktreesRepo
	gitOps       *fakeGit
	taskID       string
	worktree     string
	cleanup      func()
}

func newBootstrapTestEnv(t *testing.T, opts ...bootstrapEnvOpt) *bootstrapTestEnv {
	t.Helper()
	ctx := context.Background()

	cfg := &bootstrapEnvConfig{}
	for _, opt := range opts {
		opt(cfg)
	}

	db, err := store.Open(ctx, ":memory:")
	if err != nil {
		t.Fatalf("store.Open: %v", err)
	}
	if err := store.Migrate(ctx, db); err != nil {
		t.Fatalf("store.Migrate: %v", err)
	}

	projectsRepo := store.NewProjectsRepo(db)
	reposRepo := store.NewRepositoriesRepo(db)
	wtsRepo := store.NewWorktreesRepo(db)
	tasksRepo := store.NewTasksRepo(db)

	wt := t.TempDir()
	projRoot := t.TempDir()

	proj, err := projectsRepo.Create(ctx, store.CreateProjectInput{
		Name: "p", Path: projRoot,
	})
	if err != nil {
		t.Fatalf("Create project: %v", err)
	}
	repos, err := reposRepo.CreateBulk(ctx, proj.ID, []store.RepoSpecInput{
		{Name: "repo-a", SubPath: ""},
	})
	if err != nil {
		t.Fatalf("CreateBulk repo: %v", err)
	}
	repo := repos[0]

	task, err := tasksRepo.Create(ctx, store.CreateTaskInput{
		ProjectID: proj.ID, Title: "t", Description: "", State: "in_progress",
	})
	if err != nil {
		t.Fatalf("Create task: %v", err)
	}
	taskID := task.ID
	if _, err := wtsRepo.Upsert(ctx, store.WorktreeUpsert{
		RepositoryID: repo.ID, Path: wt, TaskID: &taskID,
	}); err != nil {
		t.Fatalf("Upsert worktree: %v", err)
	}

	cat := &catalog.Catalog{
		Version:                   "1",
		FallbackPermissionProfile: "fallback",
		PermissionProfiles: map[string]catalog.PermissionProfile{
			"fallback": {Name: "fallback", ClaudeArgs: []string{"--print"}},
		},
	}
	fake := &events.FakeEmitter{}
	runtime := &bootstrapFakeRuntime{}
	gitOps := newFakeGit()
	if cfg.gitAddWorktreeErr != nil {
		gitOps.AddErrors["*"] = cfg.gitAddWorktreeErr
	}
	wtSvc := NewWorktreesService(wtsRepo, reposRepo, projectsRepo, gitOps, fake)

	svc := NewBootstrapService(runtime, wtSvc, wtsRepo, tasksRepo, cat, fake)
	return &bootstrapTestEnv{
		svc:          svc,
		runtime:      runtime,
		emitter:      fake,
		tasksRepo:    tasksRepo,
		projectsRepo: projectsRepo,
		reposRepo:    reposRepo,
		wtsRepo:      wtsRepo,
		gitOps:       gitOps,
		taskID:       taskID,
		worktree:     wt,
		cleanup:      func() { _ = db.Close() },
	}
}

func TestStart_TaskInTerminalState(t *testing.T) {
	env := newBootstrapTestEnv(t)
	defer env.cleanup()
	ctx := context.Background()

	// Move task to terminal state ("done").
	if _, err := env.tasksRepo.UpdateState(ctx, env.taskID, "done"); err != nil {
		t.Fatalf("UpdateState: %v", err)
	}

	_, err := env.svc.Start(ctx, env.taskID)
	if !errors.Is(err, ErrTaskInTerminalState) {
		t.Fatalf("Start: err=%v, want ErrTaskInTerminalState", err)
	}
	if env.runtime.SpawnCount() != 0 {
		t.Errorf("spawn called %d times; want 0", env.runtime.SpawnCount())
	}
}

func TestStart_SandboxUnavailable(t *testing.T) {
	env := newBootstrapTestEnv(t)
	defer env.cleanup()
	// Force preflight failure by pointing PATH to an empty dir (ai-jail not found).
	t.Setenv("PATH", t.TempDir())

	_, err := env.svc.Start(context.Background(), env.taskID)
	if !errors.Is(err, ErrSandboxUnavailable) {
		t.Fatalf("Start: err=%v, want ErrSandboxUnavailable", err)
	}
	if env.runtime.SpawnCount() != 0 {
		t.Errorf("spawn called %d times; want 0", env.runtime.SpawnCount())
	}
}

func TestStart_ManifestAlreadyExists(t *testing.T) {
	env := newBootstrapTestEnv(t)
	defer env.cleanup()

	// Pre-create the manifest file.
	orchDir := filepath.Join(env.worktree, ".orchestrator")
	if err := os.MkdirAll(orchDir, 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	if err := os.WriteFile(filepath.Join(orchDir, "run.yml"), []byte("version: \"1\"\n"), 0o644); err != nil {
		t.Fatalf("write: %v", err)
	}

	_, err := env.svc.Start(context.Background(), env.taskID)
	if !errors.Is(err, ErrManifestAlreadyExists) {
		t.Fatalf("Start: err=%v, want ErrManifestAlreadyExists", err)
	}
	if env.runtime.SpawnCount() != 0 {
		t.Errorf("spawn called %d times; want 0", env.runtime.SpawnCount())
	}
}

func TestStart_HappyPath(t *testing.T) {
	env := newBootstrapTestEnv(t)
	defer env.cleanup()

	started, err := env.svc.Start(context.Background(), env.taskID)
	if err != nil {
		t.Fatalf("Start: %v", err)
	}
	if started == nil {
		t.Fatal("Start returned nil StartedBootstrap")
	}
	if started.SessionID == "" {
		t.Error("SessionID empty")
	}
	if started.Cwd != env.worktree {
		t.Errorf("Cwd=%q, want %q", started.Cwd, env.worktree)
	}
	wantManifest := filepath.Join(env.worktree, ".orchestrator", "run.yml")
	if started.ManifestPath != wantManifest {
		t.Errorf("ManifestPath=%q, want %q", started.ManifestPath, wantManifest)
	}
	wantPrompt := filepath.Join(env.worktree, ".orchestrator", "BOOTSTRAP_PROMPT.md")
	if started.PromptPath != wantPrompt {
		t.Errorf("PromptPath=%q, want %q", started.PromptPath, wantPrompt)
	}
	if started.WatcherReady == nil {
		t.Error("WatcherReady nil")
	}

	// Files on disk
	promptData, err := os.ReadFile(wantPrompt)
	if err != nil {
		t.Fatalf("ReadFile prompt: %v", err)
	}
	if !strings.Contains(string(promptData), ".orchestrator/run.yml") {
		t.Error("prompt missing schema reference")
	}
	if _, err := os.Stat(filepath.Join(env.worktree, ".ai-jail")); err != nil {
		t.Errorf(".ai-jail not written: %v", err)
	}

	// Spawn called once with correct cwd
	if got := env.runtime.SpawnCount(); got != 1 {
		t.Fatalf("spawn count=%d, want 1", got)
	}
}

func TestStart_IdempotentReturnsExisting(t *testing.T) {
	env := newBootstrapTestEnv(t)
	defer env.cleanup()
	ctx := context.Background()

	first, err := env.svc.Start(ctx, env.taskID)
	if err != nil {
		t.Fatalf("Start #1: %v", err)
	}
	second, err := env.svc.Start(ctx, env.taskID)
	if err != nil {
		t.Fatalf("Start #2: %v", err)
	}
	if first.SessionID != second.SessionID {
		t.Errorf("SessionID changed: %q vs %q", first.SessionID, second.SessionID)
	}
	if env.runtime.SpawnCount() != 1 {
		t.Errorf("spawn count=%d, want 1", env.runtime.SpawnCount())
	}
}

func TestStart_SpawnFailsCleansUp(t *testing.T) {
	env := newBootstrapTestEnv(t)
	defer env.cleanup()
	env.runtime.spawnErr = errors.New("forced spawn failure")

	_, err := env.svc.Start(context.Background(), env.taskID)
	if err == nil || !strings.Contains(err.Error(), "spawn bootstrap claude") {
		t.Fatalf("Start: err=%v, want spawn failure", err)
	}
	// Prompt and .ai-jail should NOT remain on disk.
	if _, err := os.Stat(filepath.Join(env.worktree, ".orchestrator", "BOOTSTRAP_PROMPT.md")); err == nil {
		t.Error("BOOTSTRAP_PROMPT.md leaked on disk after spawn failure")
	}
	if _, err := os.Stat(filepath.Join(env.worktree, ".ai-jail")); err == nil {
		t.Error(".ai-jail leaked on disk after spawn failure")
	}
}

func TestStart_WorktreeCreationFails(t *testing.T) {
	env := newBootstrapTestEnv(t, withGitAddWorktreeErr(errors.New("forced git failure")))
	defer env.cleanup()
	ctx := context.Background()

	// Drop the seeded worktree so resolveCwd calls CreateForTask (which hits the failing git).
	wts, _ := env.wtsRepo.ListByTask(ctx, env.taskID)
	for _, wt := range wts {
		_ = env.wtsRepo.Delete(ctx, wt.ID)
	}

	_, err := env.svc.Start(ctx, env.taskID)
	if err == nil || !strings.Contains(err.Error(), "create worktrees for task") {
		t.Fatalf("Start: err=%v, want worktree creation failure", err)
	}
	if env.runtime.SpawnCount() != 0 {
		t.Errorf("spawn count=%d, want 0", env.runtime.SpawnCount())
	}
}

func TestStart_MultiRepoWorktreeUsesParentDir(t *testing.T) {
	env := newBootstrapTestEnv(t)
	defer env.cleanup()
	ctx := context.Background()

	// Add a second repo in the same project + a worktree linked to env.taskID.
	parent := filepath.Dir(env.worktree)
	wt2 := filepath.Join(parent, "repo-b")
	if err := os.MkdirAll(wt2, 0o755); err != nil {
		t.Fatalf("mkdir wt2: %v", err)
	}

	task, err := env.tasksRepo.Get(ctx, env.taskID)
	if err != nil {
		t.Fatalf("Get task: %v", err)
	}
	repos, err := env.reposRepo.CreateBulk(ctx, task.ProjectID, []store.RepoSpecInput{
		{Name: "repo-b", SubPath: "b"},
	})
	if err != nil {
		t.Fatalf("CreateBulk repo-b: %v", err)
	}
	repo2 := repos[0]
	taskID := env.taskID
	if _, err := env.wtsRepo.Upsert(ctx, store.WorktreeUpsert{
		RepositoryID: repo2.ID, Path: wt2, TaskID: &taskID,
	}); err != nil {
		t.Fatalf("Upsert wt2: %v", err)
	}

	started, err := env.svc.Start(ctx, env.taskID)
	if err != nil {
		t.Fatalf("Start: %v", err)
	}
	if started.Cwd != parent {
		t.Errorf("Cwd=%q, want %q (parent of wts[0])", started.Cwd, parent)
	}
}

func TestCancel_HappyPath(t *testing.T) {
	env := newBootstrapTestEnv(t)
	defer env.cleanup()
	ctx := context.Background()

	started, err := env.svc.Start(ctx, env.taskID)
	if err != nil {
		t.Fatalf("Start: %v", err)
	}
	<-started.WatcherReady

	if err := env.svc.Cancel(ctx, env.taskID); err != nil {
		t.Fatalf("Cancel: %v", err)
	}

	if env.runtime.KillCount() != 1 {
		t.Errorf("kill count=%d, want 1", env.runtime.KillCount())
	}
	if _, err := os.Stat(started.PromptPath); err == nil {
		t.Error("BOOTSTRAP_PROMPT.md leaked after Cancel")
	}
	// Entry removed
	env.svc.mu.Lock()
	_, ok := env.svc.active[env.taskID]
	env.svc.mu.Unlock()
	if ok {
		t.Error("entry still in active map after Cancel")
	}
}

func TestCancel_UnknownTask(t *testing.T) {
	env := newBootstrapTestEnv(t)
	defer env.cleanup()
	if err := env.svc.Cancel(context.Background(), "no-such-task"); err != nil {
		t.Errorf("Cancel on unknown: err=%v, want nil", err)
	}
}

func TestCancel_Idempotent(t *testing.T) {
	env := newBootstrapTestEnv(t)
	defer env.cleanup()
	ctx := context.Background()
	if _, err := env.svc.Start(ctx, env.taskID); err != nil {
		t.Fatalf("Start: %v", err)
	}
	if err := env.svc.Cancel(ctx, env.taskID); err != nil {
		t.Fatalf("Cancel #1: %v", err)
	}
	if err := env.svc.Cancel(ctx, env.taskID); err != nil {
		t.Errorf("Cancel #2: err=%v, want nil (no-op)", err)
	}
	if env.runtime.KillCount() != 1 {
		t.Errorf("kill count=%d, want 1 (second Cancel should not kill again)", env.runtime.KillCount())
	}
}
