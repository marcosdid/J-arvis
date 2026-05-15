package git

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"
)

// RepoSpec describes a discovered git repository within a project base path.
// SubPath is "." for monorepo (basePath/.git exists) or the child dir name
// for multi-repo layouts (basePath/<child>/.git exists).
type RepoSpec struct {
	Name    string
	SubPath string
}

// DetectRepos scans basePath for git repositories:
//  1. If basePath/.git is a directory: return one RepoSpec{Name: filepath.Base(basePath), SubPath: "."}.
//  2. Else, scan immediate children. Each child with child/.git as a
//     directory (NOT a file gitlink — submodules are skipped) becomes
//     a RepoSpec{Name: childName, SubPath: childName}. Returned sorted
//     by name.
//  3. Empty result: return ErrNoGitRepos.
func DetectRepos(basePath string) ([]RepoSpec, error) {
	info, err := os.Stat(basePath)
	if err != nil || !info.IsDir() {
		return nil, fmt.Errorf("%w: %s is not a directory", ErrNoGitRepos, basePath)
	}

	if dotGit, err := os.Stat(filepath.Join(basePath, ".git")); err == nil && dotGit.IsDir() {
		return []RepoSpec{{Name: filepath.Base(basePath), SubPath: "."}}, nil
	}

	entries, err := os.ReadDir(basePath)
	if err != nil {
		return nil, fmt.Errorf("%w: read dir: %v", ErrNoGitRepos, err)
	}

	var specs []RepoSpec
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		dotGit, err := os.Stat(filepath.Join(basePath, e.Name(), ".git"))
		if err != nil || !dotGit.IsDir() {
			// missing OR gitlink file → skip
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
