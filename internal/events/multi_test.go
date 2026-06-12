package events

import "testing"

func TestMultiEmitterFansOut(t *testing.T) {
	a, b := &FakeEmitter{}, &FakeEmitter{}
	m := MultiEmitter{a, nil, b} // nil entries are skipped
	m.Emit("x", 1)
	if len(a.Snapshot()) != 1 || len(b.Snapshot()) != 1 {
		t.Fatalf("fan-out failed: a=%d b=%d", len(a.Snapshot()), len(b.Snapshot()))
	}
}
