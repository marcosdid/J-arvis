package git

import (
	"errors"
	"fmt"
	"strings"
)

var ErrNoGitRepos = errors.New("no .git directory at path or one level below")

// GitWorktreeError wraps a failed git subprocess invocation with stderr context.
type GitWorktreeError struct {
	Op     string // "list" | "add" | "remove"
	Repo   string
	Stderr string
	Cause  error
}

func (e *GitWorktreeError) Error() string {
	return fmt.Sprintf("git worktree %s failed in %s: %s", e.Op, e.Repo, e.Stderr)
}

func (e *GitWorktreeError) Unwrap() error { return e.Cause }

// IsAlreadyRemovedErr reports whether err is a GitWorktreeError whose stderr
// indicates the target path is not (or no longer) a registered worktree.
// Both CleanupForTask and DeleteOrphan treat this as idempotent success.
func IsAlreadyRemovedErr(err error) bool {
	var gwe *GitWorktreeError
	if !errors.As(err, &gwe) {
		return false
	}
	s := strings.ToLower(gwe.Stderr)
	return strings.Contains(s, "is not a working tree") ||
		strings.Contains(s, "not a valid path")
}
