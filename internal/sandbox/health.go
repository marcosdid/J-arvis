package sandbox

import (
	"errors"
	"fmt"
	"os/exec"
)

// SandboxAvailable returns nil iff all sandbox prerequisites are present:
//   - "ai-jail" binary in $PATH
//   - at least one supported terminal emulator in $PATH (or JARVIS_TERMINAL set)
// Otherwise returns a structured error.
func SandboxAvailable() error {
	if _, err := exec.LookPath("ai-jail"); err != nil {
		return fmt.Errorf("ai-jail not found in PATH: %w", err)
	}
	if _, err := DetectTerminal(); err != nil {
		return fmt.Errorf("no terminal emulator available: %w", err)
	}
	return nil
}

// DiagnoseSandbox returns a human-readable explanation suitable for a UI
// tooltip. Returns "" when SandboxAvailable() == nil.
func DiagnoseSandbox() string {
	err := SandboxAvailable()
	if err == nil {
		return ""
	}
	if errors.Is(err, ErrNoTerminal) {
		return "Install a supported terminal emulator (gnome-terminal, konsole, kitty, alacritty, foot, tilix, terminator, xterm, or xfce4-terminal) and restart the app."
	}
	return err.Error()
}
