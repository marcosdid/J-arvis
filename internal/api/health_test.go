package api

import (
	"context"
	"testing"
)

func TestHealthAPI_Snapshot_NilProbeDefaultsSandboxFalse(t *testing.T) {
	h := NewHealthAPI(nil)
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
	if snap.SandboxAvailable {
		t.Error("nil probe should default to SandboxAvailable=false")
	}
	if snap.SandboxReason != "" {
		t.Errorf("nil probe should produce empty SandboxReason, got %q", snap.SandboxReason)
	}
}

func TestHealthAPI_Snapshot_ProbeAvailable(t *testing.T) {
	h := NewHealthAPI(func() (bool, string) { return true, "" })
	snap, _ := h.Snapshot(context.Background())
	if !snap.SandboxAvailable {
		t.Error("SandboxAvailable: got false, want true")
	}
	if snap.SandboxReason != "" {
		t.Errorf("SandboxReason: got %q, want empty", snap.SandboxReason)
	}
}

func TestHealthAPI_Snapshot_ProbeUnavailableWithReason(t *testing.T) {
	h := NewHealthAPI(func() (bool, string) { return false, "ai-jail not in PATH" })
	snap, _ := h.Snapshot(context.Background())
	if snap.SandboxAvailable {
		t.Error("SandboxAvailable: got true, want false")
	}
	if snap.SandboxReason != "ai-jail not in PATH" {
		t.Errorf("SandboxReason: got %q", snap.SandboxReason)
	}
}
