package core

import (
	"context"
	"errors"
	"fmt"
	"path/filepath"

	"github.com/marcosdid/jarvis/internal/events"
	jgit "github.com/marcosdid/jarvis/internal/git"
	"github.com/marcosdid/jarvis/internal/store"
)

type WorktreesService struct {
	worktrees *store.WorktreesRepo
	repos     *store.RepositoriesRepo
	projects  *store.ProjectsRepo
	git       jgit.GitOps
	bus       events.Emitter
}

func NewWorktreesService(
	worktrees *store.WorktreesRepo,
	repos *store.RepositoriesRepo,
	projects *store.ProjectsRepo,
	git jgit.GitOps,
	bus events.Emitter,
) *WorktreesService {
	return &WorktreesService{
		worktrees: worktrees, repos: repos, projects: projects,
		git: git, bus: bus,
	}
}

func (s *WorktreesService) SyncProjectWorktrees(ctx context.Context, projectID string) ([]store.Worktree, error) {
	project, err := s.projects.Get(ctx, projectID)
	if err != nil {
		return nil, err
	}
	repos, err := s.repos.ListByProject(ctx, projectID)
	if err != nil {
		return nil, err
	}

	type discovered struct {
		repo store.Repository
		info jgit.WorktreeInfo
	}
	byPath := map[string]discovered{}

	for _, r := range repos {
		repoPath := filepath.Join(project.Path, r.SubPath)
		infos, err := s.git.List(ctx, repoPath)
		if err != nil {
			continue
		}
		for _, info := range infos {
			byPath[info.Path] = discovered{repo: r, info: info}
		}
	}

	existing, err := s.worktrees.ListByProject(ctx, projectID)
	if err != nil {
		return nil, err
	}
	knownPaths := map[string]bool{}
	for _, w := range existing {
		knownPaths[w.Path] = true
	}

	var emits []events.EmitCall
	for path, d := range byPath {
		id, err := s.worktrees.Upsert(ctx, store.WorktreeUpsert{
			RepositoryID: d.repo.ID, Path: path, Branch: d.info.Branch,
		})
		if err != nil {
			return nil, fmt.Errorf("upsert worktree %s: %w", path, err)
		}
		if !knownPaths[path] {
			emits = append(emits, events.EmitCall{
				Name: "worktree.created",
				Payload: map[string]any{
					"project_id":    projectID,
					"repository_id": d.repo.ID,
					"worktree_id":   id,
					"path":          path,
					"branch":        d.info.Branch,
					"task_id":       nil,
				},
			})
		}
	}

	for _, e := range emits {
		s.bus.Emit(e.Name, e.Payload)
	}
	return s.worktrees.ListByProject(ctx, projectID)
}

func (s *WorktreesService) CleanupForTask(ctx context.Context, taskID string) error {
	wts, err := s.worktrees.ListByTask(ctx, taskID)
	if err != nil {
		return fmt.Errorf("list worktrees for task: %w", err)
	}
	if len(wts) == 0 {
		return nil
	}

	var emits []events.EmitCall
	for _, w := range wts {
		subPath, projectPath, projectID, err := s.repoAndProjectPath(ctx, w.RepositoryID)
		if err != nil {
			_ = s.worktrees.OrphanRow(ctx, w.ID)
			emits = append(emits, orphanedEmit("", w.ID, w.Path, err.Error()))
			continue
		}
		repoFull := filepath.Join(projectPath, subPath)

		removeErr := s.git.Remove(ctx, repoFull, w.Path, true)
		switch {
		case removeErr == nil || jgit.IsAlreadyRemovedErr(removeErr):
			if err := s.worktrees.Delete(ctx, w.ID); err != nil {
				return fmt.Errorf("delete worktree row %s: %w", w.ID, err)
			}
			emits = append(emits, removedEmit(projectID, w.ID, w.Path, &taskID))
		default:
			if err := s.worktrees.OrphanRow(ctx, w.ID); err != nil {
				return fmt.Errorf("orphan worktree row %s: %w", w.ID, err)
			}
			gwe := &jgit.GitWorktreeError{}
			reason := removeErr.Error()
			if errors.As(removeErr, &gwe) {
				reason = gwe.Stderr
			}
			emits = append(emits, orphanedEmit(projectID, w.ID, w.Path, reason))
		}
	}

	for _, e := range emits {
		s.bus.Emit(e.Name, e.Payload)
	}
	return nil
}

func (s *WorktreesService) DeleteOrphan(ctx context.Context, id string) error {
	w, err := s.worktrees.GetByID(ctx, id)
	if err != nil {
		return err
	}
	if w.TaskID != nil {
		return fmt.Errorf("%w (worktree=%s, task=%s)", WorktreeNotOrphanError, id, *w.TaskID)
	}
	subPath, projectPath, projectID, err := s.repoAndProjectPath(ctx, w.RepositoryID)
	if err != nil {
		return err
	}
	repoFull := filepath.Join(projectPath, subPath)
	removeErr := s.git.Remove(ctx, repoFull, w.Path, true)
	if removeErr != nil && !jgit.IsAlreadyRemovedErr(removeErr) {
		return removeErr
	}
	if err := s.worktrees.Delete(ctx, id); err != nil {
		return err
	}
	s.bus.Emit("worktree.removed", map[string]any{
		"project_id":  projectID,
		"worktree_id": id,
		"path":        w.Path,
		"task_id":     nil,
	})
	return nil
}

func (s *WorktreesService) repoAndProjectPath(ctx context.Context, repositoryID string) (subPath, projectPath, projectID string, err error) {
	row := s.repos.GetByID(ctx, repositoryID)
	if row == nil {
		return "", "", "", errors.New("repository not found")
	}
	project, err := s.projects.Get(ctx, row.ProjectID)
	if err != nil {
		return "", "", "", err
	}
	return row.SubPath, project.Path, project.ID, nil
}

func removedEmit(projectID, worktreeID, path string, taskID *string) events.EmitCall {
	return events.EmitCall{
		Name: "worktree.removed",
		Payload: map[string]any{
			"project_id":  projectID,
			"worktree_id": worktreeID,
			"path":        path,
			"task_id":     taskID,
		},
	}
}

func orphanedEmit(projectID, worktreeID, path, reason string) events.EmitCall {
	return events.EmitCall{
		Name: "worktree.orphaned",
		Payload: map[string]any{
			"project_id":  projectID,
			"worktree_id": worktreeID,
			"path":        path,
			"reason":      reason,
		},
	}
}
