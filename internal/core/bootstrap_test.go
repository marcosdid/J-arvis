package core

import (
	"context"
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
// Task 3.8 will exercise this; for now it's an empty hook.
type bootstrapEnvOpt func(*bootstrapEnvConfig)
type bootstrapEnvConfig struct {
	// Task 3.8 fills this in. For Tasks 3.1-3.7, leave empty.
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

// Suppress "imported and not used" warnings on filepath until Task 3.4 needs it.
var _ = filepath.Join
