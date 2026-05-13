package events

import "testing"

func TestLazyEmitter_NilResolveIsNoOp(t *testing.T) {
	l := &LazyEmitter{}
	l.Emit("x", nil)
}

func TestLazyEmitter_ResolvesAndDelegates(t *testing.T) {
	fake := &FakeEmitter{}
	l := &LazyEmitter{Resolve: func() Emitter { return fake }}
	l.Emit("task.created", map[string]string{"id": "1"})
	if len(fake.Calls) != 1 {
		t.Fatalf("expected 1 call, got %d", len(fake.Calls))
	}
	if fake.Calls[0].Name != "task.created" {
		t.Errorf("name: got %q", fake.Calls[0].Name)
	}
}

func TestLazyEmitter_ResolveReturnsNilIsNoOp(t *testing.T) {
	l := &LazyEmitter{Resolve: func() Emitter { return nil }}
	l.Emit("x", nil)
}

func TestFakeEmitter_RecordsCalls(t *testing.T) {
	f := &FakeEmitter{}
	f.Emit("a", 1)
	f.Emit("b", 2)
	if len(f.Calls) != 2 {
		t.Errorf("expected 2 calls, got %d", len(f.Calls))
	}
}
