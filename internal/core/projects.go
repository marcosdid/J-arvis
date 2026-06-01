package core

import (
	"context"
	"fmt"

	"github.com/marcosdid/jarvis/internal/events"
	jgit "github.com/marcosdid/jarvis/internal/git"
	"github.com/marcosdid/jarvis/internal/store"
)

type CreateProjectInput struct {
	Name string `json:"name"`
	Path string `json:"path"`
}

type ProjectsService struct {
	projects *store.ProjectsRepo
	repos    *store.RepositoriesRepo
	tasks    *store.TasksRepo
	bus      events.Emitter
}

func NewProjectsService(
	projects *store.ProjectsRepo,
	repos *store.RepositoriesRepo,
	tasks *store.TasksRepo,
	bus events.Emitter,
) *ProjectsService {
	return &ProjectsService{projects: projects, repos: repos, tasks: tasks, bus: bus}
}

// Create validates the filesystem path, detects repos, and persists Project +
// Repository rows. Returns the project with Repositories hydrated.
//
// Error mapping for the API layer:
//   - jgit.ErrNoGitRepos        → 422 (no .git found at path or 1 level below)
//   - store path-unique conflict → 409 (path already used by another project)
func (s *ProjectsService) Create(ctx context.Context, in CreateProjectInput) (*store.Project, error) {
	specs, err := jgit.DetectRepos(in.Path)
	if err != nil {
		return nil, err
	}

	project, err := s.projects.Create(ctx, store.CreateProjectInput{Name: in.Name, Path: in.Path})
	if err != nil {
		return nil, fmt.Errorf("create project row: %w", err)
	}

	repoInputs := make([]store.RepoSpecInput, 0, len(specs))
	for _, spec := range specs {
		name := spec.Name
		if spec.SubPath == "." {
			name = project.Name
		}
		repoInputs = append(repoInputs, store.RepoSpecInput{Name: name, SubPath: spec.SubPath})
	}
	createdRepos, err := s.repos.CreateBulk(ctx, project.ID, repoInputs)
	if err != nil {
		_ = s.projects.Delete(ctx, project.ID)
		return nil, fmt.Errorf("create repositories: %w", err)
	}
	project.Repositories = createdRepos
	s.bus.Emit("project.created", project)
	return project, nil
}

// RescanRepositories re-runs DetectRepos on the project's path and inserts
// any repositories that exist on disk but are missing from the DB. Idempotent:
// no inserts and no events when everything is already in sync. Never deletes
// existing rows (tasks/worktrees may reference them).
//
// Use case: a project was created when DetectRepos had limited heuristics, so
// not all sub-repos were registered. The user adds repos to disk (or the
// detect logic improves), and Rescan brings the DB in line without forcing
// a delete+recreate of the project.
func (s *ProjectsService) RescanRepositories(ctx context.Context, projectID string) (*store.Project, error) {
	project, err := s.projects.Get(ctx, projectID)
	if err != nil {
		return nil, err
	}

	specs, err := jgit.DetectRepos(project.Path)
	if err != nil {
		return nil, err
	}

	existing := map[string]struct{}{}
	for _, r := range project.Repositories {
		existing[r.SubPath] = struct{}{}
	}

	toAdd := make([]store.RepoSpecInput, 0, len(specs))
	for _, spec := range specs {
		if _, ok := existing[spec.SubPath]; ok {
			continue
		}
		name := spec.Name
		if spec.SubPath == "." {
			name = project.Name
		}
		toAdd = append(toAdd, store.RepoSpecInput{Name: name, SubPath: spec.SubPath})
	}

	if len(toAdd) == 0 {
		return project, nil
	}

	if _, err := s.repos.CreateBulk(ctx, project.ID, toAdd); err != nil {
		return nil, fmt.Errorf("insert new repositories: %w", err)
	}

	// Re-fetch to get the fully hydrated repo list with assigned IDs.
	refreshed, err := s.projects.Get(ctx, projectID)
	if err != nil {
		return nil, err
	}
	s.bus.Emit("project.updated", refreshed)
	return refreshed, nil
}

// Delete refuses if the project still has tasks. Returns ProjectHasTasksError.
func (s *ProjectsService) Delete(ctx context.Context, id string) error {
	tasks, err := s.tasks.List(ctx, store.TaskFilters{ProjectIDs: []string{id}})
	if err != nil {
		return fmt.Errorf("count tasks: %w", err)
	}
	if len(tasks) > 0 {
		return fmt.Errorf("%w (count: %d)", ProjectHasTasksError, len(tasks))
	}
	if err := s.projects.Delete(ctx, id); err != nil {
		return err
	}
	s.bus.Emit("project.deleted", map[string]string{"id": id})
	return nil
}

// Get retrieves a single project by id.
func (s *ProjectsService) Get(ctx context.Context, id string) (*store.Project, error) {
	return s.projects.Get(ctx, id)
}

// List delegates to ProjectsRepo which hydrates repositories via RepositoriesRepo.
func (s *ProjectsService) List(ctx context.Context) ([]store.Project, error) {
	return s.projects.List(ctx)
}
