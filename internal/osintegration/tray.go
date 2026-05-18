package osintegration

import (
	"context"
	"sync/atomic"

	"fyne.io/systray"
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

// realTrayItem wraps *systray.MenuItem to satisfy our trayItem interface.
type realTrayItem struct{ inner *systray.MenuItem }

func (r *realTrayItem) Clicked() <-chan struct{} { return r.inner.ClickedCh }

// realTrayLib wraps the fyne.io/systray package-level functions to satisfy trayLib.
type realTrayLib struct{}

func (r *realTrayLib) SetIcon(b []byte)    { systray.SetIcon(b) }
func (r *realTrayLib) SetTooltip(t string) { systray.SetTooltip(t) }
func (r *realTrayLib) AddMenuItem(title, tip string) trayItem {
	return &realTrayItem{inner: systray.AddMenuItem(title, tip)}
}
func (r *realTrayLib) AddSeparator() { systray.AddSeparator() }
func (r *realTrayLib) Quit()         { systray.Quit() }

// realTrayFactory is the production factory. It wraps systray.RunWithExternalLoop:
//   - returns realTrayLib (forwards to the package singleton)
//   - returns (start, end) callbacks that the caller invokes at Wails OnStartup
//     / OnShutdown respectively.
//
// On Linux, start triggers nativeStart (D-Bus connect + StatusNotifierItem
// export); end triggers nativeEnd → runSystrayExit → onExit + systray.Quit().
var realTrayFactory trayFactory = func(onReady, onExit func()) (trayLib, func(), func()) {
	start, end := systray.RunWithExternalLoop(onReady, onExit)
	return &realTrayLib{}, start, end
}

// Start registers tray callbacks via the factory (synchronous, fast — just
// callback registration; no D-Bus/GTK work happens here). It then launches
// t.start() in a goroutine since nativeStart blocks until the lib loop
// finishes.
//
// MUST be called synchronously from Wails OnStartup. Wails calls OnStartup
// and OnShutdown serially on the same main goroutine — so by the time
// OnShutdown can run, all of t.lib/t.start/t.end are already assigned
// (no race on Stop's read).
func (t *TrayController) Start(ctx context.Context) {
	t.lib, t.start, t.end = t.factory(t.makeOnReady(ctx), t.makeOnExit())
	if t.start != nil {
		go t.start()
	}
}

func (t *TrayController) makeOnReady(ctx context.Context) func() {
	return func() {
		t.lib.SetIcon(TrayIconPNG)
		t.lib.SetTooltip("J-arvis")
		mShow := t.lib.AddMenuItem("Mostrar janela", "")
		t.lib.AddSeparator()
		mQuit := t.lib.AddMenuItem("Quit", "Encerrar J-arvis (mata sessions, runs, master)")

		go t.menuLoop(ctx, mShow, mQuit)
	}
}

func (t *TrayController) menuLoop(ctx context.Context, mShow, mQuit trayItem) {
	for {
		select {
		case <-ctx.Done():
			return
		case <-mShow.Clicked():
			t.onShow()
		case <-mQuit.Clicked():
			// STEADY-STATE PATH: user clicked Quit. Win the swap;
			// onExit (which runs at OnShutdown via Stop()) finds
			// quitInProgress=true and no-ops.
			if !t.quitInProgress.Swap(true) {
				t.lib.Quit()
				t.onQuit()
			}
			return
		}
	}
}

func (t *TrayController) makeOnExit() func() {
	return func() {
		// FALLBACK PATH: lib loop ended (only via Stop() in external-loop
		// mode). If steady-state path already swapped (user clicked Quit),
		// this is a no-op. Otherwise we initiate the quit ourselves.
		if !t.quitInProgress.Swap(true) {
			t.onQuit()
		}
	}
}

// Stop tears the tray down deterministically via the lib's `end` function.
// In external-loop mode, this is what triggers nativeEnd → runSystrayExit
// → our onExit. Should be called from Wails OnShutdown (before
// masterSvc.Stop — UI ops sumir antes das domain ops).
func (t *TrayController) Stop() {
	if t.end != nil {
		t.end()
	}
}
