package api

import (
	"context"

	"github.com/marcosdid/jarvis/internal/core"
	"github.com/marcosdid/jarvis/internal/store"
)

// ProjectsService is the API-layer view of *core.ProjectsService. Defined
// here so tests can fake it without importing core.
type ProjectsService interface {
	List(ctx context.Context) ([]store.Project, error)
	Create(ctx context.Context, in core.CreateProjectInput) (*store.Project, error)
	Delete(ctx context.Context, id string) error
}

type ProjectsAPI struct {
	svc ProjectsService
}

func NewProjectsAPI(svc ProjectsService) *ProjectsAPI {
	return &ProjectsAPI{svc: svc}
}

func (a *ProjectsAPI) List() ([]store.Project, error) {
	return a.svc.List(context.Background())
}

func (a *ProjectsAPI) Create(in core.CreateProjectInput) (*store.Project, error) {
	return a.svc.Create(context.Background(), in)
}

func (a *ProjectsAPI) Delete(id string) error {
	return a.svc.Delete(context.Background(), id)
}
