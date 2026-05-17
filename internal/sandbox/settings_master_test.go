package sandbox

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestWriteMasterSettings_WritesValidMcpServersBlock(t *testing.T) {
	dir := t.TempDir()
	if err := WriteMasterSettings(dir, "http://127.0.0.1:42037", "tok-abc"); err != nil {
		t.Fatalf("WriteMasterSettings: %v", err)
	}
	data, err := os.ReadFile(filepath.Join(dir, ".claude", "settings.json"))
	if err != nil {
		t.Fatalf("read: %v", err)
	}
	var parsed map[string]any
	if err := json.Unmarshal(data, &parsed); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	servers, ok := parsed["mcpServers"].(map[string]any)
	if !ok {
		t.Fatalf("no mcpServers block: %s", string(data))
	}
	jarvis, ok := servers["j-arvis-master"].(map[string]any)
	if !ok {
		t.Fatal("no j-arvis-master entry")
	}
	if jarvis["url"] != "http://127.0.0.1:42037/api/mcp" {
		t.Errorf("url=%q, want suffix /api/mcp", jarvis["url"])
	}
	headers := jarvis["headers"].(map[string]any)
	if headers["Authorization"] != "Bearer tok-abc" {
		t.Errorf("Authorization=%q, want 'Bearer tok-abc'", headers["Authorization"])
	}
}

func TestWriteMasterSettings_FileMode0600(t *testing.T) {
	dir := t.TempDir()
	_ = WriteMasterSettings(dir, "u", "t")
	info, err := os.Stat(filepath.Join(dir, ".claude", "settings.json"))
	if err != nil {
		t.Fatalf("stat: %v", err)
	}
	if info.Mode().Perm() != 0o600 {
		t.Errorf("mode=%o, want 0600", info.Mode().Perm())
	}
}

func TestWriteMasterSettings_CreatesClaudeDir(t *testing.T) {
	dir := t.TempDir()
	if err := WriteMasterSettings(dir, "u", "t"); err != nil {
		t.Fatalf("WriteMasterSettings: %v", err)
	}
	if _, err := os.Stat(filepath.Join(dir, ".claude")); err != nil {
		t.Errorf(".claude dir not created: %v", err)
	}
}

func TestWriteMasterSettings_NoHooksBlock(t *testing.T) {
	dir := t.TempDir()
	_ = WriteMasterSettings(dir, "u", "t")
	data, _ := os.ReadFile(filepath.Join(dir, ".claude", "settings.json"))
	if strings.Contains(string(data), "\"hooks\"") {
		t.Errorf("master settings has hooks block (should be mcpServers-only): %s", string(data))
	}
}
