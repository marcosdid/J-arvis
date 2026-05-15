package core

import "errors"

// ProjectHasTasksError is returned by ProjectsService.Delete when the project
// still has tasks (any state, including "discarded" — caller must delete them
// first). Wails surface maps to HTTP 409.
var ProjectHasTasksError = errors.New("project has tasks; discard them before deleting")

// WorktreeNotOrphanError is returned by WorktreesService.DeleteOrphan when
// the target worktree still has a task_id set. Maps to HTTP 422.
var WorktreeNotOrphanError = errors.New("worktree belongs to active task; use task cleanup flow instead")

// ErrTaskAlreadyHasWorktrees: CreateForTask refuses to add worktrees to a
// task that already has them. Callers should use the existing set or call
// CleanupForTask first.
var ErrTaskAlreadyHasWorktrees = errors.New("task already has worktrees; reuse or cleanup first")

// Session-related sentinels (F10.4).
var (
	ErrTaskInTerminalState         = errors.New("task is in terminal state; cannot start session")
	ErrTaskAlreadyHasActiveSession = errors.New("task already has an active session")
	ErrSandboxUnavailable          = errors.New("sandbox runtime unavailable (ai-jail or terminal missing)")
)
