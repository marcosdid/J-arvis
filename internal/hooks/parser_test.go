package hooks

import (
	"errors"
	"testing"
)

func TestParseNotification_Valid(t *testing.T) {
	payload := map[string]any{"message": "hi from claude"}
	got, err := ParseNotification(payload)
	if err != nil {
		t.Fatalf("ParseNotification: %v", err)
	}
	if got != StatusAwaitingResponse {
		t.Errorf("status: got %q, want %q", got, StatusAwaitingResponse)
	}
}

func TestParseNotification_MissingMessage(t *testing.T) {
	_, err := ParseNotification(map[string]any{"foo": "bar"})
	if !errors.Is(err, ErrInvalidHookPayload) {
		t.Errorf("want ErrInvalidHookPayload, got %v", err)
	}
}

func TestParseStop_AlwaysIdle(t *testing.T) {
	got, err := ParseStop(map[string]any{})
	if err != nil {
		t.Fatalf("ParseStop: %v", err)
	}
	if got != StatusIdle {
		t.Errorf("status: got %q, want %q", got, StatusIdle)
	}
}

func TestParsePreToolUse_Valid(t *testing.T) {
	got, err := ParsePreToolUse(map[string]any{"tool_name": "Read"})
	if err != nil {
		t.Fatalf("ParsePreToolUse: %v", err)
	}
	if got != "Read" {
		t.Errorf("tool: got %q, want Read", got)
	}
}

func TestParsePreToolUse_MissingToolName(t *testing.T) {
	_, err := ParsePreToolUse(map[string]any{})
	if !errors.Is(err, ErrInvalidHookPayload) {
		t.Errorf("want ErrInvalidHookPayload, got %v", err)
	}
}

func TestParsePreToolUse_NonStringToolName(t *testing.T) {
	_, err := ParsePreToolUse(map[string]any{"tool_name": 42})
	if !errors.Is(err, ErrInvalidHookPayload) {
		t.Errorf("want ErrInvalidHookPayload, got %v", err)
	}
}

func TestParsePreToolUse_EmptyToolName(t *testing.T) {
	_, err := ParsePreToolUse(map[string]any{"tool_name": ""})
	if !errors.Is(err, ErrInvalidHookPayload) {
		t.Errorf("empty string should be rejected, got %v", err)
	}
}
