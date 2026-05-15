package store

import (
	"context"
	"database/sql"
	"errors"
	"testing"
	"time"
)

// seedTaskOnly inserts a task row assuming the project already exists.
// Use this when the project was seeded once in the test setup.
func seedTaskOnly(t *testing.T, db *sql.DB, taskID, projectID string) {
	t.Helper()
	_, err := db.Exec(
		`INSERT INTO tasks(id, project_id, title, state, created_at, updated_at)
		 VALUES (?, ?, ?, 'idea', ?, ?)`,
		taskID, projectID, "t", time.Now(), time.Now(),
	)
	if err != nil {
		t.Fatalf("seed task: %v", err)
	}
}

// seedTask combines seedProject + seedTaskOnly for tests that only need one
// task in one project.
func seedTask(t *testing.T, db *sql.DB, taskID, projectID string) {
	t.Helper()
	seedProject(t, db, projectID)
	seedTaskOnly(t, db, taskID, projectID)
}

func TestSessionsRepo_InsertAndGetByID(t *testing.T) {
	db := newTestDB(t)
	seedTask(t, db, "task-1", "proj-1")
	repo := NewSessionsRepo(db)
	pid := 1234
	in := Session{
		ID: "sid-1", TaskID: "task-1",
		Status: "executing", PID: &pid,
		Cwd: "/tmp/wt-1", HookToken: "tok-1",
		StartedAt: time.Now(),
	}
	if err := repo.Insert(context.Background(), in); err != nil {
		t.Fatalf("Insert: %v", err)
	}
	got, err := repo.GetByID(context.Background(), "sid-1")
	if err != nil {
		t.Fatalf("GetByID: %v", err)
	}
	if got.TaskID != "task-1" || got.Cwd != "/tmp/wt-1" || got.HookToken != "tok-1" {
		t.Errorf("mismatch: %+v", got)
	}
}

func TestSessionsRepo_GetByID_NotFound(t *testing.T) {
	db := newTestDB(t)
	repo := NewSessionsRepo(db)
	_, err := repo.GetByID(context.Background(), "missing")
	if !errors.Is(err, ErrSessionNotFound) {
		t.Errorf("want ErrSessionNotFound, got %v", err)
	}
}

func TestSessionsRepo_UpdateStatus_ReturnsPrev(t *testing.T) {
	db := newTestDB(t)
	seedTask(t, db, "task-1", "proj-1")
	repo := NewSessionsRepo(db)
	pid := 1
	_ = repo.Insert(context.Background(), Session{
		ID: "sid-1", TaskID: "task-1", Status: "executing",
		PID: &pid, Cwd: "/tmp", HookToken: "tok", StartedAt: time.Now(),
	})
	prev, err := repo.UpdateStatus(context.Background(), "sid-1", "idle")
	if err != nil {
		t.Fatalf("UpdateStatus: %v", err)
	}
	if prev != "executing" {
		t.Errorf("prev: got %q, want executing", prev)
	}
	got, _ := repo.GetByID(context.Background(), "sid-1")
	if got.Status != "idle" {
		t.Errorf("status not persisted: %s", got.Status)
	}
}

func TestSessionsRepo_BumpLastHookAt(t *testing.T) {
	db := newTestDB(t)
	seedTask(t, db, "task-1", "proj-1")
	repo := NewSessionsRepo(db)
	pid := 1
	_ = repo.Insert(context.Background(), Session{
		ID: "sid-1", TaskID: "task-1", Status: "executing",
		PID: &pid, Cwd: "/tmp", HookToken: "tok", StartedAt: time.Now(),
	})
	before := time.Now().Add(-time.Hour)
	_ = repo.BumpLastHookAt(context.Background(), "sid-1", before)
	got, _ := repo.GetByID(context.Background(), "sid-1")
	if got.LastHookAt == nil || got.LastHookAt.Before(before.Add(-time.Second)) {
		t.Errorf("LastHookAt not bumped: %+v", got.LastHookAt)
	}
}

func TestSessionsRepo_MarkEnded(t *testing.T) {
	db := newTestDB(t)
	seedTask(t, db, "task-1", "proj-1")
	repo := NewSessionsRepo(db)
	pid := 1
	_ = repo.Insert(context.Background(), Session{
		ID: "sid-1", TaskID: "task-1", Status: "executing",
		PID: &pid, Cwd: "/tmp", HookToken: "tok", StartedAt: time.Now(),
	})
	if err := repo.MarkEnded(context.Background(), "sid-1", "done"); err != nil {
		t.Fatalf("MarkEnded: %v", err)
	}
	got, _ := repo.GetByID(context.Background(), "sid-1")
	if got.Status != "done" || got.EndedAt == nil {
		t.Errorf("not ended: %+v", got)
	}
}

func TestSessionsRepo_ListActiveByTask(t *testing.T) {
	db := newTestDB(t)
	seedTask(t, db, "task-1", "proj-1")
	seedTaskOnly(t, db, "task-2", "proj-1")
	repo := NewSessionsRepo(db)
	pid := 1
	_ = repo.Insert(context.Background(), Session{
		ID: "sid-a", TaskID: "task-1", Status: "executing",
		PID: &pid, Cwd: "/tmp", HookToken: "ta", StartedAt: time.Now(),
	})
	_ = repo.Insert(context.Background(), Session{
		ID: "sid-b", TaskID: "task-1", Status: "executing",
		PID: &pid, Cwd: "/tmp", HookToken: "tb", StartedAt: time.Now(),
	})
	_ = repo.MarkEnded(context.Background(), "sid-b", "done")
	_ = repo.Insert(context.Background(), Session{
		ID: "sid-c", TaskID: "task-2", Status: "executing",
		PID: &pid, Cwd: "/tmp", HookToken: "tc", StartedAt: time.Now(),
	})

	got, err := repo.ListActiveByTask(context.Background(), "task-1")
	if err != nil {
		t.Fatalf("ListActiveByTask: %v", err)
	}
	if len(got) != 1 || got[0].ID != "sid-a" {
		t.Errorf("want only sid-a, got %+v", got)
	}
}

func TestSessionsRepo_ListByTask_IncludesEnded(t *testing.T) {
	db := newTestDB(t)
	seedTask(t, db, "task-1", "proj-1")
	repo := NewSessionsRepo(db)
	pid := 1
	_ = repo.Insert(context.Background(), Session{
		ID: "sid-a", TaskID: "task-1", Status: "executing",
		PID: &pid, Cwd: "/tmp", HookToken: "ta", StartedAt: time.Now(),
	})
	_ = repo.MarkEnded(context.Background(), "sid-a", "done")
	got, _ := repo.ListByTask(context.Background(), "task-1")
	if len(got) != 1 {
		t.Errorf("want 1, got %d", len(got))
	}
}

func TestSessionsRepo_HookAdapter_PassThrough(t *testing.T) {
	db := newTestDB(t)
	seedTask(t, db, "task-1", "proj-1")
	repo := NewSessionsRepo(db)
	pid := 1
	_ = repo.Insert(context.Background(), Session{
		ID: "sid-1", TaskID: "task-1", Status: "executing",
		PID: &pid, Cwd: "/tmp", HookToken: "tok", StartedAt: time.Now(),
	})
	adapter := NewSessionsHookAdapter(repo)
	prev, err := adapter.UpdateStatus("sid-1", "idle")
	if err != nil || prev != "executing" {
		t.Errorf("adapter UpdateStatus: prev=%q err=%v", prev, err)
	}
	if err := adapter.BumpLastHookAt("sid-1"); err != nil {
		t.Errorf("adapter BumpLastHookAt: %v", err)
	}
}
