package master

import (
	"strings"
	"sync"
	"testing"
	"time"
)

// Use /bin/sh as a stand-in for claude — gives a real interactive shell
// over pty without depending on claude being installed.
func TestSession_StartSendStop(t *testing.T) {
	s := New()
	var mu sync.Mutex
	var collected strings.Builder
	s.OnOutput = func(chunk string) {
		mu.Lock()
		defer mu.Unlock()
		collected.WriteString(chunk)
	}

	if err := s.Start("/bin/sh", nil); err != nil {
		t.Fatalf("Start: %v", err)
	}
	if !s.Running() {
		t.Error("expected Running=true after Start")
	}
	if s.PID() <= 0 {
		t.Error("expected PID > 0")
	}

	if err := s.Send("echo j-arvis-pty-marker\n"); err != nil {
		t.Fatalf("Send: %v", err)
	}

	// Wait up to 1s for the echo to come back through the pty.
	deadline := time.Now().Add(1 * time.Second)
	for time.Now().Before(deadline) {
		mu.Lock()
		got := collected.String()
		mu.Unlock()
		if strings.Contains(got, "j-arvis-pty-marker") {
			break
		}
		time.Sleep(20 * time.Millisecond)
	}
	mu.Lock()
	final := collected.String()
	mu.Unlock()
	if !strings.Contains(final, "j-arvis-pty-marker") {
		t.Errorf("expected echo in output, got %q", final)
	}

	if err := s.Stop(); err != nil {
		t.Errorf("Stop: %v", err)
	}
	time.Sleep(50 * time.Millisecond)
	if s.Running() {
		t.Error("expected Running=false after Stop")
	}
}

func TestSession_SendBeforeStart(t *testing.T) {
	s := New()
	if err := s.Send("x"); err == nil {
		t.Error("expected error when sending before Start")
	}
}

func TestSession_StartTwice(t *testing.T) {
	s := New()
	if err := s.Start("/bin/sh", nil); err != nil {
		t.Fatalf("Start: %v", err)
	}
	defer s.Stop()
	if err := s.Start("/bin/sh", nil); err == nil {
		t.Error("expected error on double Start")
	}
}

func TestSession_Resize(t *testing.T) {
	s := New()
	if err := s.Start("/bin/sh", nil); err != nil {
		t.Fatalf("Start: %v", err)
	}
	defer s.Stop()
	if err := s.Resize(40, 120); err != nil {
		t.Errorf("Resize: %v", err)
	}
}
