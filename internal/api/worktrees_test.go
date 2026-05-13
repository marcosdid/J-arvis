package api

import (
	"context"
	"errors"
	"testing"

	"github.com/marcosdid/jarvis/internal/core"
	"github.com/marcosdid/jarvis/internal/store"
)

type fakeWorktreesService struct {
	syncByProject map[string][]store.Worktree
	deleteErrs    map[string]error
}

func (f *fakeWorktreesService) SyncProjectWorktrees(_ context.Context, projectID string) ([]store.Worktree, error) {
	if v, ok := f.syncByProject[projectID]; ok {
		return v, nil
	}
	return nil, store.ErrProjectNotFound
}

func (f *fakeWorktreesService) DeleteOrphan(_ context.Context, id string) error {
	if err, ok := f.deleteErrs[id]; ok {
		return err
	}
	return nil
}

func (f *fakeWorktreesService) CleanupForTask(_ context.Context, _ string) error { return nil }

func TestWorktreesAPI_ListByProject(t *testing.T) {
	svc := &fakeWorktreesService{
		syncByProject: map[string][]store.Worktree{
			"p1": {{ID: "w1", Path: "/x", RepositoryID: "r1", RepositoryName: "monorepo"}},
		},
	}
	api := NewWorktreesAPI(svc)
	got, err := api.ListByProject("p1")
	if err != nil {
		t.Fatalf("ListByProject: %v", err)
	}
	if len(got) != 1 || got[0].ID != "w1" || got[0].RepositoryName != "monorepo" {
		t.Errorf("mismatch: %+v", got)
	}
	if got[0].IsOrphan != true {
		t.Errorf("IsOrphan should be true (TaskID=nil): %+v", got[0])
	}
}

func TestWorktreesAPI_Delete_PropagatesNotOrphan(t *testing.T) {
	svc := &fakeWorktreesService{
		deleteErrs: map[string]error{"w1": core.WorktreeNotOrphanError},
	}
	api := NewWorktreesAPI(svc)
	err := api.Delete("w1")
	if !errors.Is(err, core.WorktreeNotOrphanError) {
		t.Errorf("want WorktreeNotOrphanError, got %v", err)
	}
}
