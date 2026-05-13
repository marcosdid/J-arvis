package api

import (
	"context"

	"github.com/marcosdid/jarvis/internal/events"
	"github.com/marcosdid/jarvis/internal/store"
)

type ProjectsRepo interface {
	List(context.Context) ([]store.Project, error)
	Get(context.Context, string) (*store.Project, error)
	Create(context.Context, store.CreateProjectInput) (*store.Project, error)
	Delete(context.Context, string) error
}

type ProjectsAPI struct {
	repo ProjectsRepo
	bus  events.Emitter
}

func NewProjectsAPI(repo ProjectsRepo, bus events.Emitter) *ProjectsAPI {
	return &ProjectsAPI{repo: repo, bus: bus}
}

func (a *ProjectsAPI) List() ([]store.Project, error) {
	return a.repo.List(context.Background())
}

func (a *ProjectsAPI) Create(in store.CreateProjectInput) (*store.Project, error) {
	created, err := a.repo.Create(context.Background(), in)
	if err != nil {
		return nil, err
	}
	a.bus.Emit("project.created", created)
	return created, nil
}

func (a *ProjectsAPI) Delete(id string) error {
	if err := a.repo.Delete(context.Background(), id); err != nil {
		return err
	}
	a.bus.Emit("project.deleted", map[string]string{"id": id})
	return nil
}
