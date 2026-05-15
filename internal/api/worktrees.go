package api

import (
	"context"

	"github.com/marcosdid/jarvis/internal/store"
)

type WorktreesService interface {
	SyncProjectWorktrees(ctx context.Context, projectID string) ([]store.Worktree, error)
	DeleteOrphan(ctx context.Context, id string) error
	CleanupForTask(ctx context.Context, taskID string) error
}

// WorktreeRead is the JS-facing projection.
type WorktreeRead struct {
	ID             string  `json:"id"`
	RepositoryID   string  `json:"repository_id"`
	RepositoryName string  `json:"repository_name"`
	TaskID         *string `json:"task_id"`
	Path           string  `json:"path"`
	Branch         *string `json:"branch"`
	IsOrphan       bool    `json:"is_orphan"`
}

type WorktreesAPI struct {
	svc WorktreesService
}

func NewWorktreesAPI(svc WorktreesService) *WorktreesAPI {
	return &WorktreesAPI{svc: svc}
}

func (a *WorktreesAPI) ListByProject(projectID string) ([]WorktreeRead, error) {
	wts, err := a.svc.SyncProjectWorktrees(context.Background(), projectID)
	if err != nil {
		return nil, err
	}
	out := make([]WorktreeRead, len(wts))
	for i, w := range wts {
		out[i] = WorktreeRead{
			ID: w.ID, RepositoryID: w.RepositoryID, RepositoryName: w.RepositoryName,
			TaskID: w.TaskID, Path: w.Path, Branch: w.Branch,
			IsOrphan: w.TaskID == nil,
		}
	}
	return out, nil
}

func (a *WorktreesAPI) Delete(id string) error {
	return a.svc.DeleteOrphan(context.Background(), id)
}
