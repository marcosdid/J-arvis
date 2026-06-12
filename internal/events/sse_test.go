package events

import (
	"bufio"
	"bytes"
	"log"
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
	e.subscribe()

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

func TestSSEEmitterDropThenUnsubscribeIsSafe(t *testing.T) {
	e := NewSSEEmitter()
	// net/http recovers handler panics and only logs them, so a double
	// close inside the Handler's deferred unsubscribe would keep this
	// test green. Capture the server log to surface it.
	var serverLog bytes.Buffer
	srv := httptest.NewUnstartedServer(e.Handler())
	srv.Config.ErrorLog = log.New(&serverLog, "", 0)
	srv.Start()
	defer srv.Close()

	resp, err := srv.Client().Get(srv.URL)
	if err != nil {
		t.Fatal(err)
	}

	deadline := time.Now().Add(2 * time.Second)
	for e.ClientCount() != 1 {
		if time.Now().After(deadline) {
			t.Fatal("client never registered")
		}
		time.Sleep(5 * time.Millisecond)
	}

	// Never read the body: once kernel TCP buffers fill, the handler
	// blocks writing, the channel backs up past its 1024 slots, and
	// Emit drops the client (delete + close).
	payload := strings.Repeat("x", 4096)
	deadline = time.Now().Add(5 * time.Second)
	for e.ClientCount() != 0 {
		if time.Now().After(deadline) {
			t.Fatal("slow client was never dropped")
		}
		e.Emit("task.updated", map[string]string{"p": payload})
	}

	// Unblock the handler so its deferred unsubscribe runs against the
	// channel Emit already closed; srv.Close waits for it to finish.
	resp.Body.Close()
	srv.Close()

	e.Emit("task.updated", map[string]string{"id": "final"})

	if logged := serverLog.String(); strings.Contains(logged, "panic") {
		t.Fatalf("handler panicked:\n%s", logged)
	}
}
