package api

import (
	"context"
	"time"
)

type HealthSnapshot struct {
	AppVersion       string `json:"appVersion"`
	Uptime           int64  `json:"uptime"`
	SandboxAvailable bool   `json:"sandbox_available"`
	SandboxReason    string `json:"sandbox_reason"`
}

type SandboxProbe func() (available bool, reason string)

type HealthAPI struct {
	startedAt time.Time
	probe     SandboxProbe
}

// nil probe → sandbox_available=false until wired.
func NewHealthAPI(probe SandboxProbe) *HealthAPI {
	return &HealthAPI{startedAt: time.Now(), probe: probe}
}

func (h *HealthAPI) Snapshot(_ context.Context) (HealthSnapshot, error) {
	avail, reason := false, ""
	if h.probe != nil {
		avail, reason = h.probe()
	}
	return HealthSnapshot{
		AppVersion:       "0.10.0-f10-dev",
		Uptime:           int64(time.Since(h.startedAt).Seconds()),
		SandboxAvailable: avail,
		SandboxReason:    reason,
	}, nil
}
