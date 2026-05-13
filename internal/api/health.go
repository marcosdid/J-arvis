package api

import (
	"context"
	"time"
)

type HealthSnapshot struct {
	AppVersion string `json:"appVersion"`
	Uptime     int64  `json:"uptime"`
}

type HealthAPI struct {
	startedAt time.Time
}

func NewHealthAPI() *HealthAPI {
	return &HealthAPI{startedAt: time.Now()}
}

func (h *HealthAPI) Snapshot(_ context.Context) (HealthSnapshot, error) {
	return HealthSnapshot{
		AppVersion: "0.10.0-f10-dev",
		Uptime:     int64(time.Since(h.startedAt).Seconds()),
	}, nil
}
