package hooks

import (
	"errors"
	"fmt"
)

// ErrInvalidHookPayload signals that a claude hook payload is missing required
// fields or has wrong types. Hook routes return HTTP 422 in this case.
var ErrInvalidHookPayload = errors.New("invalid hook payload")

// Session status constants. These match Python's SessionStatus StrEnum values
// and the CHECK constraint in the sessions table migration.
const (
	StatusExecuting        = "executing"
	StatusAwaitingResponse = "awaiting_response"
	StatusIdle             = "idle"
	StatusError            = "error"
	StatusDone             = "done"
)

// ParseNotification: claude says it produced a notification → user is awaited.
func ParseNotification(payload map[string]any) (string, error) {
	if _, ok := payload["message"]; !ok {
		return "", fmt.Errorf("ParseNotification: missing 'message': %w", ErrInvalidHookPayload)
	}
	return StatusAwaitingResponse, nil
}

// ParseStop: claude finished its turn → idle.
func ParseStop(_ map[string]any) (string, error) {
	return StatusIdle, nil
}

// ParsePreToolUse: claude is about to invoke a tool. Returns the tool name.
func ParsePreToolUse(payload map[string]any) (string, error) {
	name, ok := payload["tool_name"].(string)
	if !ok || name == "" {
		return "", fmt.Errorf("ParsePreToolUse: missing or non-string 'tool_name': %w", ErrInvalidHookPayload)
	}
	return name, nil
}
