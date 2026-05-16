package events

import "sync"

type Emitter interface {
	Emit(name string, payload any)
}

// LazyEmitter defers emit calls until an underlying Emitter is available.
// This is needed because Wails' runtime context is only valid after
// OnStartup fires — but Bind() runs earlier, so API constructors receive
// a LazyEmitter and resolve the real emitter at emit-time.
type LazyEmitter struct {
	Resolve func() Emitter
}

func (l *LazyEmitter) Emit(name string, payload any) {
	if l.Resolve == nil {
		return
	}
	if e := l.Resolve(); e != nil {
		e.Emit(name, payload)
	}
}

// FakeEmitter records emitted events for tests. Thread-safe — production
// code emits from background goroutines (watchdogs, hook handlers) and
// tests assert from the foreground.
type FakeEmitter struct {
	mu    sync.Mutex
	Calls []EmitCall
}

type EmitCall struct {
	Name    string
	Payload any
}

func (f *FakeEmitter) Emit(name string, payload any) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.Calls = append(f.Calls, EmitCall{Name: name, Payload: payload})
}
