package hooks

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"
)

// fakeSessionUpdater records calls in memory.
type fakeSessionUpdater struct {
	mu            sync.Mutex
	statusUpdates []statusCall
	hookBumps     []string
	// nextPrev overrides the "previous" status returned by UpdateStatus on the
	// next call. Tests use this to simulate a session that's already in a
	// given status, so they can validate the "no emit when unchanged" guard.
	nextPrev string
}
type statusCall struct{ SessionID, Prev, Next string }

func (f *fakeSessionUpdater) UpdateStatus(sid, next string) (string, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	prev := "executing"
	if f.nextPrev != "" {
		prev = f.nextPrev
		f.nextPrev = ""
	}
	for _, c := range f.statusUpdates {
		if c.SessionID == sid {
			prev = c.Next
		}
	}
	f.statusUpdates = append(f.statusUpdates, statusCall{sid, prev, next})
	return prev, nil
}

func (f *fakeSessionUpdater) BumpLastHookAt(sid string) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.hookBumps = append(f.hookBumps, sid)
	return nil
}

type fakeBus struct {
	mu    sync.Mutex
	calls []emitCall
}
type emitCall struct {
	Name    string
	Payload any
}

func (f *fakeBus) Emit(name string, payload any) {
	f.mu.Lock()
	f.calls = append(f.calls, emitCall{name, payload})
	f.mu.Unlock()
}

// newHandlerUnderTest wraps the Handler in a real httptest.NewServer so tests
// can use absolute URLs against the loopback address it picks.
func newHandlerUnderTest(t *testing.T) (string, *TokenRegistry, *fakeSessionUpdater, *fakeBus) {
	t.Helper()
	reg := NewTokenRegistry()
	upd := &fakeSessionUpdater{}
	bus := &fakeBus{}
	h := NewHandler(reg, bus, upd)
	ts := httptest.NewServer(h)
	t.Cleanup(ts.Close)
	return ts.URL, reg, upd, bus
}

func TestHandler_Notification_UnknownTokenReturns404(t *testing.T) {
	baseURL, _, _, _ := newHandlerUnderTest(t)
	res, err := http.Post(baseURL+"/api/hooks/Notification/unknown", "application/json",
		bytes.NewReader([]byte(`{"message":"x"}`)))
	if err != nil {
		t.Fatalf("POST: %v", err)
	}
	defer func() { _ = res.Body.Close() }()
	if res.StatusCode != 404 {
		t.Errorf("status: got %d, want 404", res.StatusCode)
	}
}

func TestHandler_Notification_HappyPath(t *testing.T) {
	baseURL, reg, upd, bus := newHandlerUnderTest(t)
	tok := reg.Generate("sid-1")

	res, err := http.Post(baseURL+"/api/hooks/Notification/"+tok, "application/json",
		bytes.NewReader([]byte(`{"message":"need user"}`)))
	if err != nil {
		t.Fatalf("POST: %v", err)
	}
	defer func() { _ = res.Body.Close() }()
	if res.StatusCode != 204 {
		body, _ := io.ReadAll(res.Body)
		t.Errorf("status: got %d, want 204; body=%s", res.StatusCode, string(body))
	}
	if len(upd.statusUpdates) != 1 || upd.statusUpdates[0].SessionID != "sid-1" {
		t.Errorf("expected 1 status update for sid-1, got %+v", upd.statusUpdates)
	}
	if len(bus.calls) != 1 || bus.calls[0].Name != "session.status_changed" {
		t.Errorf("expected session.status_changed emit, got %+v", bus.calls)
	}
}

func TestHandler_Notification_NoEmitIfStatusUnchanged(t *testing.T) {
	upd := &fakeSessionUpdater{nextPrev: StatusAwaitingResponse}
	bus := &fakeBus{}
	reg := NewTokenRegistry()
	h := NewHandler(reg, bus, upd)
	ts := httptest.NewServer(h)
	defer ts.Close()
	tok := reg.Generate("sid-1")

	res, err := http.Post(ts.URL+"/api/hooks/Notification/"+tok, "application/json",
		bytes.NewReader([]byte(`{"message":"again"}`)))
	if err != nil {
		t.Fatalf("POST: %v", err)
	}
	defer func() { _ = res.Body.Close() }()

	if len(bus.calls) != 0 {
		t.Errorf("expected no emit when status unchanged, got %+v", bus.calls)
	}
}

func TestHandler_PreToolUse_Returns200WithContinueTrue(t *testing.T) {
	baseURL, reg, _, bus := newHandlerUnderTest(t)
	tok := reg.Generate("sid-1")

	res, err := http.Post(baseURL+"/api/hooks/PreToolUse/"+tok, "application/json",
		bytes.NewReader([]byte(`{"tool_name":"Read"}`)))
	if err != nil {
		t.Fatalf("POST: %v", err)
	}
	defer func() { _ = res.Body.Close() }()
	if res.StatusCode != 200 {
		t.Errorf("status: got %d, want 200", res.StatusCode)
	}
	var body map[string]bool
	_ = json.NewDecoder(res.Body).Decode(&body)
	if !body["continue"] {
		t.Errorf("body: got %+v, want {continue:true}", body)
	}
	if len(bus.calls) != 1 || bus.calls[0].Name != "session.tool_use" {
		t.Errorf("expected session.tool_use emit, got %+v", bus.calls)
	}
}

func TestHandler_PreToolUse_MissingToolNameReturns422(t *testing.T) {
	baseURL, reg, _, _ := newHandlerUnderTest(t)
	tok := reg.Generate("sid-1")
	res, err := http.Post(baseURL+"/api/hooks/PreToolUse/"+tok, "application/json",
		bytes.NewReader([]byte(`{}`)))
	if err != nil {
		t.Fatalf("POST: %v", err)
	}
	defer func() { _ = res.Body.Close() }()
	if res.StatusCode != 422 {
		t.Errorf("status: got %d, want 422", res.StatusCode)
	}
}

func TestHandler_Stop_StatusChangedOnlyIfPrevDifferent(t *testing.T) {
	baseURL, reg, _, bus := newHandlerUnderTest(t)
	tok := reg.Generate("sid-1")

	res, err := http.Post(baseURL+"/api/hooks/Stop/"+tok, "application/json",
		bytes.NewReader([]byte(`{}`)))
	if err != nil {
		t.Fatalf("POST: %v", err)
	}
	defer func() { _ = res.Body.Close() }()
	if res.StatusCode != 204 {
		t.Errorf("status: got %d, want 204", res.StatusCode)
	}
	if len(bus.calls) != 1 || bus.calls[0].Name != "session.status_changed" {
		t.Errorf("expected session.status_changed (executing→idle), got %+v", bus.calls)
	}
	// Stop should NOT emit session.stopped (manual-only).
	for _, c := range bus.calls {
		if c.Name == "session.stopped" {
			t.Errorf("hook Stop should not emit session.stopped: %+v", bus.calls)
		}
	}
}
