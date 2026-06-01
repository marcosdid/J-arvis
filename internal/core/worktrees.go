package core

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/marcosdid/jarvis/internal/events"
	jgit "github.com/marcosdid/jarvis/internal/git"
	"github.com/marcosdid/jarvis/internal/store"
)

type WorktreesService struct {
	worktrees *store.WorktreesRepo
	repos     *store.RepositoriesRepo
	projects  *store.ProjectsRepo
	tasks     *store.TasksRepo
	git       jgit.GitOps
	bus       events.Emitter
}

func NewWorktreesService(
	worktrees *store.WorktreesRepo,
	repos *store.RepositoriesRepo,
	projects *store.ProjectsRepo,
	tasks *store.TasksRepo,
	git jgit.GitOps,
	bus events.Emitter,
) *WorktreesService {
	return &WorktreesService{
		worktrees: worktrees, repos: repos, projects: projects, tasks: tasks,
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

	// Reconcile only paths that J-arvs already tracks. Worktrees the user
	// created outside the J-arvs flow (their own feature branches, histórias,
	// etc.) must remain invisible — otherwise they'd appear as fake orphans
	// and the UI's ✕ button would silently `git worktree remove` their work.
	for path, d := range byPath {
		if !knownPaths[path] {
			continue
		}
		if _, err := s.worktrees.Upsert(ctx, store.WorktreeUpsert{
			RepositoryID: d.repo.ID, Path: path, Branch: d.info.Branch,
		}); err != nil {
			return nil, fmt.Errorf("upsert worktree %s: %w", path, err)
		}
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

// CreateForTask atomically creates one git worktree per project repository for
// the given task. Derives target cwd as `<project.path>/../<project.name>--<branchSlug>`
// for monorepo or as a parent dir containing per-repo children for multi-repo.
// Mirrors Python `_create_worktrees_atomic` semantics.
//
// Returns the persisted store.Worktree rows.
func (s *WorktreesService) CreateForTask(ctx context.Context, taskID, branch string) ([]store.Worktree, error) {
	existing, err := s.worktrees.ListByTask(ctx, taskID)
	if err != nil {
		return nil, err
	}
	if len(existing) > 0 {
		return nil, ErrTaskAlreadyHasWorktrees
	}

	taskProject, err := s.projects.GetProjectForTask(ctx, taskID)
	if err != nil {
		return nil, fmt.Errorf("resolve project for task: %w", err)
	}

	repos, err := s.repos.ListByProject(ctx, taskProject.ID)
	if err != nil {
		return nil, err
	}
	if len(repos) == 0 {
		return nil, fmt.Errorf("project %s has no repositories", taskProject.ID)
	}

	cwd := filepath.Join(
		filepath.Dir(taskProject.Path),
		filepath.Base(taskProject.Path)+"--"+branchSlug(branch),
	)
	if _, err := os.Stat(cwd); err == nil {
		return nil, fmt.Errorf("derived cwd already exists: %s", cwd)
	}

	isMulti := len(repos) > 1
	if isMulti {
		if err := os.MkdirAll(cwd, 0o755); err != nil {
			return nil, fmt.Errorf("mkdir multi-repo cwd: %w", err)
		}
	}

	type created struct {
		repo store.Repository
		path string
	}
	var done []created
	rollback := func() {
		for i := len(done) - 1; i >= 0; i-- {
			repoFull := filepath.Join(taskProject.Path, done[i].repo.SubPath)
			_ = s.git.Remove(ctx, repoFull, done[i].path, true)
		}
		if isMulti {
			_ = os.Remove(cwd)
		}
	}

	var out []store.Worktree
	for _, r := range repos {
		target := cwd
		if isMulti {
			target = filepath.Join(cwd, r.Name)
		}
		repoFull := filepath.Join(taskProject.Path, r.SubPath)
		if err := s.git.Add(ctx, repoFull, target, branch); err != nil {
			rollback()
			return nil, fmt.Errorf("git worktree add %s: %w", target, err)
		}
		done = append(done, created{repo: r, path: target})

		tid := taskID
		b := branch
		id, err := s.worktrees.Upsert(ctx, store.WorktreeUpsert{
			RepositoryID: r.ID, Path: target, Branch: &b, TaskID: &tid,
		})
		if err != nil {
			rollback()
			return nil, fmt.Errorf("upsert worktree row: %w", err)
		}
		got, err := s.worktrees.GetByID(ctx, id)
		if err != nil {
			rollback()
			return nil, err
		}
		out = append(out, *got)
	}

	// Drop a context file the spawned Claude session reads on start. We do this
	// for every CreateForTask (single- and multi-repo); the renderer adapts to
	// the layout. Best-effort: failures don't roll back — the worktrees are
	// already valid, the context file is purely documentation.
	//
	// Skip if the target dir doesn't exist on disk yet — this happens in tests
	// where git.Add is a fake that doesn't actually create the worktree dir.
	// In production the dir always exists by this point.
	contextCwd := cwd
	if !isMulti {
		contextCwd = out[0].Path
	}
	if _, statErr := os.Stat(contextCwd); statErr == nil {
		if task, err := s.tasks.Get(ctx, taskID); err == nil {
			_ = WriteTaskContext(TaskContextInput{
				Cwd:     contextCwd,
				Project: *taskProject,
				Task:    *task,
				Branch:  branch,
				Repos:   repos,
			})
		}
	}

	return out, nil
}

// branchSlug converts a branch ref like "feat/new-thing" into a filesystem-safe
// suffix "feat-new-thing".
func branchSlug(branch string) string {
	s := strings.ReplaceAll(branch, "/", "-")
	s = strings.ReplaceAll(s, " ", "-")
	return s
}
