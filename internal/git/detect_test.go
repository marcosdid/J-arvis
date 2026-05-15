package git

import (
	"errors"
	"os"
	"path/filepath"
	"testing"
)

func mkGitDir(t *testing.T, parent, name string) string {
	t.Helper()
	p := filepath.Join(parent, name)
	if err := os.MkdirAll(filepath.Join(p, ".git"), 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	return p
}

func TestDetectRepos_Monorepo(t *testing.T) {
	dir := mkGitDir(t, t.TempDir(), "proj")
	specs, err := DetectRepos(dir)
	if err != nil {
		t.Fatalf("DetectRepos: %v", err)
	}
	if len(specs) != 1 {
		t.Fatalf("want 1 spec, got %d", len(specs))
	}
	if specs[0].SubPath != "." {
		t.Errorf("SubPath: got %q, want %q", specs[0].SubPath, ".")
	}
	if specs[0].Name != "proj" {
		t.Errorf("Name: got %q, want %q", specs[0].Name, "proj")
	}
}

func TestDetectRepos_MultiRepo_Sorted(t *testing.T) {
	base := t.TempDir()
	mkGitDir(t, base, "zeta")
	mkGitDir(t, base, "alpha")
	mkGitDir(t, base, "mango")
	specs, err := DetectRepos(base)
	if err != nil {
		t.Fatalf("DetectRepos: %v", err)
	}
	if len(specs) != 3 {
		t.Fatalf("want 3 specs, got %d", len(specs))
	}
	want := []string{"alpha", "mango", "zeta"}
	for i, w := range want {
		if specs[i].Name != w || specs[i].SubPath != w {
			t.Errorf("spec[%d]: got %+v, want name=%s sub_path=%s", i, specs[i], w, w)
		}
	}
}

func TestDetectRepos_GitlinkSubmoduleSkipped(t *testing.T) {
	base := t.TempDir()
	mkGitDir(t, base, "real-repo")
	sub := filepath.Join(base, "submodule")
	if err := os.MkdirAll(sub, 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	// .git as a FILE (gitlink), not a directory
	if err := os.WriteFile(filepath.Join(sub, ".git"), []byte("gitdir: ../.git/modules/submodule\n"), 0o644); err != nil {
		t.Fatalf("write: %v", err)
	}
	specs, err := DetectRepos(base)
	if err != nil {
		t.Fatalf("DetectRepos: %v", err)
	}
	if len(specs) != 1 || specs[0].Name != "real-repo" {
		t.Errorf("expected only real-repo, got %+v", specs)
	}
}

func TestDetectRepos_EmptyDir(t *testing.T) {
	_, err := DetectRepos(t.TempDir())
	if !errors.Is(err, ErrNoGitRepos) {
		t.Errorf("expected ErrNoGitRepos, got %v", err)
	}
}

func TestDetectRepos_NotADir(t *testing.T) {
	f := filepath.Join(t.TempDir(), "x")
	os.WriteFile(f, []byte("not a dir"), 0o644)
	_, err := DetectRepos(f)
	if !errors.Is(err, ErrNoGitRepos) {
		t.Errorf("expected ErrNoGitRepos for non-dir, got %v", err)
	}
}
