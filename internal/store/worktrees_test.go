package store

import (
	"context"
	"database/sql"
	"errors"
	"testing"
	"time"
)

func newTestDBWithProjectAndRepo(t *testing.T) (db *sql.DB, projectID, repoID string) {
	t.Helper()
	db = newTestDB(t)
	seedProject(t, db, "p1")
	if _, err := db.Exec(
		`INSERT INTO repositories(id, project_id, name, sub_path, created_at) VALUES (?, ?, ?, ?, ?)`,
		"r1", "p1", "monorepo", ".", time.Now(),
	); err != nil {
		t.Fatalf("seed repo: %v", err)
	}
	return db, "p1", "r1"
}

func TestWorktreesRepo_ListByProject_Empty(t *testing.T) {
	db, projectID, _ := newTestDBWithProjectAndRepo(t)
	repo := NewWorktreesRepo(db)
	got, err := repo.ListByProject(context.Background(), projectID)
	if err != nil {
		t.Fatalf("ListByProject: %v", err)
	}
	if len(got) != 0 {
		t.Errorf("want empty, got %+v", got)
	}
}

func TestWorktreesRepo_Upsert_AndListByProject(t *testing.T) {
	db, projectID, repoID := newTestDBWithProjectAndRepo(t)
	repo := NewWorktreesRepo(db)
	branch := "feature/x"
	id1, err := repo.Upsert(context.Background(), WorktreeUpsert{
		RepositoryID: repoID, Path: "/tmp/wt-1", Branch: &branch,
	})
	if err != nil {
		t.Fatalf("Upsert: %v", err)
	}
	if id1 == "" {
		t.Error("expected non-empty id")
	}

	got, err := repo.ListByProject(context.Background(), projectID)
	if err != nil {
		t.Fatalf("ListByProject: %v", err)
	}
	if len(got) != 1 {
		t.Fatalf("want 1, got %d", len(got))
	}
	if got[0].Path != "/tmp/wt-1" || got[0].Branch == nil || *got[0].Branch != "feature/x" {
		t.Errorf("row mismatch: %+v", got[0])
	}
	if got[0].TaskID != nil {
		t.Errorf("expected orphan, got task_id=%v", got[0].TaskID)
	}

	newBranch := "feature/y"
	id2, err := repo.Upsert(context.Background(), WorktreeUpsert{
		RepositoryID: repoID, Path: "/tmp/wt-1", Branch: &newBranch,
	})
	if err != nil {
		t.Fatalf("Upsert (2nd): %v", err)
	}
	if id2 != id1 {
		t.Errorf("re-upsert should keep id; got %s, want %s", id2, id1)
	}
	got2, _ := repo.ListByProject(context.Background(), projectID)
	if len(got2) != 1 {
		t.Fatalf("want 1 after re-upsert, got %d", len(got2))
	}
	if got2[0].Branch == nil || *got2[0].Branch != "feature/y" {
		t.Errorf("branch not updated: %+v", got2[0])
	}
}

func TestWorktreesRepo_ListByTask(t *testing.T) {
	db, _, repoID := newTestDBWithProjectAndRepo(t)
	tasksRepo := NewTasksRepo(db)
	tk, _ := tasksRepo.Create(context.Background(), CreateTaskInput{
		ProjectID: "p1", Title: "t",
	})

	repo := NewWorktreesRepo(db)
	_, _ = db.Exec(
		`INSERT INTO worktrees(id, repository_id, task_id, path, branch) VALUES (?, ?, ?, ?, ?)`,
		"wt-1", repoID, tk.ID, "/tmp/wt-x", "feature/y",
	)

	got, err := repo.ListByTask(context.Background(), tk.ID)
	if err != nil {
		t.Fatalf("ListByTask: %v", err)
	}
	if len(got) != 1 || got[0].Path != "/tmp/wt-x" {
		t.Errorf("ListByTask mismatch: %+v", got)
	}
}

func TestWorktreesRepo_OrphanRow(t *testing.T) {
	db, _, repoID := newTestDBWithProjectAndRepo(t)
	tasksRepo := NewTasksRepo(db)
	tk, _ := tasksRepo.Create(context.Background(), CreateTaskInput{ProjectID: "p1", Title: "t"})

	repo := NewWorktreesRepo(db)
	_, _ = db.Exec(
		`INSERT INTO worktrees(id, repository_id, task_id, path) VALUES (?, ?, ?, ?)`,
		"wt-1", repoID, tk.ID, "/tmp/wt-x",
	)

	if err := repo.OrphanRow(context.Background(), "wt-1"); err != nil {
		t.Fatalf("OrphanRow: %v", err)
	}
	got, _ := repo.GetByID(context.Background(), "wt-1")
	if got.TaskID != nil {
		t.Errorf("expected orphan, got task_id=%v", *got.TaskID)
	}
}

func TestWorktreesRepo_Delete(t *testing.T) {
	db, _, repoID := newTestDBWithProjectAndRepo(t)
	repo := NewWorktreesRepo(db)
	branch := "x"
	id, _ := repo.Upsert(context.Background(), WorktreeUpsert{
		RepositoryID: repoID, Path: "/tmp/wt-1", Branch: &branch,
	})
	if err := repo.Delete(context.Background(), id); err != nil {
		t.Fatalf("Delete: %v", err)
	}
	_, err := repo.GetByID(context.Background(), id)
	if !errors.Is(err, ErrWorktreeNotFound) {
		t.Errorf("want ErrWorktreeNotFound, got %v", err)
	}
}
