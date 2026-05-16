package api

import (
	"context"

	"github.com/marcosdid/jarvis/internal/core"
	"github.com/marcosdid/jarvis/internal/events"
)

// MasterAPI is the Wails-bound thin shell over core.MasterService.
// All domain logic (singleton lifecycle, DB persistence, watchdog,
// ai-jail spawn) lives in core.MasterService.
type MasterAPI struct {
	svc *core.MasterService
	bus events.Emitter
}

// NewMasterAPI wires the Wails surface and bridges session output/exit
// from the underlying *master.Session through to the event bus.
func NewMasterAPI(svc *core.MasterService, bus events.Emitter) *MasterAPI {
	a := &MasterAPI{svc: svc, bus: bus}
	svc.SetOnOutput(func(chunk string) { bus.Emit("master.output", chunk) })
	svc.SetOnExit(func(err error) {
		msg := ""
		if err != nil {
			msg = err.Error()
		}
		bus.Emit("master.exit", map[string]string{"error": msg})
	})
	return a
}

// MasterStatusView is the JSON shape sent to the UI.
type MasterStatusView struct {
	Running   bool   `json:"running"`
	PID       int    `json:"pid"`
	SessionID string `json:"session_id"`
}

func (a *MasterAPI) Start() (MasterStatusView, error) {
	sess, err := a.svc.Start(context.Background())
	if err != nil {
		return MasterStatusView{}, err
	}
	pid := 0
	if sess.PID != nil {
		pid = *sess.PID
	}
	return MasterStatusView{Running: true, PID: pid, SessionID: sess.ClaudeSessionID}, nil
}

func (a *MasterAPI) Stop() error {
	return a.svc.Stop(context.Background())
}

func (a *MasterAPI) Send(data string) error {
	return a.svc.Send(data)
}

func (a *MasterAPI) Resize(rows, cols uint16) error {
	return a.svc.Resize(rows, cols)
}

func (a *MasterAPI) Status() MasterStatusView {
	st := a.svc.Status(context.Background())
	return MasterStatusView{Running: st.Running, PID: st.PID, SessionID: st.SessionID}
}
