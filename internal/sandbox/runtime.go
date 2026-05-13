package sandbox

import (
	"context"
	"errors"
	"fmt"
	"os/exec"
	"syscall"
)

// RuntimeSpec is the input to Spawn.
type RuntimeSpec struct {
	Cwd      string
	Terminal string
}

// Handle identifies a spawned subprocess.
type Handle struct {
	PID int
}

// Runtime is the seam between core/sessions and the actual subprocess.
type Runtime interface {
	Spawn(ctx context.Context, spec RuntimeSpec) (Handle, error)
	Kill(ctx context.Context, h Handle) error
}

// AijailRuntime spawns `<terminal-prefix> ai-jail` (no args; ai-jail reads
// .ai-jail in cwd). Tests may override BuildArgv to bypass terminal wrapping.
type AijailRuntime struct {
	BuildArgv func(spec RuntimeSpec) []string
}

func NewAijailRuntime() *AijailRuntime { return &AijailRuntime{} }

// Spawn forks the configured argv. Notes:
//   - We deliberately use exec.Command (NOT exec.CommandContext). CommandContext
//     registers a Go-side goroutine that calls Process.Kill() when ctx is
//     cancelled — but we Release the process below to avoid zombie reaping.
//     The combination is a classic TOCTOU on PID: after Release + ctx.Done(),
//     the goroutine sends SIGKILL via the original PID, which may have been
//     reused by an unrelated process (potentially a critical system process
//     under heavy load). We avoid the trap entirely by not wiring ctx here.
//   - The ctx parameter is preserved on the interface for future use (e.g.
//     a richer runtime that watches ctx in its own controlled fashion); it
//     is intentionally unused in this implementation.
//   - Release prevents zombie accumulation: we never call Wait, so the OS
//     reaps the child once we detach.
func (r *AijailRuntime) Spawn(_ context.Context, spec RuntimeSpec) (Handle, error) {
	build := r.BuildArgv
	if build == nil {
		build = func(s RuntimeSpec) []string {
			return BuildTerminalCommand(s.Terminal, []string{"ai-jail"})
		}
	}
	argv := build(spec)
	if len(argv) == 0 {
		return Handle{}, errors.New("runtime: empty argv from BuildArgv")
	}
	cmd := exec.Command(argv[0], argv[1:]...) //nolint:gosec // argv built from internal config
	cmd.Dir = spec.Cwd
	if err := cmd.Start(); err != nil {
		return Handle{}, fmt.Errorf("spawn %s: %w", argv[0], err)
	}
	_ = cmd.Process.Release()
	return Handle{PID: cmd.Process.Pid}, nil
}

// Kill sends SIGTERM to the given handle's PID. ESRCH (no such process) is
// idempotent success. Guards against PID <= 0 to prevent the kill(2)
// process-group / kill-all-you-own semantics from firing on a zero-value or
// negative Handle.
func (r *AijailRuntime) Kill(_ context.Context, h Handle) error {
	if h.PID <= 0 {
		return nil
	}
	if err := syscall.Kill(h.PID, syscall.SIGTERM); err != nil {
		if errors.Is(err, syscall.ESRCH) {
			return nil
		}
		return fmt.Errorf("kill pid %d: %w", h.PID, err)
	}
	return nil
}
