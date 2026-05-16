package sandbox

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

// WriteMasterSettings writes <cwd>/.claude/settings.json with the mcpServers
// block pointing at the J-arvis internal MCP endpoint. Used by master session
// only — task sessions use WriteSettings (hooks block).
//
// File mode is 0600 because the JSON contains the bearer token. The token is
// regenerated on every daemon boot, so leaking the file is bounded in time,
// but there's zero reason for it to be world-readable.
func WriteMasterSettings(cwd, mcpBaseURL, bearerToken string) error {
	dir := filepath.Join(cwd, ".claude")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return fmt.Errorf("mkdir .claude: %w", err)
	}
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
		return fmt.Errorf("marshal master settings: %w", err)
	}
	return os.WriteFile(filepath.Join(dir, "settings.json"), data, 0o600)
}
