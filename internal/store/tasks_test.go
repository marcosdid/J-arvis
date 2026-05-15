package store

import (
	"context"
	"database/sql"
	"errors"
	"path/filepath"
	"testing"
	"time"
)

func newTestDB(t *testing.T) *sql.DB {
	t.Helper()
	tmpDir := t.TempDir()
	db, err := Open(context.Background(), filepath.Join(tmpDir, "test.db"))
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	if err := Migrate(context.Background(), db); err != nil {
		t.Fatalf("Migrate: %v", err)
	}
	t.Cleanup(func() { _ = db.Close() })
	return db
}

func seedProject(t *testing.T, db *sql.DB, id string) {
	t.Helper()
	_, err := db.Exec(`INSERT INTO projects(id, name, path, created_at) VALUES (?, ?, ?, ?)`,
		id, "demo-"+id, "/tmp/"+id, time.Now())
	if err != nil {
		t.Fatalf("seed project: %v", err)
	}
}

func TestTasksRepo_List_EmptyDB(t *testing.T) {
	db := newTestDB(t)
	repo := NewTasksRepo(db)
	tasks, err := repo.List(context.Background(), TaskFilters{})
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	if len(tasks) != 0 {
		t.Errorf("expected 0 tasks, got %d", len(tasks))
	}
}

func TestTasksRepo_CreateAndList(t *testing.T) {
	db := newTestDB(t)
	seedProject(t, db, "prj-1")
	repo := NewTasksRepo(db)

	created, err := repo.Create(context.Background(), CreateTaskInput{
		ProjectID: "prj-1", Title: "do the thing", Description: "details", State: "idea",
	})
	if err != nil {
		t.Fatalf("Create: %v", err)
	}
	if created.ID == "" {
		t.Error("expected ID populated")
	}
	if created.State != "idea" {
		t.Errorf("State: got %q, want idea", created.State)
	}

	list, err := repo.List(context.Background(), TaskFilters{})
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	if len(list) != 1 {
		t.Fatalf("expected 1 task, got %d", len(list))
	}
	if list[0].Title != "do the thing" {
		t.Errorf("Title: got %q", list[0].Title)
	}
}

func TestTasksRepo_Create_DefaultsStateToIdea(t *testing.T) {
	db := newTestDB(t)
	seedProject(t, db, "prj-1")
	repo := NewTasksRepo(db)

	got, err := repo.Create(context.Background(), CreateTaskInput{
		ProjectID: "prj-1", Title: "x",
	})
	if err != nil {
		t.Fatalf("Create: %v", err)
	}
	if got.State != "idea" {
		t.Errorf("default state: got %q, want idea", got.State)
	}
}

func TestTasksRepo_UpdateState(t *testing.T) {
	db := newTestDB(t)
	seedProject(t, db, "prj-1")
	repo := NewTasksRepo(db)

	created, _ := repo.Create(context.Background(), CreateTaskInput{
		ProjectID: "prj-1", Title: "x", State: "idea",
	})
	updated, err := repo.UpdateState(context.Background(), created.ID, "in_progress")
	if err != nil {
		t.Fatalf("UpdateState: %v", err)
	}
	if updated.State != "in_progress" {
		t.Errorf("State: got %q, want in_progress", updated.State)
	}
	if !updated.UpdatedAt.After(created.UpdatedAt) && !updated.UpdatedAt.Equal(created.UpdatedAt) {
		t.Error("UpdatedAt should be >= original")
	}
}

func TestTasksRepo_UpdateState_NotFound(t *testing.T) {
	db := newTestDB(t)
	repo := NewTasksRepo(db)
	_, err := repo.UpdateState(context.Background(), "nope", "done")
	if !errors.Is(err, ErrTaskNotFound) {
		t.Errorf("expected ErrTaskNotFound, got %v", err)
	}
}

func TestTasksRepo_Discard(t *testing.T) {
	db := newTestDB(t)
	seedProject(t, db, "prj-1")
	repo := NewTasksRepo(db)
	created, _ := repo.Create(context.Background(), CreateTaskInput{
		ProjectID: "prj-1", Title: "x", State: "idea",
	})
	if err := repo.Discard(context.Background(), created.ID); err != nil {
		t.Fatalf("Discard: %v", err)
	}
	got, err := repo.Get(context.Background(), created.ID)
	if err != nil {
		t.Fatalf("Get: %v", err)
	}
	if got.State != "discarded" {
		t.Errorf("State: got %q, want discarded", got.State)
	}
}

func TestTasksRepo_List_FilterByProject(t *testing.T) {
	db := newTestDB(t)
	seedProject(t, db, "prj-1")
	seedProject(t, db, "prj-2")
	repo := NewTasksRepo(db)
	_, _ = repo.Create(context.Background(), CreateTaskInput{ProjectID: "prj-1", Title: "a"})
	_, _ = repo.Create(context.Background(), CreateTaskInput{ProjectID: "prj-2", Title: "b"})

	got, err := repo.List(context.Background(), TaskFilters{ProjectIDs: []string{"prj-1"}})
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	if len(got) != 1 || got[0].ProjectID != "prj-1" {
		t.Errorf("expected single task from prj-1, got %+v", got)
	}
}

func TestTasksRepo_Get_NotFound(t *testing.T) {
	db := newTestDB(t)
	repo := NewTasksRepo(db)
	_, err := repo.Get(context.Background(), "nope")
	if !errors.Is(err, ErrTaskNotFound) {
		t.Errorf("expected ErrTaskNotFound, got %v", err)
	}
}
