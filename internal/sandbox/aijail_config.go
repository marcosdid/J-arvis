package sandbox

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

// WriteAijailConfig writes <cwd>/.ai-jail. Overwrites any prior file.
//
// `command` becomes json.Marshal(append([]string{"claude"}, claudeArgs...)).
// In F10.4 callers pass nil → command = ["claude"].
//
// `rw_maps` is populated by walking cwd and its immediate children, resolving
// any `.git` (directory or gitlink file) to the originating repo .git dir.
// Without these mounts, worktrees inside the jail report
// "fatal: not a git repository".
func WriteAijailConfig(cwd string, claudeArgs []string) error {
	gitDirs := discoverGitDirs(cwd)
	cmdArgv := append([]string{"claude"}, claudeArgs...)
	cmdJSON, err := json.Marshal(cmdArgv)
	if err != nil {
		return fmt.Errorf("marshal command: %w", err)
	}

	var rwBlock string
	if len(gitDirs) == 0 {
		rwBlock = "[]"
	} else {
		var b strings.Builder
		b.WriteString("[\n")
		for _, p := range gitDirs {
			b.WriteString(fmt.Sprintf("    %q,\n", p))
		}
		b.WriteString("]")
		rwBlock = b.String()
	}

	body := fmt.Sprintf(
		"command = %s\nrw_maps = %s\nro_maps = []\nhide_dotdirs = []\nmask = []\nallow_tcp_ports = []\n",
		string(cmdJSON), rwBlock,
	)
	target := filepath.Join(cwd, ".ai-jail")
	return os.WriteFile(target, []byte(body), 0o600)
}

// RemoveAijailConfig removes <cwd>/.ai-jail; missing file is success.
func RemoveAijailConfig(cwd string) error {
	if err := os.Remove(filepath.Join(cwd, ".ai-jail")); err != nil && !os.IsNotExist(err) {
		return err
	}
	return nil
}

// discoverGitDirs walks cwd and its immediate children, resolving each `.git`
// to the originating repo root .git directory. Returns sorted absolute paths.
func discoverGitDirs(cwd string) []string {
	var candidates []string
	candidates = append(candidates, filepath.Join(cwd, ".git"))
	if entries, err := os.ReadDir(cwd); err == nil {
		for _, e := range entries {
			if e.IsDir() {
				candidates = append(candidates, filepath.Join(cwd, e.Name(), ".git"))
			}
		}
	}
	var resolved []string
	seen := map[string]bool{}
	for _, g := range candidates {
		info, err := os.Lstat(g)
		if err != nil {
			continue
		}
		if info.IsDir() {
			if !seen[g] {
				resolved = append(resolved, g)
				seen[g] = true
			}
			continue
		}
		raw, err := os.ReadFile(g)
		if err != nil {
			continue
		}
		text := strings.TrimSpace(string(raw))
		if !strings.HasPrefix(text, "gitdir:") {
			continue
		}
		target := strings.TrimSpace(strings.TrimPrefix(text, "gitdir:"))
		parent := filepath.Dir(target)
		if filepath.Base(parent) != "worktrees" {
			continue
		}
		repoGit := filepath.Dir(parent)
		if filepath.Base(repoGit) != ".git" {
			continue
		}
		if !seen[repoGit] {
			resolved = append(resolved, repoGit)
			seen[repoGit] = true
		}
	}
	sort.Strings(resolved)
	return resolved
}
