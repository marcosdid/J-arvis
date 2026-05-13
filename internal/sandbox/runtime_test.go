package sandbox

import (
	"context"
	"testing"
)

// runtime_test.go covers the pure-Go surface of AijailRuntime: BuildArgv
// defaults and the Kill guards against unsafe PIDs. The subprocess Spawn/Kill
// round-trip lives in runtime_integration_test.go behind the `integration`
// build tag — it forks a real shell subprocess and must not run in default
// `go test` invocations.

func TestAijailRuntime_DefaultArgv_ProducesTerminalWrappedCommand(t *testing.T) {
	// The default BuildArgv builds `BuildTerminalCommand(terminal, ["ai-jail"])`.
	// We exercise BuildTerminalCommand directly to avoid forking.
	got := BuildTerminalCommand("kitty", []string{"ai-jail"})
	want := []string{"kitty", "ai-jail"}
	if len(got) != len(want) {
		t.Fatalf("argv len: got %d, want %d (%v vs %v)", len(got), len(want), got, want)
	}
	for i := range got {
		if got[i] != want[i] {
			t.Errorf("argv[%d]: got %q, want %q", i, got[i], want[i])
		}
	}
}

func TestAijailRuntime_Kill_ZeroPID_IsNoop(t *testing.T) {
	// A zero-value Handle{} must NEVER reach syscall.Kill: kill(0, sig) signals
	// every process in the calling process's group, which would terminate the
	// test binary itself (and potentially anything sharing the pgrp).
	rt := NewAijailRuntime()
	if err := rt.Kill(context.Background(), Handle{}); err != nil {
		t.Errorf("Kill of zero-value Handle should be no-op, got %v", err)
	}
}

func TestAijailRuntime_Kill_NegativePID_IsNoop(t *testing.T) {
	// kill(-1, sig) signals EVERY process the caller has permission to signal.
	// kill(-N, sig) for N > 1 signals process group N. Both are dangerous.
	// The Kill guard short-circuits on PID <= 0 to prevent accidents from
	// callers that pass a misconfigured Handle.
	rt := NewAijailRuntime()
	if err := rt.Kill(context.Background(), Handle{PID: -1}); err != nil {
		t.Errorf("Kill of PID=-1 should be no-op, got %v", err)
	}
	if err := rt.Kill(context.Background(), Handle{PID: -42}); err != nil {
		t.Errorf("Kill of PID=-42 should be no-op, got %v", err)
	}
}
