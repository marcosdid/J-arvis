package store

import (
	"context"
	"errors"
	"testing"
)

func TestProjectsRepo_List_Empty(t *testing.T) {
	db := newTestDB(t)
	repo := NewProjectsRepo(db)
	got, err := repo.List(context.Background())
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	if len(got) != 0 {
		t.Errorf("expected 0 projects, got %d", len(got))
	}
}

func TestProjectsRepo_CreateAndGet(t *testing.T) {
	db := newTestDB(t)
	repo := NewProjectsRepo(db)
	created, err := repo.Create(context.Background(), CreateProjectInput{
		Name: "demo", Path: "/tmp/demo",
	})
	if err != nil {
		t.Fatalf("Create: %v", err)
	}
	if created.ID == "" {
		t.Error("expected ID populated")
	}
	got, err := repo.Get(context.Background(), created.ID)
	if err != nil {
		t.Fatalf("Get: %v", err)
	}
	if got.Name != "demo" {
		t.Errorf("Name: got %q", got.Name)
	}
	if got.Repositories == nil {
		t.Error("Repositories should be non-nil")
	}
}

func TestProjectsRepo_Get_NotFound(t *testing.T) {
	db := newTestDB(t)
	repo := NewProjectsRepo(db)
	_, err := repo.Get(context.Background(), "nope")
	if !errors.Is(err, ErrProjectNotFound) {
		t.Errorf("expected ErrProjectNotFound, got %v", err)
	}
}

func TestProjectsRepo_Delete(t *testing.T) {
	db := newTestDB(t)
	repo := NewProjectsRepo(db)
	created, _ := repo.Create(context.Background(), CreateProjectInput{
		Name: "x", Path: "/tmp/x",
	})
	if err := repo.Delete(context.Background(), created.ID); err != nil {
		t.Fatalf("Delete: %v", err)
	}
	if _, err := repo.Get(context.Background(), created.ID); !errors.Is(err, ErrProjectNotFound) {
		t.Errorf("expected NotFound after delete, got %v", err)
	}
}
