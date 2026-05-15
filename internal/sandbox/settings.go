package sandbox

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

const gitignoreLine = ".claude/settings.json"

// WriteSettings creates <worktreePath>/.claude/settings.json with hook entries
// that POST to baseURL/api/hooks/{event}/{token}. Overwrites any prior file.
func WriteSettings(worktreePath, baseURL, token string) error {
	hook := func(event, terminator string) any {
		return map[string]any{
			"matcher": "*",
			"hooks": []any{
				map[string]any{
					"type": "command",
					"command": fmt.Sprintf(
						"curl -sS -X POST '%s/api/hooks/%s/%s' --data-binary @-%s",
						baseURL, event, token, terminator,
					),
				},
			},
		}
	}
	payload := map[string]any{
		"hooks": map[string]any{
			"Notification": []any{hook("Notification", "")},
			"PreToolUse":   []any{hook("PreToolUse", "; exit 0")},
			"Stop":         []any{hook("Stop", "")},
		},
	}
	target := filepath.Join(worktreePath, ".claude", "settings.json")
	if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
		return fmt.Errorf("mkdir .claude: %w", err)
	}
	body, err := json.MarshalIndent(payload, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal settings: %w", err)
	}
	return os.WriteFile(target, body, 0o600)
}

// RemoveSettings removes <worktreePath>/.claude/settings.json. Missing file
// is not an error (idempotent).
func RemoveSettings(worktreePath string) error {
	target := filepath.Join(worktreePath, ".claude", "settings.json")
	if err := os.Remove(target); err != nil && !os.IsNotExist(err) {
		return err
	}
	return nil
}

// EnsureGitignore appends `.claude/settings.json` to <worktreePath>/.gitignore
// if not already present. Idempotent. Preserves existing content.
func EnsureGitignore(worktreePath string) error {
	path := filepath.Join(worktreePath, ".gitignore")
	existing := ""
	if raw, err := os.ReadFile(path); err == nil {
		existing = string(raw)
	} else if !os.IsNotExist(err) {
		return err
	}
	for _, line := range strings.Split(existing, "\n") {
		if line == gitignoreLine {
			return nil
		}
	}
	suffix := ""
	if existing != "" && !strings.HasSuffix(existing, "\n") {
		suffix = "\n"
	}
	return os.WriteFile(path, []byte(existing+suffix+gitignoreLine+"\n"), 0o644)
}
