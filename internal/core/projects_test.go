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
