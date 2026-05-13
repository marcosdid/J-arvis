package api

import (
	"context"
	"testing"
	"time"

	"github.com/marcosdid/jarvis/internal/events"
	"github.com/marcosdid/jarvis/internal/store"
)

type fakeProjectsRepo struct {
	items map[string]*store.Project
}

func newFakeProjectsRepo() *fakeProjectsRepo {
	return &fakeProjectsRepo{items: map[string]*store.Project{}}
}

func (f *fakeProjectsRepo) List(_ context.Context) ([]store.Project, error) {
	out := []store.Project{}
	for _, p := range f.items {
		out = append(out, *p)
	}
	return out, nil
}

func (f *fakeProjectsRepo) Get(_ context.Context, id string) (*store.Project, error) {
	p, ok := f.items[id]
	if !ok {
		return nil, store.ErrProjectNotFound
	}
	return p, nil
}

func (f *fakeProjectsRepo) Create(_ context.Context, in store.CreateProjectInput) (*store.Project, error) {
	p := &store.Project{
		ID: "prj-" + in.Name, Name: in.Name, Path: in.Path,
		CreatedAt: time.Now(), Repositories: []store.Repository{},
	}
	f.items[p.ID] = p
	return p, nil
}

func (f *fakeProjectsRepo) Delete(_ context.Context, id string) error {
	if _, ok := f.items[id]; !ok {
		return store.ErrProjectNotFound
	}
	delete(f.items, id)
	return nil
}

func TestProjectsAPI_Create_EmitsEvent(t *testing.T) {
	bus := &events.FakeEmitter{}
	api := NewProjectsAPI(newFakeProjectsRepo(), bus)
	got, err := api.Create(store.CreateProjectInput{
		Name: "demo", Path: "/tmp/demo",
	})
	if err != nil {
		t.Fatalf("Create: %v", err)
	}
	if got.Name != "demo" {
		t.Errorf("Name: got %q", got.Name)
	}
	if len(bus.Calls) != 1 || bus.Calls[0].Name != "project.created" {
		t.Errorf("expected project.created emit, got %+v", bus.Calls)
	}
}

func TestProjectsAPI_Delete_EmitsEvent(t *testing.T) {
	bus := &events.FakeEmitter{}
	repo := newFakeProjectsRepo()
	api := NewProjectsAPI(repo, bus)
	created, _ := api.Create(store.CreateProjectInput{Name: "x", Path: "/x"})
	bus.Calls = nil

	if err := api.Delete(created.ID); err != nil {
		t.Fatalf("Delete: %v", err)
	}
	if len(bus.Calls) != 1 || bus.Calls[0].Name != "project.deleted" {
		t.Errorf("expected project.deleted emit, got %+v", bus.Calls)
	}
}

func TestProjectsAPI_List(t *testing.T) {
	repo := newFakeProjectsRepo()
	api := NewProjectsAPI(repo, &events.FakeEmitter{})
	_, _ = api.Create(store.CreateProjectInput{Name: "a", Path: "/a"})
	_, _ = api.Create(store.CreateProjectInput{Name: "b", Path: "/b"})

	got, err := api.List()
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	if len(got) != 2 {
		t.Errorf("expected 2 projects, got %d", len(got))
	}
}
