package core

import (
	"context"
	"fmt"
	"log"
	"path/filepath"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/marcosdid/jarvis/internal/catalog"
	"github.com/marcosdid/jarvis/internal/events"
	"github.com/marcosdid/jarvis/internal/hooks"
	"github.com/marcosdid/jarvis/internal/sandbox"
	"github.com/marcosdid/jarvis/internal/store"
)

// HookServer is the minimal slice of *hooks.Server this service needs.
type HookServer interface {
	BaseURL() string
}

type SessionsService struct {
	sessions   *store.SessionsRepo
	tasks      *store.TasksRepo
	worktrees  *store.WorktreesRepo
	projects   *store.ProjectsRepo
	wtSvc      *WorktreesService
	runtime    sandbox.Runtime
	registry   *hooks.TokenRegistry
	hookSrv    HookServer
	catalog    *catalog.Catalog
	bus        events.Emitter
	claudeHome string
}

func NewSessionsService(
	sessions *store.SessionsRepo,
	tasks *store.TasksRepo,
	worktrees *store.WorktreesRepo,
	projects *store.ProjectsRepo,
	wtSvc *WorktreesService,
	runtime sandbox.Runtime,
	registry *hooks.TokenRegistry,
	hookSrv HookServer,
	cat *catalog.Catalog,
	bus events.Emitter,
	claudeHome string,
) *SessionsService {
	return &SessionsService{
		sessions: sessions, tasks: tasks, worktrees: worktrees, projects: projects, wtSvc: wtSvc,
		runtime: runtime, registry: registry, hookSrv: hookSrv, catalog: cat, bus: bus,
		claudeHome: claudeHome,
	}
}

func (s *SessionsService) Start(ctx context.Context, taskID string) (*store.Session, error) {
	// 1. Sandbox preflight.
	if err := sandbox.SandboxAvailable(); err != nil {
		return nil, fmt.Errorf("%w: %v", ErrSandboxUnavailable, err)
	}
	terminal, err := sandbox.DetectTerminal()
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrSandboxUnavailable, err)
	}

	// 2. Task guards.
	task, err := s.tasks.Get(ctx, taskID)
	if err != nil {
		return nil, err
	}
	if IsTerminal(task.State) {
		return nil, ErrTaskInTerminalState
	}
	active, err := s.sessions.ListActiveByTask(ctx, taskID)
	if err != nil {
		return nil, err
	}
	if len(active) > 0 {
		return nil, ErrTaskAlreadyHasActiveSession
	}

	// 3. Resolve worktrees + cwd.
	wts, err := s.worktrees.ListByTask(ctx, taskID)
	if err != nil {
		return nil, err
	}
	if len(wts) == 0 {
		branch := taskBranchOrSlug(task)
		wts, err = s.wtSvc.CreateForTask(ctx, taskID, branch)
		if err != nil {
			return nil, fmt.Errorf("create worktrees for task: %w", err)
		}
	}
	cwd := wts[0].Path
	if len(wts) > 1 {
		// Multi-repo: all worktrees share the same parent by construction.
		cwd = filepath.Dir(wts[0].Path)
	}

	// 4. Generate token + register in memory.
	sessionID := uuid.NewString()
	token := s.registry.Generate(sessionID)

	// 5. Resolve permission profile (catalog) → claude_args for ai-jail.
	profileName := s.catalog.FallbackPermissionProfile
	if task.PermissionProfile != nil && *task.PermissionProfile != "" {
		profileName = *task.PermissionProfile
	}
	profile, err := s.catalog.ResolveProfile(profileName)
	if err != nil {
		s.registry.Revoke(token)
		return nil, fmt.Errorf("resolve permission profile: %w", err)
	}

	// 6. Write .claude/settings.json + .ai-jail (+ gitignore).
	if err := sandbox.WriteSettings(cwd, s.hookSrv.BaseURL(), token); err != nil {
		s.registry.Revoke(token)
		return nil, fmt.Errorf("write settings: %w", err)
	}
	_ = sandbox.EnsureGitignore(cwd)
	if err := sandbox.WriteAijailConfig(cwd, profile.ClaudeArgs); err != nil {
		_ = sandbox.RemoveSettings(cwd)
		s.registry.Revoke(token)
		return nil, fmt.Errorf("write .ai-jail: %w", err)
	}

	// 7. Spawn subprocess.
	handle, err := s.runtime.Spawn(ctx, sandbox.RuntimeSpec{Cwd: cwd, Terminal: terminal})
	if err != nil {
		_ = sandbox.RemoveAijailConfig(cwd)
		_ = sandbox.RemoveSettings(cwd)
		s.registry.Revoke(token)
		return nil, fmt.Errorf("spawn ai-jail: %w", err)
	}

	// 8. Persist row.
	pid := handle.PID
	row := store.Session{
		ID: sessionID, TaskID: taskID,
		Status: "executing", PID: &pid,
		Cwd: cwd, HookToken: token,
		StartedAt: time.Now(),
	}
	if err := s.sessions.Insert(ctx, row); err != nil {
		_ = s.runtime.Kill(ctx, handle)
		_ = sandbox.RemoveAijailConfig(cwd)
		_ = sandbox.RemoveSettings(cwd)
		s.registry.Revoke(token)
		return nil, fmt.Errorf("insert session row: %w", err)
	}

	s.bus.Emit("session.started", row)
	return &row, nil
}

