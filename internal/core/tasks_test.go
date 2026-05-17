package core

import (
	"context"
	"errors"
	"reflect"
	"sync"
	"testing"
	"time"

	"github.com/marcosdid/jarvis/internal/catalog"
	"github.com/marcosdid/jarvis/internal/events"
	"github.com/marcosdid/jarvis/internal/store"
)

// fakeTasksRepo is an in-memory TasksRepoInterface for service-level tests.
// It does not enforce transition validity (the service does that); state writes
// go straight through.
type fakeTasksRepo struct {
	items map[string]*store.Task
}

func newFakeTasksRepo() *fakeTasksRepo {
	return &fakeTasksRepo{items: map[string]*store.Task{}}
}

func (f *fakeTasksRepo) List(_ context.Context, filt store.TaskFilters) ([]store.Task, error) {
	out := make([]store.Task, 0, len(f.items))
	for _, t := range f.items {
		if len(filt.ProjectIDs) > 0 {
			match := false
			for _, p := range filt.ProjectIDs {
				if t.ProjectID == p {
					match = true
					break
				}
			}
			if !match {
				continue
			}
		}
		out = append(out, *t)
	}
	return out, nil
}

func (f *fakeTasksRepo) Get(_ context.Context, id string) (*store.Task, error) {
	t, ok := f.items[id]
	if !ok {
		return nil, store.ErrTaskNotFound
	}
	return t, nil
}

func (f *fakeTasksRepo) Create(_ context.Context, in store.CreateTaskInput) (*store.Task, error) {
	t := &store.Task{
		ID: "tsk-" + in.Title, ProjectID: in.ProjectID, Title: in.Title,
		Description: in.Description, State: in.State, Branch: in.Branch,
		Template: in.Template, PermissionProfile: in.PermissionProfile,
		CreatedAt: time.Now(), UpdatedAt: time.Now(),
	}
	f.items[t.ID] = t
	return t, nil
}

func (f *fakeTasksRepo) UpdateState(_ context.Context, id, state string) (*store.Task, error) {
	t, ok := f.items[id]
	if !ok {
		return nil, store.ErrTaskNotFound
	}
	t.State = state
	t.UpdatedAt = time.Now()
	return t, nil
}

func (f *fakeTasksRepo) UpdateFields(_ context.Context, id string, title *string, description *string, branch *string) (*store.Task, error) {
	t, ok := f.items[id]
	if !ok {
		return nil, store.ErrTaskNotFound
	}
	if title != nil {
		t.Title = *title
	}
	if description != nil {
		t.Description = *description
	}
	if branch != nil {
		t.Branch = branch
	}
	t.UpdatedAt = time.Now()
	return t, nil
}

func (f *fakeTasksRepo) Discard(_ context.Context, id string) error {
	t, ok := f.items[id]
	if !ok {
		return store.ErrTaskNotFound
	}
	t.State = "discarded"
	return nil
}

func TestTransition_TerminalRunsAllCleanupsInOrder_BootstrapFirst(t *testing.T) {
	var order []string
	var mu sync.Mutex
	rec := func(name string) func(_ context.Context, taskID string) error {
		return func(_ context.Context, taskID string) error {
			mu.Lock()
			defer mu.Unlock()
			order = append(order, name+":"+taskID)
			return nil
		}
	}

	repo := newFakeTasksRepo()
	// Seed at "review" so the Patch to "done" is a valid transition.
	created, err := repo.Create(context.Background(), store.CreateTaskInput{
		ProjectID: "p1", Title: "t", Description: "", State: "review",
	})
	if err != nil {
		t.Fatalf("Create: %v", err)
	}

	svc := NewTasksService(repo, &catalog.Catalog{}, &events.FakeEmitter{},
		rec("worktree"),
		rec("session"),
		rec("runs"),
		rec("bootstrap"),
	)

	state := "done"
	if _, err := svc.Patch(context.Background(), created.ID, PatchTaskInput{State: &state}); err != nil {
		t.Fatalf("Patch: %v", err)
	}

	want := []string{
		"bootstrap:" + created.ID,
		"session:" + created.ID,
		"runs:" + created.ID,
		"worktree:" + created.ID,
	}
	if !reflect.DeepEqual(order, want) {
		t.Errorf("order=%v, want %v", order, want)
	}
}

func TestTransition_BootstrapErrorDoesNotBlockOthers(t *testing.T) {
	var calls int
	var mu sync.Mutex
	count := func(_ context.Context, _ string) error {
		mu.Lock()
		defer mu.Unlock()
		calls++
		return nil
	}
	failing := func(_ context.Context, _ string) error {
		mu.Lock()
		defer mu.Unlock()
		calls++
		return errors.New("bootstrap fail")
	}

	repo := newFakeTasksRepo()
	created, err := repo.Create(context.Background(), store.CreateTaskInput{
		ProjectID: "p1", Title: "t", Description: "", State: "review",
	})
	if err != nil {
		t.Fatalf("Create: %v", err)
	}

	svc := NewTasksService(repo, &catalog.Catalog{}, &events.FakeEmitter{},
		count, count, count, failing,
	)

	state := "done"
	if _, err := svc.Patch(context.Background(), created.ID, PatchTaskInput{State: &state}); err != nil {
		t.Fatalf("Patch: %v", err)
	}
	if calls != 4 {
		t.Errorf("calls=%d, want 4 (bootstrap failure must not block others)", calls)
	}
}
