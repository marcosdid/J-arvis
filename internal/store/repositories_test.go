package store

import (
	"context"
	"testing"
)

func TestRepositoriesRepo_CreateBulk_AndListByProject_SortedBySubPath(t *testing.T) {
	db := newTestDB(t)
	seedProject(t, db, "p1")

	repos := NewRepositoriesRepo(db)
	created, err := repos.CreateBulk(context.Background(), "p1", []RepoSpecInput{
		{Name: "zeta", SubPath: "zeta"},
		{Name: "alpha", SubPath: "alpha"},
		{Name: "monorepo", SubPath: "."},
	})
	if err != nil {
		t.Fatalf("CreateBulk: %v", err)
	}
	if len(created) != 3 {
		t.Fatalf("want 3 created, got %d", len(created))
	}

	got, err := repos.ListByProject(context.Background(), "p1")
	if err != nil {
		t.Fatalf("ListByProject: %v", err)
	}
	wantOrder := []string{".", "alpha", "zeta"}
	if len(got) != 3 {
		t.Fatalf("want 3 rows, got %d", len(got))
	}
	for i, w := range wantOrder {
		if got[i].SubPath != w {
			t.Errorf("row[%d].SubPath: got %q, want %q", i, got[i].SubPath, w)
		}
	}
}

func TestRepositoriesRepo_ListByProject_Empty(t *testing.T) {
	db := newTestDB(t)
	seedProject(t, db, "p1")
	repos := NewRepositoriesRepo(db)
	got, err := repos.ListByProject(context.Background(), "p1")
	if err != nil {
		t.Fatalf("ListByProject: %v", err)
	}
	if len(got) != 0 {
		t.Errorf("want empty, got %+v", got)
	}
}

func TestRepositoriesRepo_CreateBulk_UniqueViolation(t *testing.T) {
	db := newTestDB(t)
	seedProject(t, db, "p1")
	repos := NewRepositoriesRepo(db)
	if _, err := repos.CreateBulk(context.Background(), "p1", []RepoSpecInput{
		{Name: "a", SubPath: "a"},
		{Name: "a-dup", SubPath: "a"},
	}); err == nil {
		t.Error("expected unique constraint violation on (project_id, sub_path)")
	}
}
