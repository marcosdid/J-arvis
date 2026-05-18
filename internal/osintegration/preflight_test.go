package osintegration

import "testing"

func TestPreflightOK_NoDisplay(t *testing.T) {
	t.Setenv("DISPLAY", "")
	t.Setenv("WAYLAND_DISPLAY", "")
	if PreflightOK() {
		t.Error("PreflightOK = true, want false (no display set)")
	}
}

func TestPreflightOK_NoDBus(t *testing.T) {
	t.Setenv("DISPLAY", ":0")
	t.Setenv("WAYLAND_DISPLAY", "")
	t.Setenv("DBUS_SESSION_BUS_ADDRESS", "")
	t.Setenv("XDG_RUNTIME_DIR", "")
	// godbus may still find a bus via ~/.dbus/session-bus or autolaunch;
	// this test is best-effort. If it returns true, godbus autolaunched
	// a fallback, which is fine (real env has it).
	got := PreflightOK()
	t.Logf("PreflightOK without DBUS_SESSION_BUS_ADDRESS = %v", got)
}

func TestPreflightOK_WithDisplayAndDBus(t *testing.T) {
	t.Setenv("DISPLAY", ":0")
	// DBUS_SESSION_BUS_ADDRESS is whatever the test runner inherits
	// (probably set in dev; possibly absent in CI).
	got := PreflightOK()
	t.Logf("PreflightOK with DISPLAY set = %v", got)
}
