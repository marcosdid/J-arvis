package git

import (
	"bytes"
	"context"
	"os/exec"
	"strings"
	"time"
)

// WorktreeInfo describes a single entry returned by `git worktree list --porcelain`.
type WorktreeInfo struct {
	Path   string
	Branch *string // nil for detached HEAD or bare worktree
}

// GitOps is the seam between the core layer and the git binary on disk.
// Tests inject fakes; production wires NewSubprocessOps().
type GitOps interface {
	List(ctx context.Context, repo string) ([]WorktreeInfo, error)
	Add(ctx context.Context, repo, target, branch string) error
	Remove(ctx context.Context, repo, target string, force bool) error
}

type subprocessOps struct {
	timeout time.Duration
}

func NewSubprocessOps() GitOps {
	return &subprocessOps{timeout: 30 * time.Second}
}

func (s *subprocessOps) run(ctx context.Context, op string, repo string, args ...string) ([]byte, error) {
	ctx, cancel := context.WithTimeout(ctx, s.timeout)
	defer cancel()
	cmd := exec.CommandContext(ctx, "git", append([]string{"-C", repo}, args...)...)
	var stderr bytes.Buffer
	cmd.Stderr = &stderr
	out, err := cmd.Output()
	if err != nil {
		return nil, &GitWorktreeError{
			Op:     op,
			Repo:   repo,
			Stderr: strings.TrimSpace(stderr.String()),
			Cause:  err,
		}
	}
	return out, nil
}

func (s *subprocessOps) List(ctx context.Context, repo string) ([]WorktreeInfo, error) {
	out, err := s.run(ctx, "list", repo, "worktree", "list", "--porcelain")
	if err != nil {
		return nil, err
	}
	return parseWorktreeList(string(out)), nil
}

func (s *subprocessOps) Add(ctx context.Context, repo, target, branch string) error {
	_, err := s.run(ctx, "add", repo, "worktree", "add", target, "-b", branch)
	return err
}

func (s *subprocessOps) Remove(ctx context.Context, repo, target string, force bool) error {
	args := []string{"worktree", "remove", target}
	if force {
		args = append(args, "--force")
	}
	_, err := s.run(ctx, "remove", repo, args...)
	return err
}

const (
	_worktreePrefix = "worktree "
	_branchPrefix   = "branch refs/heads/"
)

// parseWorktreeList parses `git worktree list --porcelain` output.
// Format: blank-line-separated blocks; each block has a `worktree <path>` line
// and optionally a `branch refs/heads/<name>` line. Detached/bare have no branch.
func parseWorktreeList(output string) []WorktreeInfo {
	text := strings.TrimSpace(output)
	if text == "" {
		return nil
	}
	var infos []WorktreeInfo
	for _, block := range strings.Split(text, "\n\n") {
		var path string
		var branch *string
		for _, line := range strings.Split(block, "\n") {
			switch {
			case strings.HasPrefix(line, _worktreePrefix):
				path = strings.TrimPrefix(line, _worktreePrefix)
			case strings.HasPrefix(line, _branchPrefix):
				b := strings.TrimPrefix(line, _branchPrefix)
				branch = &b
			}
		}
		if path != "" {
			infos = append(infos, WorktreeInfo{Path: path, Branch: branch})
		}
	}
	return infos
}
