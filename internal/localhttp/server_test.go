package localhttp

import (
	"net/http"
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
