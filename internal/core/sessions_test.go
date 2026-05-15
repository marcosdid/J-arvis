package core

import (
	"context"
	"database/sql"
	"errors"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/marcosdid/jarvis/internal/catalog"
	"github.com/marcosdid/jarvis/internal/events"
	"github.com/marcosdid/jarvis/internal/hooks"
	"github.com/marcosdid/jarvis/internal/sandbox"
	"github.com/marcosdid/jarvis/internal/store"
)

// fakeRuntime is a sandbox.Runtime double that never forks.
type fakeRuntime struct {
	nextPID  int
	spawnErr error
	killErr  error
	spawned  []sandbox.RuntimeSpec
	killed   []sandbox.Handle
}

func newFakeRuntime() *fakeRuntime { return &fakeRuntime{nextPID: 1000} }

func (f *fakeRuntime) Spawn(_ context.Context, spec sandbox.RuntimeSpec) (sandbox.Handle, error) {
	if f.spawnErr != nil {
		return sandbox.Handle{}, f.spawnErr
	}
	f.spawned = append(f.spawned, spec)
	f.nextPID++
	return sandbox.Handle{PID: f.nextPID}, nil
}

func (f *fakeRuntime) Kill(_ context.Context, h sandbox.Handle) error {
	f.killed = append(f.killed, h)
	return f.killErr
}

type fakeHookServer struct{ baseURL string }

func (f *fakeHookServer) BaseURL() string { return f.baseURL }

// newSessionsServiceForTest constructs a SessionsService with real DB + fake
// runtime/hooks. Returns the service and the DB so tests can seed rows.
// seedProjectAndTask inserts a project + a single task into the DB.
// Used by sessions tests to satisfy task-lookup paths without forking.
func seedProjectAndTask(t *testing.T, db *sql.DB, projectID, taskID string) {
	t.Helper()
	now := time.Now()
	if _, err := db.Exec(
		`INSERT INTO projects(id, name, path, created_at) VALUES (?, ?, ?, ?)`,
		projectID, projectID, "/tmp/"+projectID, now,
	); err != nil {
		t.Fatalf("seed project: %v", err)
	}
	if _, err := db.Exec(
		`INSERT INTO tasks(id, project_id, title, state, created_at, updated_at)
		 VALUES (?, ?, ?, 'idea', ?, ?)`,
		taskID, projectID, "t", now, now,
	); err != nil {
		t.Fatalf("seed task: %v", err)
	}
}

func newSessionsServiceForTest(t *testing.T) (*SessionsService, *sql.DB, string) {
	t.Helper()
	db := newTestStoreDB(t)
	projectsRepo := store.NewProjectsRepo(db)
	reposRepo := store.NewRepositoriesRepo(db)
	tasksRepo := store.NewTasksRepo(db)
	wtRepo := store.NewWorktreesRepo(db)
	sessRepo := store.NewSessionsRepo(db)
	bus := &events.FakeEmitter{}

	// Reuse the package-level fakeGit defined in fake_git_test.go (created in F10.3).
	wtSvc := NewWorktreesService(wtRepo, reposRepo, projectsRepo, newFakeGit(), bus)
	svc := NewSessionsService(
		sessRepo, tasksRepo, wtRepo, projectsRepo, wtSvc,
		newFakeRuntime(),
		hooks.NewTokenRegistry(),
		&fakeHookServer{baseURL: "http://127.0.0.1:55555"},
		catalog.MustLoad(),
		bus, t.TempDir(),
	)
	return svc, db, t.TempDir()
}

func TestSessionsService_Start_RejectsWhenSandboxUnavailable(t *testing.T) {
	// Strip PATH so SandboxAvailable() fails (no ai-jail, no terminals).
	t.Setenv("PATH", t.TempDir())
	t.Setenv("JARVIS_TERMINAL", "")

	svc, db, _ := newSessionsServiceForTest(t)
	seedProjectAndTask(t, db, "p1", "task-1")

	_, err := svc.Start(context.Background(), "task-1")
	if !errors.Is(err, ErrSandboxUnavailable) {
		t.Errorf("want ErrSandboxUnavailable, got %v", err)
	}
}

