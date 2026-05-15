package core

import (
	"context"
	"errors"
	"log"

	"github.com/marcosdid/jarvis/internal/catalog"
	"github.com/marcosdid/jarvis/internal/events"
	"github.com/marcosdid/jarvis/internal/store"
)

var ErrInvalidTransition = errors.New("invalid state transition")

type TasksRepoInterface interface {
	List(context.Context, store.TaskFilters) ([]store.Task, error)
	Get(context.Context, string) (*store.Task, error)
	Create(context.Context, store.CreateTaskInput) (*store.Task, error)
	UpdateState(context.Context, string, string) (*store.Task, error)
	Discard(context.Context, string) error
}

type TasksWorktreeCleanupFn func(ctx context.Context, taskID string) error
type TasksSessionCleanupFn func(ctx context.Context, taskID string) error

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

type TasksService struct {
	repo            TasksRepoInterface
	catalog         *catalog.Catalog
	bus             events.Emitter
	worktreeCleanup TasksWorktreeCleanupFn
	sessionCleanup  TasksSessionCleanupFn
}

func NewTasksService(
	repo TasksRepoInterface, cat *catalog.Catalog, bus events.Emitter,
	worktreeCleanup TasksWorktreeCleanupFn,
	sessionCleanup TasksSessionCleanupFn,
) *TasksService {
	return &TasksService{
		repo:            repo,
		catalog:         cat,
		bus:             bus,
		worktreeCleanup: worktreeCleanup,
		sessionCleanup:  sessionCleanup,
	}
}

func (s *TasksService) List(ctx context.Context, projectIDs []string) ([]store.Task, error) {
	return s.repo.List(ctx, store.TaskFilters{ProjectIDs: projectIDs})
}

func (s *TasksService) Get(ctx context.Context, id string) (*store.Task, error) {
	return s.repo.Get(ctx, id)
}

func (s *TasksService) Create(ctx context.Context, in CreateTaskInput) (*store.Task, error) {
	tmpl := ""
	if in.Template != nil {
		tmpl = *in.Template
	}
	resolved, err := s.catalog.Resolve(tmpl)
	if err != nil {
		return nil, err // wraps catalog.ErrTemplateUnknown
	}
	profile := resolved.ProfileName
	created, err := s.repo.Create(ctx, store.CreateTaskInput{
		ProjectID:         in.ProjectID,
		Title:             in.Title,
		Description:       in.Description,
		State:             "idea",
		Branch:            in.Branch,
		Template:          in.Template,
		PermissionProfile: &profile,
	})
	if err != nil {
		return nil, err
	}
	s.bus.Emit("task.created", created)
	return created, nil
}

func (s *TasksService) Patch(ctx context.Context, id string, in PatchTaskInput) (*store.Task, error) {
	current, err := s.repo.Get(ctx, id)
	if err != nil {
		return nil, err
	}
	if in.State == nil || *in.State == current.State {
		return current, nil
	}
	if !IsValidTransition(current.State, *in.State) {
		return nil, ErrInvalidTransition
	}
	updated, err := s.repo.UpdateState(ctx, id, *in.State)
	if err != nil {
		return nil, err
	}
	s.bus.Emit("task.updated", updated)
	if IsTerminal(*in.State) {
		// Sessions cleanup runs BEFORE worktree cleanup: subprocess writing
		// to a worktree that's about to disappear would become a zombie
		// writing to a non-existent path. Stop first ensures clean shutdown.
		s.runSessionCleanup(ctx, id)
		s.runWorktreeCleanup(ctx, id)
	}
	return updated, nil
}

func (s *TasksService) Discard(ctx context.Context, id string) error {
	if err := s.repo.Discard(ctx, id); err != nil {
		return err
	}
	// Emit full task payload so JS subscribers see consistent shape across
	// update vs discard paths (both deliver project_id/title/state).
	if full, err := s.repo.Get(ctx, id); err == nil {
		s.bus.Emit("task.discarded", full)
	} else {
		s.bus.Emit("task.discarded", map[string]string{"id": id})
	}
	s.runSessionCleanup(ctx, id)
	s.runWorktreeCleanup(ctx, id)
	return nil
}

func (s *TasksService) runWorktreeCleanup(ctx context.Context, taskID string) {
	if s.worktreeCleanup == nil {
		return
	}
	if err := s.worktreeCleanup(ctx, taskID); err != nil {
		log.Printf("worktree cleanup for task %s: %v", taskID, err)
	}
}

func (s *TasksService) runSessionCleanup(ctx context.Context, taskID string) {
	if s.sessionCleanup == nil {
		return
	}
	if err := s.sessionCleanup(ctx, taskID); err != nil {
		log.Printf("session cleanup for task %s: %v", taskID, err)
	}
}
