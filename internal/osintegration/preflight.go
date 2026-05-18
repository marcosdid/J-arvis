package osintegration

import (
	"os"

	"github.com/godbus/dbus/v5"
)

// PreflightOK reports whether the environment can host a system tray icon
// and a single-instance D-Bus claim. Two checks:
//  1. Display env: $DISPLAY (X11) or $WAYLAND_DISPLAY (Wayland) is set.
//     Catches headless CI + minimal containers.
//  2. D-Bus session bus probe: dbus.SessionBus() connects successfully.
//     Catches misconfigured user sessions.
//
// Returns true only when both pass. main.go uses the result to
// conditionally enable HideWindowOnClose + SingleInstanceLock.
//
// IMPORTANT: do NOT call conn.Close() on the result of SessionBus(). It
// returns the cached *Conn shared across the process via a package-level
// var protected by godbus's sessionBusLck. Closing it forces reconnect in
// every other consumer (including systray's nativeStart) and races with
// concurrent use.
func PreflightOK() bool {
	if os.Getenv("DISPLAY") == "" && os.Getenv("WAYLAND_DISPLAY") == "" {
		return false
	}
	if _, err := dbus.SessionBus(); err != nil {
		return false
	}
	return true
}
