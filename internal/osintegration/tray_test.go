package osintegration

import (
	"context"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

// fakeTrayItem captures clicked channel; tests push to clickCh to simulate clicks.
type fakeTrayItem struct {
	title   string
	tooltip string
	clickCh chan struct{}
}

func newFakeTrayItem(title, tooltip string) *fakeTrayItem {
	return &fakeTrayItem{title: title, tooltip: tooltip, clickCh: make(chan struct{}, 16)}
}

func (f *fakeTrayItem) Clicked() <-chan struct{} { return f.clickCh }

// fakeTrayLib captures calls + holds menu items in insertion order.
type fakeTrayLib struct {
	mu         sync.Mutex
	iconBytes  []byte
	tooltip    string
	items      []*fakeTrayItem
	separators int
	quitCalled atomic.Bool
}

func (f *fakeTrayLib) SetIcon(b []byte) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.iconBytes = b
}
func (f *fakeTrayLib) SetTooltip(t string) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.tooltip = t
}
func (f *fakeTrayLib) AddMenuItem(title, tooltip string) trayItem {
	f.mu.Lock()
	defer f.mu.Unlock()
	it := newFakeTrayItem(title, tooltip)
	f.items = append(f.items, it)
	return it
}
func (f *fakeTrayLib) AddSeparator() {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.separators++
}
func (f *fakeTrayLib) Quit() { f.quitCalled.Store(true) }

func (f *fakeTrayLib) ItemByTitle(title string) *fakeTrayItem {
	f.mu.Lock()
	defer f.mu.Unlock()
	for _, it := range f.items {
		if it.title == title {
			return it
		}
	}
	return nil
}

// Accessors for test assertions — guarded by f.mu to avoid -race warnings
// when the menuLoop goroutine is concurrently writing/reading state via
// SetIcon/SetTooltip/AddMenuItem.
func (f *fakeTrayLib) Tooltip() string {
	f.mu.Lock()
	defer f.mu.Unlock()
	return f.tooltip
}

func (f *fakeTrayLib) IconBytes() []byte {
	f.mu.Lock()
	defer f.mu.Unlock()
	return f.iconBytes
}

func (f *fakeTrayLib) Separators() int {
	f.mu.Lock()
	defer f.mu.Unlock()
	return f.separators
}

func (f *fakeTrayLib) ItemTitles() []string {
	f.mu.Lock()
	defer f.mu.Unlock()
	titles := make([]string, len(f.items))
	for i, it := range f.items {
		titles[i] = it.title
	}
	return titles
}

// fakeTrayFactory holds wires to inspect after Start.
type fakeTrayFactory struct {
	mu      sync.Mutex
	lib     *fakeTrayLib
	onReady func()
	onExit  func()
	started atomic.Bool
	ended   atomic.Bool
}

func newFakeTrayFactory() *fakeTrayFactory { return &fakeTrayFactory{lib: &fakeTrayLib{}} }

func (f *fakeTrayFactory) Make() trayFactory {
	return func(onReady, onExit func()) (trayLib, func(), func()) {
		f.mu.Lock()
		defer f.mu.Unlock()
		f.onReady = onReady
		f.onExit = onExit
		start := func() {
			f.started.Store(true)
			if onReady != nil {
				onReady() // sync invocation: mirrors fyne.io/systray's nativeStart
			}
		}
		end := func() {
			f.ended.Store(true)
			if onExit != nil {
				onExit() // mirrors nativeEnd → runSystrayExit → onExit
			}
		}
		return f.lib, start, end
	}
}

// TestTrayController_StartWiresMenuItems asserts icon, tooltip, two menu items, separator.
func TestTrayController_StartWiresMenuItems(t *testing.T) {
	fact := newFakeTrayFactory()
	ctl := NewTrayControllerForTest(func() {}, func() {}, fact.Make())
	ctl.Start(context.Background())

	if !fact.started.Load() {
		t.Fatal("start() never called")
	}
	if len(fact.lib.IconBytes()) == 0 {
		t.Error("SetIcon not called or empty")
	}
	if got := fact.lib.Tooltip(); got != "J-arvis" {
		t.Errorf("SetTooltip = %q, want %q", got, "J-arvis")
	}
	titles := fact.lib.ItemTitles()
	if len(titles) != 2 {
		t.Fatalf("menu items = %d, want 2", len(titles))
	}
	if titles[0] != "Mostrar janela" {
		t.Errorf("items[0] = %q, want %q", titles[0], "Mostrar janela")
	}
	if titles[1] != "Quit" {
		t.Errorf("items[1] = %q, want %q", titles[1], "Quit")
	}
	if got := fact.lib.Separators(); got != 1 {
		t.Errorf("separators = %d, want 1", got)
	}
}

// Suppress "imported and not used" for time during TDD red phase — used by 5.2/5.3.
var _ = time.Now
