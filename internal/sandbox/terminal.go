package sandbox

import (
	"errors"
	"fmt"
	"os"
	"os/exec"
)

// ErrNoTerminal is returned by DetectTerminal when neither JARVIS_TERMINAL
// resolves to a supported terminal nor any terminal in terminalPriority is
// found in PATH.
var ErrNoTerminal = errors.New("no supported terminal emulator found in PATH")

// terminalPriority lists terminals in detection order. First found in PATH
// wins when JARVIS_TERMINAL is unset.
var terminalPriority = []string{
	"gnome-terminal", "konsole", "xfce4-terminal", "kitty",
	"alacritty", "foot", "tilix", "terminator", "xterm",
}

// terminalPrefixes maps each supported terminal to its argv prefix that
// precedes the inner command.
var terminalPrefixes = map[string][]string{
	"gnome-terminal": {"gnome-terminal", "--"},
	"konsole":        {"konsole", "-e"},
	"xfce4-terminal": {"xfce4-terminal", "-x"},
	"kitty":          {"kitty"},
	"alacritty":      {"alacritty", "-e"},
	"foot":           {"foot"},
	"tilix":          {"tilix", "--"},
	"terminator":     {"terminator", "-x"},
	"xterm":          {"xterm", "-e"},
}

// DetectTerminal honors JARVIS_TERMINAL env override; otherwise scans PATH in
// terminalPriority order.
func DetectTerminal() (string, error) {
	if override := os.Getenv("JARVIS_TERMINAL"); override != "" {
		if _, ok := terminalPrefixes[override]; !ok {
			return "", fmt.Errorf("JARVIS_TERMINAL=%q is not a supported terminal", override)
		}
		return override, nil
	}
	for _, name := range terminalPriority {
		if _, err := exec.LookPath(name); err == nil {
			return name, nil
		}
	}
	return "", ErrNoTerminal
}

// BuildTerminalCommand wraps inner argv with the terminal's required prefix.
func BuildTerminalCommand(terminal string, inner []string) []string {
	prefix := terminalPrefixes[terminal]
	out := make([]string, 0, len(prefix)+len(inner))
	out = append(out, prefix...)
	out = append(out, inner...)
	return out
}
