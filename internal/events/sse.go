package events

import (
	"encoding/json"
	"net/http"
	"sync"
)

type sseEnvelope struct {
	Name    string `json:"name"`
	Payload any    `json:"payload"`
}

// SSEEmitter broadcasts bus events to connected /api/events clients.
// Implements Emitter. A client whose buffer fills (slow consumer) is
// dropped rather than blocking Emit — producers run on hot paths
// (PTY output, hook handlers). EventSource auto-reconnects, so a
// dropped client recovers on its own and React Query re-syncs state.
type SSEEmitter struct {
	mu      sync.Mutex
	clients map[chan []byte]struct{}
}

func NewSSEEmitter() *SSEEmitter {
	return &SSEEmitter{clients: map[chan []byte]struct{}{}}
}

func (e *SSEEmitter) Emit(name string, payload any) {
	data, err := json.Marshal(sseEnvelope{Name: name, Payload: payload})
	if err != nil {
		return
	}
	e.mu.Lock()
	defer e.mu.Unlock()
	for ch := range e.clients {
		select {
		case ch <- data:
		default: // full buffer = slow consumer; drop it
			delete(e.clients, ch)
			close(ch)
		}
	}
}

// ClientCount exists for tests and the health snapshot; not load-bearing.
func (e *SSEEmitter) ClientCount() int {
	e.mu.Lock()
	defer e.mu.Unlock()
	return len(e.clients)
}

func (e *SSEEmitter) subscribe() chan []byte {
	ch := make(chan []byte, 1024)
	e.mu.Lock()
	e.clients[ch] = struct{}{}
	e.mu.Unlock()
	return ch
}

func (e *SSEEmitter) unsubscribe(ch chan []byte) {
	e.mu.Lock()
	defer e.mu.Unlock()
	if _, ok := e.clients[ch]; ok {
		delete(e.clients, ch)
		close(ch)
	}
}

func (e *SSEEmitter) Handler() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		fl, ok := w.(http.Flusher)
		if !ok {
			http.Error(w, "streaming unsupported", http.StatusInternalServerError)
			return
		}
		w.Header().Set("Content-Type", "text/event-stream")
		w.Header().Set("Cache-Control", "no-cache")
		ch := e.subscribe()
		defer e.unsubscribe(ch)
		w.WriteHeader(http.StatusOK)
		fl.Flush()
		for {
			select {
			case <-r.Context().Done():
				return
			case data, open := <-ch:
				if !open { // dropped by Emit (slow consumer)
					return
				}
				_, _ = w.Write([]byte("data: "))
				_, _ = w.Write(data)
				_, _ = w.Write([]byte("\n\n"))
				fl.Flush()
			}
		}
	})
}
