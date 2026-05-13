package api

import (
	"context"
	"testing"
)

func TestHealthAPI_Snapshot(t *testing.T) {
	h := NewHealthAPI()
	snap, err := h.Snapshot(context.Background())
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if snap.AppVersion == "" {
		t.Error("AppVersion should not be empty")
	}
	if snap.Uptime < 0 {
		t.Errorf("Uptime should be >= 0, got %d", snap.Uptime)
	}
}
