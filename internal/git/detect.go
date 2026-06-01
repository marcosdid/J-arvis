package git

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"
)

// RepoSpec describes a discovered git repository within a project base path.
// SubPath is "." for the basePath itself, or the child dir name for a
// sibling/child repo. A single basePath can produce both: a repo at the root
// AND children that are independent repos (hybrid layout).
type RepoSpec struct {
	Name    string
	SubPath string
}

// DetectRepos scans basePath for git repositories with INCLUSIVE semantics:
//
//   - If basePath/.git is a directory: add RepoSpec{Name: filepath.Base(basePath), SubPath: "."}.
//   - Scan immediate children: each child whose `.git` is a directory (NOT a
//     gitlink file — submodules are skipped) becomes a RepoSpec.
//   - The two checks are independent: a hybrid layout (root has .git AND has
//     child repos) returns all of them. This matches real super-projects like
//     gcb-hub where the root holds context/docs and siblings hold backend/frontend.
//   - Empty result: returns ErrNoGitRepos.
//
// Results are sorted by Name for deterministic ordering.
func DetectRepos(basePath string) ([]RepoSpec, error) {
	info, err := os.Stat(basePath)
	if err != nil || !info.IsDir() {
		return nil, fmt.Errorf("%w: %s is not a directory", ErrNoGitRepos, basePath)
	}

	var specs []RepoSpec

	if dotGit, err := os.Stat(filepath.Join(basePath, ".git")); err == nil && dotGit.IsDir() {
		specs = append(specs, RepoSpec{Name: filepath.Base(basePath), SubPath: "."})
	}

	entries, err := os.ReadDir(basePath)
	if err != nil {
		return nil, fmt.Errorf("%w: read dir: %v", ErrNoGitRepos, err)
	}
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		dotGit, err := os.Stat(filepath.Join(basePath, e.Name(), ".git"))
		if err != nil || !dotGit.IsDir() {
			continue
		}
		specs = append(specs, RepoSpec{Name: e.Name(), SubPath: e.Name()})
	}

	if len(specs) == 0 {
		return nil, fmt.Errorf("%w: %s", ErrNoGitRepos, basePath)
	}

	sort.Slice(specs, func(i, j int) bool { return specs[i].Name < specs[j].Name })
	return specs, nil
}
