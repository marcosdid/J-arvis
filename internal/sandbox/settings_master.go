package sandbox

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

// WriteMasterSettings writes two files to the master session's working dir:
//
//  1. <cwd>/.mcp.json — project-scoped MCP server config that Claude Code
//     discovers automatically on startup. Mode 0600 because it contains the
//     bearer token.
//
//  2. <cwd>/.claude/settings.json — turns on enableAllProjectMcpServers so
//     the master subprocess auto-approves the .mcp.json entries without an
//     interactive prompt. Mode 0644 (no secrets).
//
// References:
//   - https://code.claude.com/docs/en/mcp#project-scope
//   - https://code.claude.com/docs/en/settings#enableAllProjectMcpServers
func WriteMasterSettings(cwd, mcpBaseURL, bearerToken string) error {
	if err := writeMcpJSON(cwd, mcpBaseURL, bearerToken); err != nil {
		return err
	}
	return writeClaudeSettings(cwd)
}

func writeMcpJSON(cwd, mcpBaseURL, bearerToken string) error {
	payload := map[string]any{
		"mcpServers": map[string]any{
			"j-arvis-master": map[string]any{
				"type": "http",
				"url":  mcpBaseURL + "/api/mcp",
				"headers": map[string]string{
					"Authorization": "Bearer " + bearerToken,
				},
			},
		},
	}
	data, err := json.MarshalIndent(payload, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal .mcp.json: %w", err)
	}
	return os.WriteFile(filepath.Join(cwd, ".mcp.json"), data, 0o600)
}

func writeClaudeSettings(cwd string) error {
	dir := filepath.Join(cwd, ".claude")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return fmt.Errorf("mkdir .claude: %w", err)
	}
	payload := map[string]any{
		"enableAllProjectMcpServers": true,
	}
	data, err := json.MarshalIndent(payload, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal settings.json: %w", err)
	}
	return os.WriteFile(filepath.Join(dir, "settings.json"), data, 0o644)
}
