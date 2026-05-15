package localhttp

import "testing"

func TestNewReturnsUnstartedServer(t *testing.T) {
	s := New()
	if s == nil {
		t.Fatal("New returned nil")
	}
	if s.Started() {
		t.Errorf("Started()=true on fresh Server, want false")
	}
}
