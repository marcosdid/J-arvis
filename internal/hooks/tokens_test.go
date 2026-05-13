package hooks

import (
	"sync"
	"testing"
)

func TestTokenRegistry_GenerateUnique64Hex(t *testing.T) {
	r := NewTokenRegistry()
	seen := map[string]bool{}
	for i := 0; i < 100; i++ {
		tok := r.Generate("sid-" + string(rune('a'+i%26)))
		if len(tok) != 64 {
			t.Errorf("token len: got %d, want 64", len(tok))
		}
		if seen[tok] {
			t.Errorf("duplicate token: %s", tok)
		}
		seen[tok] = true
	}
}

func TestTokenRegistry_ResolveRoundTrip(t *testing.T) {
	r := NewTokenRegistry()
	tok := r.Generate("session-1")
	got, ok := r.Resolve(tok)
	if !ok {
		t.Fatal("Resolve: not found")
	}
	if got != "session-1" {
		t.Errorf("Resolve: got %s, want session-1", got)
	}
}

func TestTokenRegistry_ResolveUnknown(t *testing.T) {
	r := NewTokenRegistry()
	_, ok := r.Resolve("nonexistent")
	if ok {
		t.Error("Resolve of unknown token should return ok=false")
	}
}

func TestTokenRegistry_Revoke(t *testing.T) {
	r := NewTokenRegistry()
	tok := r.Generate("session-1")
	r.Revoke(tok)
	if _, ok := r.Resolve(tok); ok {
		t.Error("token still resolvable after Revoke")
	}
}

func TestTokenRegistry_ConcurrentGenerateAndResolve(t *testing.T) {
	r := NewTokenRegistry()
	var wg sync.WaitGroup
	for i := 0; i < 50; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			tok := r.Generate("session")
			_, _ = r.Resolve(tok)
			r.Revoke(tok)
		}()
	}
	wg.Wait()
}

func TestTokenRegistry_FindBySessionID_ReturnsRegistered(t *testing.T) {
	r := NewTokenRegistry()
	tok := r.Generate("session-X")
	got := r.FindBySessionID("session-X")
	if got != tok {
		t.Errorf("got %q, want %q", got, tok)
	}
}

func TestTokenRegistry_FindBySessionID_NotFoundReturnsEmpty(t *testing.T) {
	r := NewTokenRegistry()
	if got := r.FindBySessionID("nonexistent"); got != "" {
		t.Errorf("got %q, want empty", got)
	}
}
