package api

import (
	"errors"
	"testing"

	"github.com/marcosdid/jarvis/internal/events"
)

type fakeSession struct {
	started  bool
	binPath  string
	args     []string
	running  bool
	pid      int
	sent     []string
	stopped  bool
	onOutput func(string)
	onExit   func(error)
	startErr error
}

func (f *fakeSession) Start(binPath string, args []string) error {
	if f.startErr != nil {
		return f.startErr
	}
	f.started = true
	f.binPath = binPath
	f.args = args
	f.running = true
	f.pid = 1234
	return nil
}
func (f *fakeSession) Send(data string) error {
	if !f.running {
		return errors.New("not running")
	}
	f.sent = append(f.sent, data)
	return nil
}
func (f *fakeSession) Resize(_, _ uint16) error    { return nil }
func (f *fakeSession) Stop() error                 { f.stopped = true; f.running = false; return nil }
func (f *fakeSession) Running() bool               { return f.running }
func (f *fakeSession) PID() int                    { return f.pid }
func (f *fakeSession) SetOnOutput(fn func(string)) { f.onOutput = fn }
func (f *fakeSession) SetOnExit(fn func(error))    { f.onExit = fn }

func TestMasterAPI_Start_EmitsStatus(t *testing.T) {
	bus := &events.FakeEmitter{}
	fake := &fakeSession{}
	api := NewMasterAPI(bus, func() Session { return fake }, "/usr/bin/claude")

	status, err := api.Start()
	if err != nil {
		t.Fatalf("Start: %v", err)
	}
	if !status.Running || status.PID != 1234 {
		t.Errorf("status: %+v", status)
	}
	if fake.binPath != "/usr/bin/claude" {
		t.Errorf("binPath: got %q", fake.binPath)
	}
	if len(bus.Calls) != 1 || bus.Calls[0].Name != "master.status" {
		t.Errorf("expected master.status emit, got %+v", bus.Calls)
	}
}

func TestMasterAPI_Start_OutputForwardsToBusAsEvent(t *testing.T) {
	bus := &events.FakeEmitter{}
	fake := &fakeSession{}
	api := NewMasterAPI(bus, func() Session { return fake }, "")
	if _, err := api.Start(); err != nil {
		t.Fatalf("Start: %v", err)
	}
	fake.onOutput("hello world")
	found := false
	for _, c := range bus.Calls {
		if c.Name == "master.output" && c.Payload == "hello world" {
			found = true
		}
	}
	if !found {
		t.Errorf("expected master.output emit with payload, got %+v", bus.Calls)
	}
}

func TestMasterAPI_Send_RequiresStart(t *testing.T) {
	bus := &events.FakeEmitter{}
	api := NewMasterAPI(bus, func() Session { return &fakeSession{} }, "")
	if err := api.Send("x"); err == nil {
		t.Error("expected error when sending before Start")
	}
}

func TestMasterAPI_Send_DelegatesToSession(t *testing.T) {
	bus := &events.FakeEmitter{}
	fake := &fakeSession{}
	api := NewMasterAPI(bus, func() Session { return fake }, "")
	_, _ = api.Start()
	if err := api.Send("hello\n"); err != nil {
		t.Fatalf("Send: %v", err)
	}
	if len(fake.sent) != 1 || fake.sent[0] != "hello\n" {
		t.Errorf("sent: %+v", fake.sent)
	}
}

func TestMasterAPI_Stop_StopsAndEmits(t *testing.T) {
	bus := &events.FakeEmitter{}
	fake := &fakeSession{}
	api := NewMasterAPI(bus, func() Session { return fake }, "")
	_, _ = api.Start()
	bus.Calls = nil
	if err := api.Stop(); err != nil {
		t.Fatalf("Stop: %v", err)
	}
	if !fake.stopped {
		t.Error("expected session.Stop called")
	}
	if len(bus.Calls) != 1 || bus.Calls[0].Name != "master.status" {
		t.Errorf("expected master.status emit, got %+v", bus.Calls)
	}
}

func TestMasterAPI_StartTwice_NoOpIfRunning(t *testing.T) {
	bus := &events.FakeEmitter{}
	fake := &fakeSession{}
	api := NewMasterAPI(bus, func() Session { return fake }, "")
	_, _ = api.Start()
	status, err := api.Start()
	if err != nil {
		t.Errorf("Start (second): %v", err)
	}
	if !status.Running {
		t.Error("expected Running=true on idempotent Start")
	}
}
