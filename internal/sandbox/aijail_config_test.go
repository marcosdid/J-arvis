package sandbox

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestWriteAijailConfig_BareClaudeCommand_EmptyRwMaps(t *testing.T) {
	dir := t.TempDir()
	if err := WriteAijailConfig(dir, nil); err != nil {
		t.Fatalf("WriteAijailConfig: %v", err)
	}
	raw, err := os.ReadFile(filepath.Join(dir, ".ai-jail"))
	if err != nil {
		t.Fatalf("read: %v", err)
	}
	s := string(raw)
	if !strings.Contains(s, `command = ["claude"]`) {
		t.Errorf("missing bare claude command: %q", s)
	}
	if !strings.Contains(s, "rw_maps = []") {
		t.Errorf("expected empty rw_maps inline: %q", s)
	}
	for _, k := range []string{"ro_maps", "hide_dotdirs", "mask", "allow_tcp_ports"} {
		if !strings.Contains(s, k+" = []") {
			t.Errorf("missing %s = []: %q", k, s)
		}
	}
}

func TestWriteAijailConfig_WithClaudeArgs(t *testing.T) {
	dir := t.TempDir()
	args := []string{"--dangerously-skip-permissions"}
	if err := WriteAijailConfig(dir, args); err != nil {
		t.Fatalf("WriteAijailConfig: %v", err)
	}
	raw, _ := os.ReadFile(filepath.Join(dir, ".ai-jail"))
	if !strings.Contains(string(raw), `command = ["claude","--dangerously-skip-permissions"]`) {
		t.Errorf("args not interpolated: %q", string(raw))
	}
}

func TestWriteAijailConfig_DiscoversGitDirInMonorepo(t *testing.T) {
	dir := t.TempDir()
	if err := os.MkdirAll(filepath.Join(dir, ".git"), 0o755); err != nil {
		t.Fatalf("mkdir .git: %v", err)
	}
	if err := WriteAijailConfig(dir, nil); err != nil {
		t.Fatalf("WriteAijailConfig: %v", err)
	}
	raw, _ := os.ReadFile(filepath.Join(dir, ".ai-jail"))
	want := filepath.Join(dir, ".git")
	if !strings.Contains(string(raw), want) {
		t.Errorf("rw_maps missing %s: %q", want, string(raw))
	}
}

func TestWriteAijailConfig_DiscoversGitDirInMultiRepoChildren(t *testing.T) {
	dir := t.TempDir()
	for _, name := range []string{"alpha", "beta"} {
		if err := os.MkdirAll(filepath.Join(dir, name, ".git"), 0o755); err != nil {
			t.Fatalf("mkdir: %v", err)
		}
	}
	if err := WriteAijailConfig(dir, nil); err != nil {
		t.Fatalf("WriteAijailConfig: %v", err)
	}
	raw, _ := os.ReadFile(filepath.Join(dir, ".ai-jail"))
	for _, name := range []string{"alpha", "beta"} {
		want := filepath.Join(dir, name, ".git")
		if !strings.Contains(string(raw), want) {
			t.Errorf("rw_maps missing %s: %q", want, string(raw))
		}
	}
}

func TestWriteAijailConfig_ResolvesGitlinkWorktreeFile(t *testing.T) {
	dir := t.TempDir()
	repoRoot := filepath.Join(dir, "src-repo")
	gitWorktreesDir := filepath.Join(repoRoot, ".git", "worktrees", "feat-x")
	if err := os.MkdirAll(gitWorktreesDir, 0o755); err != nil {
		t.Fatalf("mkdir worktrees: %v", err)
	}
	wtDir := filepath.Join(dir, "worktree-cwd")
	if err := os.MkdirAll(wtDir, 0o755); err != nil {
		t.Fatalf("mkdir wt: %v", err)
	}
	gitlinkContent := "gitdir: " + gitWorktreesDir + "\n"
	if err := os.WriteFile(filepath.Join(wtDir, ".git"), []byte(gitlinkContent), 0o644); err != nil {
		t.Fatalf("write gitlink: %v", err)
	}
	if err := WriteAijailConfig(wtDir, nil); err != nil {
		t.Fatalf("WriteAijailConfig: %v", err)
	}
	raw, _ := os.ReadFile(filepath.Join(wtDir, ".ai-jail"))
	expected := filepath.Join(repoRoot, ".git")
	if !strings.Contains(string(raw), expected) {
		t.Errorf("rw_maps missing resolved gitlink target %s: %q", expected, string(raw))
	}
}

func TestRemoveAijailConfig_Idempotent(t *testing.T) {
	dir := t.TempDir()
	if err := RemoveAijailConfig(dir); err != nil {
		t.Errorf("RemoveAijailConfig on missing file: %v", err)
	}
	_ = WriteAijailConfig(dir, nil)
	if err := RemoveAijailConfig(dir); err != nil {
		t.Errorf("RemoveAijailConfig: %v", err)
	}
	if _, err := os.Stat(filepath.Join(dir, ".ai-jail")); !os.IsNotExist(err) {
		t.Error("file not removed")
	}
}