func TestSessionsService_Stop_NotFound(t *testing.T) {
	svc, _, _ := newSessionsServiceForTest(t)
	err := svc.Stop(context.Background(), "does-not-exist")
	if !errors.Is(err, store.ErrSessionNotFound) {
		t.Errorf("want ErrSessionNotFound, got %v", err)
	}
}

func TestSessionsService_Stop_AlreadyEndedIsNoop(t *testing.T) {
	svc, db, _ := newSessionsServiceForTest(t)
	seedProjectAndTask(t, db, "p1", "task-1")

	sessRepo := store.NewSessionsRepo(db)
	pid := 1
	_ = sessRepo.Insert(context.Background(), store.Session{
		ID: "sid-1", TaskID: "task-1", Status: "done",
		PID: &pid, Cwd: "/tmp", HookToken: "tok", StartedAt: time.Now(),
	})
	end := time.Now()
	_ = sessRepo.MarkEnded(context.Background(), "sid-1", "done")
	_ = end

	if err := svc.Stop(context.Background(), "sid-1"); err != nil {
		t.Errorf("Stop of already-ended session should be no-op, got %v", err)
	}
}

func TestSessionsService_ListByTask_Empty(t *testing.T) {
	svc, db, _ := newSessionsServiceForTest(t)
	seedProjectAndTask(t, db, "p1", "task-1")

	got, err := svc.ListByTask(context.Background(), "task-1")
	if err != nil {
		t.Fatalf("ListByTask: %v", err)
	}
	if len(got) != 0 {
		t.Errorf("want empty, got %d", len(got))
	}
}

func TestSessionsService_CleanupForTask_NoActiveSessions(t *testing.T) {
	svc, db, _ := newSessionsServiceForTest(t)
	seedProjectAndTask(t, db, "p1", "task-1")

	if err := svc.CleanupForTask(context.Background(), "task-1"); err != nil {
		t.Errorf("CleanupForTask with no sessions: %v", err)
	}
}

func TestSessionsService_GetTranscript_NoFiles(t *testing.T) {
	svc, db, _ := newSessionsServiceForTest(t)
	seedProjectAndTask(t, db, "p1", "task-1")

	sessRepo := store.NewSessionsRepo(db)
	pid := 1
	_ = sessRepo.Insert(context.Background(), store.Session{
		ID: "sid-1", TaskID: "task-1", Status: "executing",
		PID: &pid, Cwd: filepath.Join(t.TempDir(), "wt"),
		HookToken: "tok", StartedAt: time.Now(),
	})

	msgs, err := svc.GetTranscript(context.Background(), "sid-1")
	if err != nil {
		t.Fatalf("GetTranscript: %v", err)
	}
	if len(msgs) != 0 {
		t.Errorf("want 0 msgs (no JSONL exist), got %d", len(msgs))
	}
}

func TestTaskBranchOrSlug(t *testing.T) {
	br := "feat/x"
	tk := &store.Task{ID: "abc", Branch: &br}
	if got := taskBranchOrSlug(tk); got != "feat/x" {
		t.Errorf("with branch: got %q, want feat/x", got)
	}
	tkNoBr := &store.Task{ID: "abc"}
	if got := taskBranchOrSlug(tkNoBr); got != "task-abc" {
		t.Errorf("no branch: got %q, want task-abc", got)
	}
	empty := ""
	tkEmpty := &store.Task{ID: "abc", Branch: &empty}
	if got := taskBranchOrSlug(tkEmpty); got != "task-abc" {
		t.Errorf("empty branch: got %q, want task-abc", got)
	}
	_ = os.Getenv // keep import
}
