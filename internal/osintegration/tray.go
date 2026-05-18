package osintegration

import (
	"context"
	"sync/atomic"
)

// trayItem is the minimal interface a menu item must satisfy: expose a
// Clicked channel that fires when the user clicks the entry.
type trayItem interface {
	Clicked() <-chan struct{}
}

// trayLib abstracts the subset of fyne.io/systray we use. Implemented by
// realTrayLib (Task 7.1) in production and by fakeTrayLib in tests.
type trayLib interface {
	SetIcon(data []byte)
	SetTooltip(t string)
	AddMenuItem(title, tooltip string) trayItem
	AddSeparator()
	Quit()
}

// trayFactory registers callbacks with the underlying lib and returns
// the lib instance plus the (start, end) callbacks the caller must
// invoke at the right lifecycle points.
//
// The contract for the `end` callback: it MUST invoke onExit. In
// production this happens via fyne.io/systray's nativeEnd → runSystrayExit
// cascade. In tests, fakeTrayFactory's end must call onExit explicitly so
// TestTrayController_OnExit* tests work.
type trayFactory func(onReady, onExit func()) (lib trayLib, start, end func())

// TrayController owns the tray lifecycle. Instance state (quitInProgress)
// keeps tests isolated and supports concurrent quit clicks correctly.
type TrayController struct {
	factory        trayFactory
	onShow         func()
	onQuit         func()
	lib            trayLib
	start, end     func()
	quitInProgress atomic.Bool
}

// NewTrayController constructs a controller with the production factory.
// Tests use NewTrayControllerForTest to inject a fake factory.
func NewTrayController(onShow, onQuit func()) *TrayController {
	return &TrayController{factory: realTrayFactory, onShow: onShow, onQuit: onQuit}
}

// NewTrayControllerForTest is exposed for tests that need a custom factory.
func NewTrayControllerForTest(onShow, onQuit func(), factory trayFactory) *TrayController {
	return &TrayController{factory: factory, onShow: onShow, onQuit: onQuit}
}

// realTrayFactory wraps fyne.io/systray. Stub for now — Task 7.1 fills it in.
var realTrayFactory trayFactory = func(onReady, onExit func()) (trayLib, func(), func()) {
	panic("realTrayFactory not yet implemented (lands in Task 7.1)")
}

// Start placeholder — Task 5 wires it. Splitting the skeleton from the
// behavior lets Stage 4 land alone (no half-built logic in a committed file).
func (t *TrayController) Start(ctx context.Context) {
	// Implementation in Task 5.1
	_ = ctx
}

// Stop placeholder — Task 6 wires it.
func (t *TrayController) Stop() {
	// Implementation in Task 6.x
}
