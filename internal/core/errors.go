package core

import "errors"

// ProjectHasTasksError is returned by ProjectsService.Delete when the project
// still has tasks (any state, including "discarded" — caller must delete them
// first). Wails surface maps to HTTP 409.
var ProjectHasTasksError = errors.New("project has tasks; discard them before deleting")

// WorktreeNotOrphanError is returned by WorktreesService.DeleteOrphan when
// the target worktree still has a task_id set. Maps to HTTP 422.
var WorktreeNotOrphanError = errors.New("worktree belongs to active task; use task cleanup flow instead")
