//go:build integration

package sandbox

import (
	"context"
	"path/filepath"
	"syscall"
	"testing"
	"time"
)

// TestAijailRuntime_SpawnAndKill_FakeBinary exercises a real fork+exec via the
// testdata/fake-aijail.sh fixture. It is GATED BEHIND `//go:build integration`
// because:
//   1. Forking subprocesses interacts with the host kernel; PID-reuse + race
//      detector + heavy workloads have caused unstable behavior in this
//      project's history (see runtime.go Spawn comment).
//   2. Default `go test` should remain fork-free so unit suites run safely on
//      developer machines and CI without external dependencies.
//
// Run only when explicitly opting in:
//   go test -tags=integration ./internal/sandbox/...
func TestAijailRuntime_SpawnAndKill_FakeBinary(t *testing.T) {
	rt := &AijailRuntime{
		BuildArgv: func(spec RuntimeSpec) []string {
			scriptPath, _ := filepath.Abs("testdata/fake-aijail.sh")
			return []string{scriptPath}
		},
	}
	spec := RuntimeSpec{Cwd: t.TempDir()}

	handle, err := rt.Spawn(context.Background(), spec)
	if err != nil {
		t.Fatalf("Spawn: %v", err)
	}
	if handle.PID <= 0 {
		t.Fatalf("PID: got %d, want > 0", handle.PID)
	}

	// Belt-and-suspenders cleanup: ensure the script and any child it spawned
	// are gone even if the test fails partway through. SIGKILL is fine here —
	// we are tearing down a fixture, not exercising graceful shutdown.
	defer func() {
		_ = syscall.Kill(handle.PID, syscall.SIGKILL)
	}()

	time.Sleep(100 * time.Millisecond)

	// signal 0 = existence check (no signal delivered).
	if err := syscall.Kill(handle.PID, 0); err != nil {
		t.Fatalf("process not alive after Spawn: %v", err)
	}

	if err := rt.Kill(context.Background(), handle); err != nil {
		t.Errorf("Kill: %v", err)
	}

	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		if err := syscall.Kill(handle.PID, 0); err != nil {
			return // process gone — success
		}
		time.Sleep(50 * time.Millisecond)
	}
	t.Errorf("process %d still alive after Kill", handle.PID)
}
