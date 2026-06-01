package core

import (
	"context"
	"database/sql"
	"errors"
	"os"
	"path/filepath"
	"testing"

	"github.com/marcosdid/jarvis/internal/events"
	jgit "github.com/marcosdid/jarvis/internal/git"
	"github.com/marcosdid/jarvis/internal/store"
)

// newTestStoreDB opens a fresh SQLite at t.TempDir() and applies all migrations.
func newTestStoreDB(t *testing.T) *sql.DB {
	t.Helper()
	dbPath := filepath.Join(t.TempDir(), "test.db")
	db, err := store.Open(context.Background(), dbPath)
	if err != nil {
		t.Fatalf("store.Open: %v", err)
	}
	if err := store.Migrate(context.Background(), db); err != nil {
		t.Fatalf("store.Migrate: %v", err)
	}
	t.Cleanup(func() { _ = db.Close() })
	return db
}

func mkRepoDir(t *testing.T, parent, name string) string {
	t.Helper()
	p := filepath.Join(parent, name)
	if err := os.MkdirAll(filepath.Join(p, ".git"), 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	return p
}

func newProjectsServiceUnderTest(t *testing.T, db *sql.DB, bus events.Emitter) *ProjectsService {
	t.Helper()
	return NewProjectsService(
		store.NewProjectsRepo(db),
		store.NewRepositoriesRepo(db),
		store.NewTasksRepo(db),
		bus,
	)
}

func TestProjectsService_Create_Monorepo(t *testing.T) {
	db := newTestStoreDB(t)
	bus := &events.FakeEmitter{}
	svc := newProjectsServiceUnderTest(t, db, bus)
	path := mkRepoDir(t, t.TempDir(), "proj")
	p, err := svc.Create(context.Background(), CreateProjectInput{Name: "proj", Path: path})
	if err != nil {
		t.Fatalf("Create: %v", err)
	}
	if len(p.Repositories) != 1 || p.Repositories[0].SubPath != "." {
		t.Errorf("want monorepo, got %+v", p.Repositories)
	}
	if len(bus.Calls) != 1 || bus.Calls[0].Name != "project.created" {
		t.Errorf("expected project.created emit, got %+v", bus.Calls)
	}
}

func TestProjectsService_Create_MultiRepo(t *testing.T) {
	db := newTestStoreDB(t)
	bus := &events.FakeEmitter{}
	svc := newProjectsServiceUnderTest(t, db, bus)
	base := t.TempDir()
	mkRepoDir(t, base, "alpha")
	mkRepoDir(t, base, "beta")
	p, err := svc.Create(context.Background(), CreateProjectInput{Name: "umbrella", Path: base})
	if err != nil {
		t.Fatalf("Create: %v", err)
	}
	if len(p.Repositories) != 2 {
		t.Fatalf("want 2 repos, got %d", len(p.Repositories))
	}
	if p.Repositories[0].SubPath != "alpha" || p.Repositories[1].SubPath != "beta" {
		t.Errorf("order: %+v", p.Repositories)
	}
}

func TestProjectsService_Create_NoGitRepos_Returns422Error(t *testing.T) {
	db := newTestStoreDB(t)
	bus := &events.FakeEmitter{}
	svc := newProjectsServiceUnderTest(t, db, bus)
	emptyDir := t.TempDir()
	_, err := svc.Create(context.Background(), CreateProjectInput{Name: "x", Path: emptyDir})
	if !errors.Is(err, jgit.ErrNoGitRepos) {
		t.Errorf("want ErrNoGitRepos, got %v", err)
	}
}

func TestProjectsService_Delete_RejectsWithTasks(t *testing.T) {
	db := newTestStoreDB(t)
	bus := &events.FakeEmitter{}
	svc := newProjectsServiceUnderTest(t, db, bus)
	path := mkRepoDir(t, t.TempDir(), "p")
	p, _ := svc.Create(context.Background(), CreateProjectInput{Name: "p", Path: path})
	tasksRepo := store.NewTasksRepo(db)
	if _, err := tasksRepo.Create(context.Background(), store.CreateTaskInput{
		ProjectID: p.ID, Title: "t",
	}); err != nil {
		t.Fatalf("seed task: %v", err)
	}
	err := svc.Delete(context.Background(), p.ID)
	if !errors.Is(err, ProjectHasTasksError) {
		t.Errorf("want ProjectHasTasksError, got %v", err)
	}
}

// TestProjectsService_RescanRepositories_AddsNewRepos covers the gcb-hub
// scenario: the project was created when DetectRepos still had the early-
// return bug, so only 1 repo was registered. The user adds (or already had)
// sub-repos on disk. Rescan must detect those new sub-repos and insert them,
// without touching tasks or the existing repository rows.
func TestProjectsService_RescanRepositories_AddsNewRepos(t *testing.T) {
	db := newTestStoreDB(t)
	bus := &events.FakeEmitter{}
	svc := newProjectsServiceUnderTest(t, db, bus)

	// Start: only root repo on disk.
	base := t.TempDir()
	root := filepath.Join(base, "umbrella")
	if err := os.MkdirAll(filepath.Join(root, ".git"), 0o755); err != nil {
		t.Fatalf("mkdir root .git: %v", err)
	}
	p, err := svc.Create(context.Background(), CreateProjectInput{Name: "umbrella", Path: root})
	if err != nil {
		t.Fatalf("Create: %v", err)
	}
	if len(p.Repositories) != 1 {
		t.Fatalf("setup: expected 1 repo, got %d", len(p.Repositories))
	}

	// Later: user adds sub-repos backend and frontend in the same dir.
	if err := os.MkdirAll(filepath.Join(root, "backend", ".git"), 0o755); err != nil {
		t.Fatalf("mkdir backend .git: %v", err)
	}
	if err := os.MkdirAll(filepath.Join(root, "frontend", ".git"), 0o755); err != nil {
		t.Fatalf("mkdir frontend .git: %v", err)
	}

	bus.Calls = nil
	updated, err := svc.RescanRepositories(context.Background(), p.ID)
	if err != nil {
		t.Fatalf("RescanRepositories: %v", err)
	}
	if len(updated.Repositories) != 3 {
		t.Fatalf("expected 3 repos after rescan, got %d: %+v", len(updated.Repositories), updated.Repositories)
	}
	names := map[string]string{}
	for _, r := range updated.Repositories {
		names[r.Name] = r.SubPath
	}
	if names["umbrella"] != "." {
		t.Errorf("umbrella SubPath: got %q, want '.'", names["umbrella"])
	}
	if names["backend"] != "backend" {
		t.Errorf("backend SubPath: got %q, want 'backend'", names["backend"])
	}
	if names["frontend"] != "frontend" {
		t.Errorf("frontend SubPath: got %q, want 'frontend'", names["frontend"])
	}
	if len(bus.Calls) != 1 || bus.Calls[0].Name != "project.updated" {
		t.Errorf("expected project.updated emit, got %+v", bus.Calls)
	}
}

// TestProjectsService_RescanRepositories_NoChanges is the idempotent case:
// running Rescan when the DB is already in sync should be a no-op (no inserts,
// no events).
func TestProjectsService_RescanRepositories_NoChanges(t *testing.T) {
	db := newTestStoreDB(t)
	bus := &events.FakeEmitter{}
	svc := newProjectsServiceUnderTest(t, db, bus)
	path := mkRepoDir(t, t.TempDir(), "p")
	p, _ := svc.Create(context.Background(), CreateProjectInput{Name: "p", Path: path})

	bus.Calls = nil
	updated, err := svc.RescanRepositories(context.Background(), p.ID)
	if err != nil {
		t.Fatalf("RescanRepositories: %v", err)
	}
	if len(updated.Repositories) != 1 {
		t.Errorf("expected 1 repo unchanged, got %d", len(updated.Repositories))
	}
	if len(bus.Calls) != 0 {
		t.Errorf("expected no event on no-change rescan, got %+v", bus.Calls)
	}
}

func TestProjectsService_Delete_OK_EmitsEvent(t *testing.T) {
	db := newTestStoreDB(t)
	bus := &events.FakeEmitter{}
	svc := newProjectsServiceUnderTest(t, db, bus)
	path := mkRepoDir(t, t.TempDir(), "p")
	p, _ := svc.Create(context.Background(), CreateProjectInput{Name: "p", Path: path})
	bus.Calls = nil
	if err := svc.Delete(context.Background(), p.ID); err != nil {
		t.Fatalf("Delete: %v", err)
	}
	if len(bus.Calls) != 1 || bus.Calls[0].Name != "project.deleted" {
		t.Errorf("expected project.deleted emit, got %+v", bus.Calls)
	}
}
