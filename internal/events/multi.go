package events

// MultiEmitter fans one Emit out to several emitters. F11.1 transition:
// Wails events and SSE run in parallel until F11.2 removes the Wails leg.
type MultiEmitter []Emitter

func (m MultiEmitter) Emit(name string, payload any) {
	for _, e := range m {
		if e != nil {
			e.Emit(name, payload)
		}
	}
}
