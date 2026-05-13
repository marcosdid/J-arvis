package api

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/marcosdid/jarvis/internal/events"
	"github.com/marcosdid/jarvis/internal/store"
)

type fakeTasksRepo struct {
	items map[string]*store.Task
}

func newFakeRepo() *fakeTasksRepo {
	return &fakeTasksRepo{items: map[string]*store.Task{}}
}

func (f *fakeTasksRepo) List(_ context.Context, filt store.TaskFilters) ([]store.Task, error) {
	out := []store.Task{}
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
		Description: in.Description, State: in.State, Branch: in.Branch, Template: in.Template,
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

func (f *fakeTasksRepo) Discard(_ context.Context, id string) error {
	t, ok := f.items[id]
	if !ok {
		return store.ErrTaskNotFound
	}
	t.State = "discarded"
	return nil
}

func TestTasksAPI_Create_EmitsEvent(t *testing.T) {
	bus := &events.FakeEmitter{}
	api := NewTasksAPI(newFakeRepo(), bus, nil)
	got, err := api.Create(CreateTaskInput{ProjectID: "p", Title: "x"})
	if err != nil {
		t.Fatalf("Create: %v", err)
	}
	if got.State != "idea" {
		t.Errorf("State: got %q", got.State)
	}
	if len(bus.Calls) != 1 || bus.Calls[0].Name != "task.created" {
		t.Errorf("expected task.created emit, got %+v", bus.Calls)
	}
}

func TestTasksAPI_Patch_ValidTransitionEmits(t *testing.T) {
	bus := &events.FakeEmitter{}
	repo := newFakeRepo()
	api := NewTasksAPI(repo, bus, nil)
	created, _ := api.Create(CreateTaskInput{ProjectID: "p", Title: "x"})

	newState := "ready"
	updated, err := api.Patch(created.ID, PatchTaskInput{State: &newState})
	if err != nil {
		t.Fatalf("Patch: %v", err)
	}
	if updated.State != "ready" {
		t.Errorf("State: got %q", updated.State)
	}
	if len(bus.Calls) != 2 || bus.Calls[1].Name != "task.updated" {
		t.Errorf("expected task.updated emit, got %+v", bus.Calls)
	}
}

func TestTasksAPI_Patch_InvalidTransition(t *testing.T) {
	bus := &events.FakeEmitter{}
	repo := newFakeRepo()
	api := NewTasksAPI(repo, bus, nil)
	created, _ := api.Create(CreateTaskInput{ProjectID: "p", Title: "x"})

	bad := "done"
	_, err := api.Patch(created.ID, PatchTaskInput{State: &bad})
	if !errors.Is(err, ErrInvalidTransition) {
		t.Errorf("expected ErrInvalidTransition, got %v", err)
	}
}

func TestTasksAPI_Patch_SameState_NoEmit(t *testing.T) {
	bus := &events.FakeEmitter{}
	repo := newFakeRepo()
	api := NewTasksAPI(repo, bus, nil)
	created, _ := api.Create(CreateTaskInput{ProjectID: "p", Title: "x"})
	bus.Calls = nil

	same := created.State
	_, err := api.Patch(created.ID, PatchTaskInput{State: &same})
	if err != nil {
		t.Fatalf("Patch: %v", err)
	}
	if len(bus.Calls) != 0 {
		t.Errorf("expected no emit for same-state patch, got %+v", bus.Calls)
	}
}

func TestTasksAPI_Discard_EmitsEvent(t *testing.T) {
	bus := &events.FakeEmitter{}
	repo := newFakeRepo()
	api := NewTasksAPI(repo, bus, nil)
	created, _ := api.Create(CreateTaskInput{ProjectID: "p", Title: "x"})
	bus.Calls = nil

	if err := api.Discard(created.ID); err != nil {
		t.Fatalf("Discard: %v", err)
	}
	if len(bus.Calls) != 1 || bus.Calls[0].Name != "task.discarded" {
		t.Errorf("expected task.discarded emit, got %+v", bus.Calls)
	}
}

func TestTasksAPI_List_FilterByProject(t *testing.T) {
	repo := newFakeRepo()
	api := NewTasksAPI(repo, &events.FakeEmitter{}, nil)
	_, _ = api.Create(CreateTaskInput{ProjectID: "a", Title: "x"})
	_, _ = api.Create(CreateTaskInput{ProjectID: "b", Title: "y"})

	got, err := api.List([]string{"a"})
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	if len(got) != 1 || got[0].ProjectID != "a" {
		t.Errorf("expected 1 task from project a, got %+v", got)
	}
}

func TestTasksAPI_Patch_TerminalCallsCleanup(t *testing.T) {
	bus := &events.FakeEmitter{}
	repo := newFakeRepo()
	called := 0
	cleanup := func(_ context.Context, _ string) error {
		called++
		return nil
	}
	api := NewTasksAPI(repo, bus, cleanup)
	created, _ := api.Create(CreateTaskInput{ProjectID: "p", Title: "x"})
	bus.Calls = nil

	target := "done"
	repo.items[created.ID].State = "review"
	if _, err := api.Patch(created.ID, PatchTaskInput{State: &target}); err != nil {
		t.Fatalf("Patch: %v", err)
	}
	if called != 1 {
		t.Errorf("expected cleanup called once on terminal Patch, got %d", called)
	}
}

func TestTasksAPI_Patch_NonTerminalDoesNotCallCleanup(t *testing.T) {
	bus := &events.FakeEmitter{}
	repo := newFakeRepo()
	called := 0
	cleanup := func(_ context.Context, _ string) error { called++; return nil }
	api := NewTasksAPI(repo, bus, cleanup)
	created, _ := api.Create(CreateTaskInput{ProjectID: "p", Title: "x"})

	target := "ready"
	if _, err := api.Patch(created.ID, PatchTaskInput{State: &target}); err != nil {
		t.Fatalf("Patch: %v", err)
	}
	if called != 0 {
		t.Errorf("cleanup should NOT be called on non-terminal Patch; was %d", called)
	}
}

func TestTasksAPI_Discard_CallsCleanup(t *testing.T) {
	bus := &events.FakeEmitter{}
	repo := newFakeRepo()
	called := 0
	cleanup := func(_ context.Context, _ string) error { called++; return nil }
	api := NewTasksAPI(repo, bus, cleanup)
	created, _ := api.Create(CreateTaskInput{ProjectID: "p", Title: "x"})

	if err := api.Discard(created.ID); err != nil {
		t.Fatalf("Discard: %v", err)
	}
	if called != 1 {
		t.Errorf("expected cleanup called once on Discard, got %d", called)
	}
}

func TestTasksAPI_Cleanup_ErrorDoesNotPropagate(t *testing.T) {
	bus := &events.FakeEmitter{}
	repo := newFakeRepo()
	cleanup := func(_ context.Context, _ string) error {
		return errors.New("simulated cleanup failure")
	}
	api := NewTasksAPI(repo, bus, cleanup)
	created, _ := api.Create(CreateTaskInput{ProjectID: "p", Title: "x"})
	if err := api.Discard(created.ID); err != nil {
		t.Errorf("Discard should not propagate cleanup err, got %v", err)
	}
}

func TestTasksAPI_NilCleanup_DoesNotPanic(t *testing.T) {
	bus := &events.FakeEmitter{}
	repo := newFakeRepo()
	api := NewTasksAPI(repo, bus, nil)
	created, _ := api.Create(CreateTaskInput{ProjectID: "p", Title: "x"})
	if err := api.Discard(created.ID); err != nil {
		t.Errorf("Discard with nil cleanup should not error: %v", err)
	}
}
