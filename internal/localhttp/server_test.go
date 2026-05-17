package localhttp

import (
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
	"testing"
)

func TestNewReturnsUnstartedServer(t *testing.T) {
	s := New()
	if s == nil {
		t.Fatal("New returned nil")
	}
	if s.Started() {
		t.Errorf("Started()=true on fresh Server, want false")
	}
}

func TestMountBeforeStartSucceeds(t *testing.T) {
	s := New()
	h := http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusTeapot)
	})
	if err := s.Mount("/foo", h); err != nil {
		t.Fatalf("Mount: %v", err)
	}
}

func TestStartStopRoundTrip(t *testing.T) {
	s := New()
	if err := s.Mount("/ping", http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_, _ = io.WriteString(w, "pong")
	})); err != nil {
		t.Fatalf("Mount: %v", err)
	}
	port, err := s.Start()
	if err != nil {
		t.Fatalf("Start: %v", err)
	}
	if port == 0 {
		t.Fatal("Start returned port 0")
	}
	if !strings.HasPrefix(s.BaseURL(), fmt.Sprintf("http://127.0.0.1:%d", port)) {
		t.Errorf("BaseURL=%q, want prefix http://127.0.0.1:%d", s.BaseURL(), port)
	}
	res, err := http.Get(s.BaseURL() + "/ping")
	if err != nil {
		t.Fatalf("Get: %v", err)
	}
	defer res.Body.Close()
	body, _ := io.ReadAll(res.Body)
	if string(body) != "pong" {
		t.Errorf("body=%q, want pong", body)
	}
	if err := s.Stop(); err != nil {
		t.Errorf("Stop: %v", err)
	}
}

func TestMountAfterStartReturnsError(t *testing.T) {
	s := New()
	if _, err := s.Start(); err != nil {
		t.Fatalf("Start: %v", err)
	}
	defer s.Stop()
	err := s.Mount("/bar", http.NotFoundHandler())
	if !errors.Is(err, ErrAlreadyStarted) {
		t.Fatalf("err=%v, want ErrAlreadyStarted", err)
	}
}

func TestStartTwiceReturnsError(t *testing.T) {
	s := New()
	if _, err := s.Start(); err != nil {
		t.Fatalf("Start: %v", err)
	}
	defer s.Stop()
	if _, err := s.Start(); !errors.Is(err, ErrAlreadyStarted) {
		t.Fatalf("second Start err=%v, want ErrAlreadyStarted", err)
	}
}

func TestStopWithoutStartIsNoOp(t *testing.T) {
	s := New()
	if err := s.Stop(); err != nil {
		t.Errorf("Stop on unstarted server: %v", err)
	}
}
