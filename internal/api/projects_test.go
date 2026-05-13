package api

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/marcosdid/jarvis/internal/core"
	jgit "github.com/marcosdid/jarvis/internal/git"
	"github.com/marcosdid/jarvis/internal/store"
)

type fakeProjectsService struct {
	created []store.Project
	listErr error
}

func (f *fakeProjectsService) List(_ context.Context) ([]store.Project, error) {
	if f.listErr != nil {
		return nil, f.listErr
	}
	return f.created, nil
}

func (f *fakeProjectsService) Create(_ context.Context, in core.CreateProjectInput) (*store.Project, error) {
	p := store.Project{
		ID: "prj-" + in.Name, Name: in.Name, Path: in.Path,
		CreatedAt: time.Now(), Repositories: []store.Repository{},
	}
	f.created = append(f.created, p)
	return &p, nil
}

func (f *fakeProjectsService) Delete(_ context.Context, id string) error {
	for i, p := range f.created {
		if p.ID == id {
			f.created = append(f.created[:i], f.created[i+1:]...)
			return nil
		}
	}
	return store.ErrProjectNotFound
}

type errProjectsService struct{ err error }

func (e *errProjectsService) List(_ context.Context) ([]store.Project, error) { return nil, e.err }
func (e *errProjectsService) Create(_ context.Context, _ core.CreateProjectInput) (*store.Project, error) {
	return nil, e.err
}
func (e *errProjectsService) Delete(_ context.Context, _ string) error { return e.err }

func TestProjectsAPI_CreateDelegatesToService(t *testing.T) {
	svc := &fakeProjectsService{}
	api := NewProjectsAPI(svc)
	p, err := api.Create(core.CreateProjectInput{Name: "x", Path: "/x"})
	if err != nil {
		t.Fatalf("Create: %v", err)
	}
	if p.Name != "x" || p.Path != "/x" {
		t.Errorf("project not created correctly: %+v", p)
	}
}

func TestProjectsAPI_Create_PropagatesNoGitReposErr(t *testing.T) {
	svc := &errProjectsService{err: jgit.ErrNoGitRepos}
	api := NewProjectsAPI(svc)
	_, err := api.Create(core.CreateProjectInput{Name: "x", Path: "/x"})
	if !errors.Is(err, jgit.ErrNoGitRepos) {
		t.Errorf("want ErrNoGitRepos, got %v", err)
	}
}

func TestProjectsAPI_List(t *testing.T) {
	svc := &fakeProjectsService{}
	api := NewProjectsAPI(svc)
	_, _ = api.Create(core.CreateProjectInput{Name: "a", Path: "/a"})
	_, _ = api.Create(core.CreateProjectInput{Name: "b", Path: "/b"})

	got, err := api.List()
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	if len(got) != 2 {
		t.Errorf("expected 2 projects, got %d", len(got))
	}
}

func TestProjectsAPI_Delete(t *testing.T) {
	svc := &fakeProjectsService{}
	api := NewProjectsAPI(svc)
	created, _ := api.Create(core.CreateProjectInput{Name: "x", Path: "/x"})
	if err := api.Delete(created.ID); err != nil {
		t.Fatalf("Delete: %v", err)
	}
}
