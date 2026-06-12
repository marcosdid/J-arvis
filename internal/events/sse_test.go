package events

import (
	"bufio"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestSSEEmitterDeliversEnvelope(t *testing.T) {
	e := NewSSEEmitter()
	srv := httptest.NewServer(e.Handler())
	defer srv.Close()

	resp, err := srv.Client().Get(srv.URL)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if ct := resp.Header.Get("Content-Type"); ct != "text/event-stream" {
		t.Fatalf("content-type: %s", ct)
	}

	// Subscribe races the Emit below — poll until the client is registered.
	deadline := time.Now().Add(2 * time.Second)
	for e.ClientCount() == 0 {
		if time.Now().After(deadline) {
			t.Fatal("client never registered")
		}
		time.Sleep(5 * time.Millisecond)
	}

	e.Emit("task.created", map[string]string{"id": "t1"})

	reader := bufio.NewReader(resp.Body)
	line, err := reader.ReadString('\n')
	if err != nil {
		t.Fatal(err)
	}
	want := `data: {"name":"task.created","payload":{"id":"t1"}}`
	if strings.TrimSpace(line) != want {
		t.Fatalf("got %q want %q", strings.TrimSpace(line), want)
	}
}

func TestSSEEmitterSlowClientDoesNotBlockEmit(t *testing.T) {
	e := NewSSEEmitter()
	// Register a client directly and never drain it.
	ch := e.subscribe()
	_ = ch

	done := make(chan struct{})
	go func() {
		for i := 0; i < 5000; i++ { // > buffer size
			e.Emit("task.updated", map[string]int{"i": i})
		}
		close(done)
	}()
	select {
	case <-done:
		// slow client was dropped instead of blocking the emitter
	case <-time.After(3 * time.Second):
		t.Fatal("Emit blocked on slow client")
	}
	if e.ClientCount() != 0 {
		t.Fatalf("slow client should have been dropped, count=%d", e.ClientCount())
	}
}
