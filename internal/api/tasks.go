package api

import (
	"context"

	"github.com/marcosdid/jarvis/internal/core"
	"github.com/marcosdid/jarvis/internal/store"
)

// ErrInvalidTransition is re-exported for callers of the Wails-bound layer
// (existing JS code refs api.ErrInvalidTransition through the binding).
// Backed by core.ErrInvalidTransition.
var ErrInvalidTransition = core.ErrInvalidTransition

type TasksAPI struct {
	svc *core.TasksService
}

func NewTasksAPI(svc *core.TasksService) *TasksAPI {
	return &TasksAPI{svc: svc}
}

type CreateTaskInput struct {
	ProjectID   string  `json:"project_id"`
	Title       string  `json:"title"`
	Description string  `json:"description"`
	Branch      *string `json:"branch,omitempty"`
	Template    *string `json:"template,omitempty"`
}

type PatchTaskInput struct {
	Title       *string `json:"title,omitempty"`
	Description *string `json:"description,omitempty"`
	State       *string `json:"state,omitempty"`
	Branch      *string `json:"branch,omitempty"`
}

// All methods use context.Background() since Wails v2 does not propagate a
// request-scoped context to bound methods. The desktop app has no notion of
// request cancellation; the DB layer still receives a real context via the
// service.

func (a *TasksAPI) List(projectIDs []string) ([]store.Task, error) {
	return a.svc.List(context.Background(), projectIDs)
}

func (a *TasksAPI) Get(id string) (*store.Task, error) {
	return a.svc.Get(context.Background(), id)
}

func (a *TasksAPI) Create(in CreateTaskInput) (*store.Task, error) {
	return a.svc.Create(context.Background(), core.CreateTaskInput{
		ProjectID:   in.ProjectID,
		Title:       in.Title,
		Description: in.Description,
		Branch:      in.Branch,
		Template:    in.Template,
	})
}

func (a *TasksAPI) Patch(id string, in PatchTaskInput) (*store.Task, error) {
	return a.svc.Patch(context.Background(), id, core.PatchTaskInput{
		Title:       in.Title,
		Description: in.Description,
		State:       in.State,
		Branch:      in.Branch,
	})
}

func (a *TasksAPI) Discard(id string) error {
	return a.svc.Discard(context.Background(), id)
}

// Compile-time guard: *store.TasksRepo must continue to satisfy the service's
// interface contract.
var _ core.TasksRepoInterface = (*store.TasksRepo)(nil)