func (s *SessionsService) Stop(ctx context.Context, sessionID string) error {
	row, err := s.sessions.GetByID(ctx, sessionID)
	if err != nil {
		return err
	}
	if row.EndedAt != nil {
		return nil // idempotent
	}

	finalStatus := "done"
	if row.PID != nil {
		if err := s.runtime.Kill(ctx, sandbox.Handle{PID: *row.PID}); err != nil {
			finalStatus = "error"
		}
	}
	s.registry.Revoke(row.HookToken)

	_ = sandbox.RemoveSettings(row.Cwd)
	_ = sandbox.RemoveAijailConfig(row.Cwd)

	if err := s.sessions.MarkEnded(ctx, sessionID, finalStatus); err != nil {
		return err
	}
	s.bus.Emit("session.stopped", map[string]any{
		"id": sessionID, "task_id": row.TaskID, "final_status": finalStatus,
	})
	return nil
}

func (s *SessionsService) ListByTask(ctx context.Context, taskID string) ([]store.Session, error) {
	return s.sessions.ListByTask(ctx, taskID)
}

// CleanupForTask invokes Stop on every active session for taskID. Tolerant:
// per-session failures are logged but never propagated, matching the F10.3
// WorktreeCleanup contract.
func (s *SessionsService) CleanupForTask(ctx context.Context, taskID string) error {
	active, err := s.sessions.ListActiveByTask(ctx, taskID)
	if err != nil {
		return fmt.Errorf("list active sessions: %w", err)
	}
	for _, sess := range active {
		if err := s.Stop(ctx, sess.ID); err != nil {
			log.Printf("session cleanup: stop %s failed: %v", sess.ID, err)
		}
	}
	return nil
}

func (s *SessionsService) GetTranscript(ctx context.Context, sessionID string) ([]sandbox.TranscriptMessage, error) {
	row, err := s.sessions.GetByID(ctx, sessionID)
	if err != nil {
		return nil, err
	}
	encoded := strings.ReplaceAll(filepath.Clean(row.Cwd), string(filepath.Separator), "-")
	dir := filepath.Join(s.claudeHome, "projects", encoded)
	files, err := sandbox.FindTranscriptFiles(dir)
	if err != nil || len(files) == 0 {
		return []sandbox.TranscriptMessage{}, nil
	}
	var all []sandbox.TranscriptMessage
	for _, f := range files {
		msgs, err := sandbox.ParseTranscript(f)
		if err != nil {
			continue
		}
		all = append(all, msgs...)
	}
	return all, nil
}

func taskBranchOrSlug(task *store.Task) string {
	if task.Branch != nil && *task.Branch != "" {
		return *task.Branch
	}
	return "task-" + task.ID
}
