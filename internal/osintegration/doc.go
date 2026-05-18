// Package osintegration implements the OS-resident behaviors of J-arvis
// on Linux: system tray icon (fyne.io/systray), CLI flag parsing, and
// the D-Bus session bus probe used to gate Wails' SingleInstanceLock +
// HideWindowOnClose.
//
// Spec: docs/superpowers/specs/2026-05-17-f10.7-resident-app-design.md
//
// Public surface:
//   - PreflightOK() bool        — display + D-Bus probe
//   - CLIFlags, ParseFlags      — parse --focus from os.Args
//   - TrayController            — Start/Stop owned by main.go
//   - TrayIconPNG               — embedded asset
//
// The tray library (fyne.io/systray) is accessed through a trayFactory
// seam so tests can drive the lifecycle without a real display.
package osintegration
