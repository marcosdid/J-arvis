package sandbox

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestWriteSettings_WritesValidJSON(t *testing.T) {
	dir := t.TempDir()
	if err := WriteSettings(dir, "http://127.0.0.1:42037", "abcd1234"); err != nil {
		t.Fatalf("WriteSettings: %v", err)
	}
	raw, err := os.ReadFile(filepath.Join(dir, ".claude", "settings.json"))
	if err != nil {
		t.Fatalf("read settings: %v", err)
	}
	var got map[string]any
	if err := json.Unmarshal(raw, &got); err != nil {
		t.Fatalf("settings.json is not valid JSON: %v", err)
	}
	hooks, _ := got["hooks"].(map[string]any)
	if hooks == nil {
		t.Fatal("missing hooks key")
	}
	for _, event := range []string{"Notification", "PreToolUse", "Stop"} {
		if _, ok := hooks[event]; !ok {
			t.Errorf("missing hook event %s", event)
		}
	}
	s := string(raw)
	if !strings.Contains(s, "http://127.0.0.1:42037/api/hooks/Notification/abcd1234") {
		t.Error("Notification URL not interpolated")
	}
	if !strings.Contains(s, "; exit 0") {
		t.Error("PreToolUse missing '; exit 0' suffix")
	}
}

func TestWriteSettings_CreatesParentDir(t *testing.T) {
	dir := t.TempDir()
	if err := WriteSettings(dir, "http://x", "t"); err != nil {
		t.Fatalf("WriteSettings: %v", err)
	}
	if _, err := os.Stat(filepath.Join(dir, ".claude")); err != nil {
		t.Errorf(".claude dir not created: %v", err)
	}
}

func TestRemoveSettings_Idempotent(t *testing.T) {
	dir := t.TempDir()
	if err := RemoveSettings(dir); err != nil {
		t.Errorf("RemoveSettings on missing file: %v", err)
	}
	_ = WriteSettings(dir, "u", "t")
	if err := RemoveSettings(dir); err != nil {
		t.Errorf("RemoveSettings: %v", err)
	}
	if _, err := os.Stat(filepath.Join(dir, ".claude", "settings.json")); !os.IsNotExist(err) {
		t.Error("settings.json not removed")
	}
}

func TestEnsureGitignore_AppendsLine(t *testing.T) {
	dir := t.TempDir()
	if err := EnsureGitignore(dir); err != nil {
		t.Fatalf("EnsureGitignore: %v", err)
	}
	raw, _ := os.ReadFile(filepath.Join(dir, ".gitignore"))
	if !strings.Contains(string(raw), ".claude/settings.json") {
		t.Errorf("gitignore missing entry: %q", string(raw))
	}
}

func TestEnsureGitignore_Idempotent(t *testing.T) {
	dir := t.TempDir()
	_ = EnsureGitignore(dir)
	_ = EnsureGitignore(dir)
	raw, _ := os.ReadFile(filepath.Join(dir, ".gitignore"))
	if strings.Count(string(raw), ".claude/settings.json") != 1 {
		t.Errorf("gitignore entry duplicated: %q", string(raw))
	}
}

func TestEnsureGitignore_PreservesExistingContent(t *testing.T) {
	dir := t.TempDir()
	gip := filepath.Join(dir, ".gitignore")
	_ = os.WriteFile(gip, []byte("node_modules/\n"), 0o644)
	_ = EnsureGitignore(dir)
	raw, _ := os.ReadFile(gip)
	if !strings.Contains(string(raw), "node_modules/") {
		t.Error("existing gitignore content lost")
	}
}
