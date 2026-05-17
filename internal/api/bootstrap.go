package api

import (
	"context"
	"errors"
	"fmt"

	"github.com/marcosdid/jarvis/internal/core"
)

// BootstrapService is the API-layer view of *core.BootstrapService.
type BootstrapService interface {
	Start(ctx context.Context, taskID string) (*core.StartedBootstrap, error)
	Cancel(ctx context.Context, taskID string) error
	CleanupForTask(ctx context.Context, taskID string) error
}

type BootstrapAPI struct {
	svc BootstrapService
}

func NewBootstrapAPI(svc BootstrapService) *BootstrapAPI {
	return &BootstrapAPI{svc: svc}
}

// BootstrapView is the JSON-serializable projection of core.StartedBootstrap
// (the WatcherReady channel is stripped — it's a Go-only sync barrier for tests).
type BootstrapView struct {
	SessionID    string `json:"session_id"`
	Cwd          string `json:"cwd"`
	ManifestPath string `json:"manifest_path"`
	PromptPath   string `json:"prompt_path"`
}

func (a *BootstrapAPI) Start(taskID string) (BootstrapView, error) {
	started, err := a.svc.Start(context.Background(), taskID)
	if err != nil {
		return BootstrapView{}, translateBootstrapErr(err)
	}
	return BootstrapView{
		SessionID:    started.SessionID,
		Cwd:          started.Cwd,
		ManifestPath: started.ManifestPath,
		PromptPath:   started.PromptPath,
	}, nil
}

func (a *BootstrapAPI) Cancel(taskID string) error {
	return a.svc.Cancel(context.Background(), taskID)
}

// translateBootstrapErr maps sentinel core errors to human-readable messages
// the UI surfaces directly to the user. Other errors pass through unchanged.
func translateBootstrapErr(err error) error {
	switch {
	case errors.Is(err, core.ErrManifestAlreadyExists):
		return fmt.Errorf("manifest already exists; click ▶ Run again to start the stack")
	case errors.Is(err, core.ErrTaskInTerminalState):
		return fmt.Errorf("task is already in a terminal state; bootstrap not allowed")
	case errors.Is(err, core.ErrSandboxUnavailable):
		return fmt.Errorf("sandbox unavailable (ai-jail or terminal missing): %v", err)
	default:
		return err
	}
}
