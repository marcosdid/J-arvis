package sandbox

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// TestWriteMasterSettings_WritesMcpJsonAtRoot verifies that the MCP server
// config lives in .mcp.json at the project root — that's where Claude Code
// looks for project-scoped servers. Putting `mcpServers` inside
// .claude/settings.json (the previous behavior) is ignored.
//
// Spec: https://code.claude.com/docs/en/mcp#project-scope
func TestWriteMasterSettings_WritesMcpJsonAtRoot(t *testing.T) {
	dir := t.TempDir()
	if err := WriteMasterSettings(dir, "http://127.0.0.1:42037", "tok-abc"); err != nil {
		t.Fatalf("WriteMasterSettings: %v", err)
	}
	data, err := os.ReadFile(filepath.Join(dir, ".mcp.json"))
	if err != nil {
		t.Fatalf("read .mcp.json: %v", err)
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
	if jarvis["type"] != "http" {
		t.Errorf("type=%q, want 'http'", jarvis["type"])
	}
	if jarvis["url"] != "http://127.0.0.1:42037/api/mcp" {
		t.Errorf("url=%q, want suffix /api/mcp", jarvis["url"])
	}
	headers := jarvis["headers"].(map[string]any)
	if headers["Authorization"] != "Bearer tok-abc" {
		t.Errorf("Authorization=%q, want 'Bearer tok-abc'", headers["Authorization"])
	}
}

// TestWriteMasterSettings_AutoApprovesProjectMcpServers verifies that
// .claude/settings.json contains enableAllProjectMcpServers=true, otherwise
// the master Claude Code subprocess would prompt interactively before using
// the server — there's no human to click "approve" on a headless session.
//
// Spec: https://code.claude.com/docs/en/settings#enableAllProjectMcpServers
func TestWriteMasterSettings_AutoApprovesProjectMcpServers(t *testing.T) {
	dir := t.TempDir()
	if err := WriteMasterSettings(dir, "http://127.0.0.1:1", "t"); err != nil {
		t.Fatalf("WriteMasterSettings: %v", err)
	}
	data, err := os.ReadFile(filepath.Join(dir, ".claude", "settings.json"))
	if err != nil {
		t.Fatalf("read settings.json: %v", err)
	}
	var parsed map[string]any
	if err := json.Unmarshal(data, &parsed); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if parsed["enableAllProjectMcpServers"] != true {
		t.Errorf("enableAllProjectMcpServers=%v, want true (contents: %s)", parsed["enableAllProjectMcpServers"], string(data))
	}
}

// TestWriteMasterSettings_McpJsonMode0600 — .mcp.json contains the bearer
// token, so it must not be world-readable.
func TestWriteMasterSettings_McpJsonMode0600(t *testing.T) {
	dir := t.TempDir()
	_ = WriteMasterSettings(dir, "u", "t")
	info, err := os.Stat(filepath.Join(dir, ".mcp.json"))
	if err != nil {
		t.Fatalf("stat: %v", err)
	}
	if info.Mode().Perm() != 0o600 {
		t.Errorf(".mcp.json mode=%o, want 0600", info.Mode().Perm())
	}
}

// TestWriteMasterSettings_CreatesClaudeDir — .claude/ must exist for
// settings.json to land somewhere.
func TestWriteMasterSettings_CreatesClaudeDir(t *testing.T) {
	dir := t.TempDir()
	if err := WriteMasterSettings(dir, "u", "t"); err != nil {
		t.Fatalf("WriteMasterSettings: %v", err)
	}
	if _, err := os.Stat(filepath.Join(dir, ".claude")); err != nil {
		t.Errorf(".claude dir not created: %v", err)
	}
}

// TestWriteMasterSettings_NoHooksBlock — master session is bare; if .claude/
// settings.json ever contains a hooks block, something else is leaking in.
func TestWriteMasterSettings_NoHooksBlock(t *testing.T) {
	dir := t.TempDir()
	_ = WriteMasterSettings(dir, "u", "t")
	data, _ := os.ReadFile(filepath.Join(dir, ".claude", "settings.json"))
	if strings.Contains(string(data), "\"hooks\"") {
		t.Errorf("master settings has hooks block: %s", string(data))
	}
}
