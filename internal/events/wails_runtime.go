package events

import (
	"context"

	"github.com/wailsapp/wails/v2/pkg/runtime"
)

// WailsEmitter forwards events to the Wails runtime so the JS layer
// can subscribe via runtime.EventsOn.
type WailsEmitter struct {
	ctx context.Context
}

func NewWailsEmitter(ctx context.Context) *WailsEmitter {
	return &WailsEmitter{ctx: ctx}
}

func (e *WailsEmitter) Emit(name string, payload any) {
	runtime.EventsEmit(e.ctx, name, payload)
}
