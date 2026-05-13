package api

import (
	"context"
	"errors"
	"log"

	"github.com/marcosdid/jarvis/internal/core"
	"github.com/marcosdid/jarvis/internal/events"
	"github.com/marcosdid/jarvis/internal/store"
)

type TasksRepo interface {
	List(context.Context, store.TaskFilters) ([]store.Task, error)
	Get(context.Context, string) (*store.Task, error)
	Create(context.Context, store.CreateTaskInput) (*store.Task, error)
	UpdateState(context.Context, string, string) (*store.Task, error)
	Discard(context.Context, string) error
}

type WorktreeCleanupFn func(ctx context.Context, taskID string) error
type SessionCleanupFn func(ctx context.Context, taskID string) error

type TasksAPI struct {
	repo            TasksRepo
	bus             events.Emitter
	worktreeCleanup WorktreeCleanupFn
	sessionCleanup  SessionCleanupFn
}

func NewTasksAPI(
	repo TasksRepo, bus events.Emitter,
	worktreeCleanup WorktreeCleanupFn,
	sessionCleanup SessionCleanupFn,
) *TasksAPI {
	return &TasksAPI{
		repo:            repo,
		bus:             bus,
		worktreeCleanup: worktreeCleanup,
		sessionCleanup:  sessionCleanup,
	}
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

var ErrInvalidTransition = errors.New("invalid state transition")

// All methods use context.Background() since Wails v2 does not propagate a
// request-scoped context to bound methods. The desktop app has no notion of
// request cancellation; the DB layer still receives a real context.

func (a *TasksAPI) List(projectIDs []string) ([]store.Task, error) {
	return a.repo.List(context.Background(), store.TaskFilters{ProjectIDs: projectIDs})
}

func (a *TasksAPI) Get(id string) (*store.Task, error) {
	return a.repo.Get(context.Background(), id)
}

func (a *TasksAPI) Create(in CreateTaskInput) (*store.Task, error) {
	created, err := a.repo.Create(context.Background(), store.CreateTaskInput{
		ProjectID:   in.ProjectID,
		Title:       in.Title,
		Description: in.Description,
		State:       "idea",
		Branch:      in.Branch,
		Template:    in.Template,
	})
	if err != nil {
		return nil, err
	}
	a.bus.Emit("task.created", created)
	return created, nil
}

func (a *TasksAPI) Patch(id string, in PatchTaskInput) (*store.Task, error) {
	ctx := context.Background()
	current, err := a.repo.Get(ctx, id)
	if err != nil {
		return nil, err
	}
	if in.State != nil && *in.State != current.State {
		if !core.IsValidTransition(current.State, *in.State) {
			return nil, ErrInvalidTransition
		}
		updated, err := a.repo.UpdateState(ctx, id, *in.State)
		if err != nil {
			return nil, err
		}
		a.bus.Emit("task.updated", updated)
		if core.IsTerminal(*in.State) {
			// Sessions cleanup runs BEFORE worktree cleanup: subprocess writing
			// to a worktree that's about to disappear would become a zombie
			// writing to a non-existent path. Stop first ensures clean shutdown.
			a.runSessionCleanup(ctx, id)
			a.runWorktreeCleanup(ctx, id)
		}
		return updated, nil
	}
	return current, nil
}

func (a *TasksAPI) Discard(id string) error {
	ctx := context.Background()
	if err := a.repo.Discard(ctx, id); err != nil {
		return err
	}
	// Emit full task payload so JS subscribers see consistent shape across
	// update vs discard paths (both deliver project_id/title/state).
	if full, err := a.repo.Get(ctx, id); err == nil {
		a.bus.Emit("task.discarded", full)
	} else {
		a.bus.Emit("task.discarded", map[string]string{"id": id})
	}
	a.runSessionCleanup(ctx, id)
	a.runWorktreeCleanup(ctx, id)
	return nil
}

func (a *TasksAPI) runWorktreeCleanup(ctx context.Context, taskID string) {
	if a.worktreeCleanup == nil {
		return
	}
	if err := a.worktreeCleanup(ctx, taskID); err != nil {
		log.Printf("worktree cleanup for task %s: %v", taskID, err)
	}
}

func (a *TasksAPI) runSessionCleanup(ctx context.Context, taskID string) {
	if a.sessionCleanup == nil {
		return
	}
	if err := a.sessionCleanup(ctx, taskID); err != nil {
		log.Printf("session cleanup for task %s: %v", taskID, err)
	}
}
