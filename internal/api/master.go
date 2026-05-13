package api

import (
	"errors"
	"sync"

	"github.com/marcosdid/jarvis/internal/events"
	"github.com/marcosdid/jarvis/internal/master"
)

// Session is the interface MasterAPI needs from the underlying pty session.
type Session interface {
	Start(binPath string, extraArgs []string) error
	Send(data string) error
	Resize(rows, cols uint16) error
	Stop() error
	Running() bool
	PID() int
	SetOnOutput(func(chunk string))
	SetOnExit(func(err error))
}

// productionSession adapts *master.Session to the Session interface.
type productionSession struct {
	*master.Session
}

func (p *productionSession) SetOnOutput(fn func(chunk string)) {
	p.OnOutput = fn
}

func (p *productionSession) SetOnExit(fn func(err error)) {
	p.OnExit = fn
}

type SessionFactory func() Session

func DefaultSessionFactory() Session {
	return &productionSession{Session: master.New()}
}

type MasterAPI struct {
	bus     events.Emitter
	factory SessionFactory
	mu      sync.Mutex
	session Session
	binPath string
}

func NewMasterAPI(bus events.Emitter, factory SessionFactory, binPath string) *MasterAPI {
	return &MasterAPI{bus: bus, factory: factory, binPath: binPath}
}

type MasterStatus struct {
	Running bool `json:"running"`
	PID     int  `json:"pid"`
}

func (a *MasterAPI) Status() MasterStatus {
	a.mu.Lock()
	defer a.mu.Unlock()
	if a.session == nil {
		return MasterStatus{}
	}
	return MasterStatus{Running: a.session.Running(), PID: a.session.PID()}
}

func (a *MasterAPI) Start() (MasterStatus, error) {
	a.mu.Lock()
	defer a.mu.Unlock()
	if a.session != nil && a.session.Running() {
		return MasterStatus{Running: true, PID: a.session.PID()}, nil
	}
	s := a.factory()
	s.SetOnOutput(func(chunk string) {
		a.bus.Emit("master.output", chunk)
	})
	s.SetOnExit(func(err error) {
		msg := ""
		if err != nil {
			msg = err.Error()
		}
		a.bus.Emit("master.exit", map[string]string{"error": msg})
	})
	if err := s.Start(a.binPath, nil); err != nil {
		return MasterStatus{}, err
	}
	a.session = s
	status := MasterStatus{Running: true, PID: s.PID()}
	a.bus.Emit("master.status", status)
	return status, nil
}

func (a *MasterAPI) Send(data string) error {
	a.mu.Lock()
	s := a.session
	a.mu.Unlock()
	if s == nil {
		return errors.New("session not started")
	}
	return s.Send(data)
}

func (a *MasterAPI) Resize(rows, cols uint16) error {
	a.mu.Lock()
	s := a.session
	a.mu.Unlock()
	if s == nil {
		return errors.New("session not started")
	}
	return s.Resize(rows, cols)
}

func (a *MasterAPI) Stop() error {
	a.mu.Lock()
	s := a.session
	a.session = nil
	a.mu.Unlock()
	if s == nil {
		return nil
	}
	err := s.Stop()
	a.bus.Emit("master.status", MasterStatus{Running: false, PID: 0})
	return err
}
