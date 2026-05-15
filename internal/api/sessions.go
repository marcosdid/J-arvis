package api

import (
	"context"

	"github.com/marcosdid/jarvis/internal/sandbox"
	"github.com/marcosdid/jarvis/internal/store"
)

// SessionsService is the API-layer view of *core.SessionsService.
type SessionsService interface {
	Start(ctx context.Context, taskID string) (*store.Session, error)
	Stop(ctx context.Context, sessionID string) error
	ListByTask(ctx context.Context, taskID string) ([]store.Session, error)
	GetTranscript(ctx context.Context, sessionID string) ([]sandbox.TranscriptMessage, error)
	CleanupForTask(ctx context.Context, taskID string) error
}

type SessionsAPI struct {
	svc SessionsService
}

func NewSessionsAPI(svc SessionsService) *SessionsAPI {
	return &SessionsAPI{svc: svc}
}

func (a *SessionsAPI) Start(taskID string) (*store.Session, error) {
	return a.svc.Start(context.Background(), taskID)
}

func (a *SessionsAPI) Stop(sessionID string) error {
	return a.svc.Stop(context.Background(), sessionID)
}

func (a *SessionsAPI) ListByTask(taskID string) ([]store.Session, error) {
	return a.svc.ListByTask(context.Background(), taskID)
}

func (a *SessionsAPI) GetTranscript(sessionID string) ([]sandbox.TranscriptMessage, error) {
	return a.svc.GetTranscript(context.Background(), sessionID)
}
