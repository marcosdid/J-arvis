package api

import (
	"context"
	"errors"
	"strings"
	"testing"

	"github.com/marcosdid/jarvis/internal/core"
)

type fakeBootstrapSvc struct {
	startResult *core.StartedBootstrap
	startErr    error
	cancelErr   error
	startCalls  int
	cancelCalls int
}

func (f *fakeBootstrapSvc) Start(_ context.Context, _ string) (*core.StartedBootstrap, error) {
	f.startCalls++
	return f.startResult, f.startErr
}
func (f *fakeBootstrapSvc) Cancel(_ context.Context, _ string) error {
	f.cancelCalls++
	return f.cancelErr
}
func (f *fakeBootstrapSvc) CleanupForTask(_ context.Context, _ string) error { return nil }

func TestBootstrapAPI_Start_ReturnsView(t *testing.T) {
	fake := &fakeBootstrapSvc{
		startResult: &core.StartedBootstrap{
			SessionID:    "s-1",
			Cwd:          "/tmp/wt",
			ManifestPath: "/tmp/wt/.orchestrator/run.yml",
			PromptPath:   "/tmp/wt/.orchestrator/BOOTSTRAP_PROMPT.md",
		},
	}
	a := NewBootstrapAPI(fake)
	view, err := a.Start("t1")
	if err != nil {
		t.Fatalf("Start: %v", err)
	}
	if view.SessionID != "s-1" {
		t.Errorf("SessionID=%q", view.SessionID)
	}
	if view.Cwd != "/tmp/wt" {
		t.Errorf("Cwd=%q", view.Cwd)
	}
	if view.ManifestPath != "/tmp/wt/.orchestrator/run.yml" {
		t.Errorf("ManifestPath=%q", view.ManifestPath)
	}
	if view.PromptPath != "/tmp/wt/.orchestrator/BOOTSTRAP_PROMPT.md" {
		t.Errorf("PromptPath=%q", view.PromptPath)
	}
}

func TestBootstrapAPI_Start_ManifestAlreadyExists(t *testing.T) {
	fake := &fakeBootstrapSvc{startErr: core.ErrManifestAlreadyExists}
	a := NewBootstrapAPI(fake)
	_, err := a.Start("t1")
	if err == nil || !strings.Contains(err.Error(), "click ▶ Run again") {
		t.Errorf("err=%v, want human-readable message", err)
	}
}

func TestBootstrapAPI_Start_TaskTerminal(t *testing.T) {
	fake := &fakeBootstrapSvc{startErr: core.ErrTaskInTerminalState}
	a := NewBootstrapAPI(fake)
	_, err := a.Start("t1")
	if err == nil || !strings.Contains(err.Error(), "terminal state") {
		t.Errorf("err=%v, want terminal-state message", err)
	}
}

func TestBootstrapAPI_Start_SandboxUnavailable(t *testing.T) {
	fake := &fakeBootstrapSvc{startErr: core.ErrSandboxUnavailable}
	a := NewBootstrapAPI(fake)
	_, err := a.Start("t1")
	if err == nil || !strings.Contains(err.Error(), "sandbox unavailable") {
		t.Errorf("err=%v, want sandbox-unavailable message", err)
	}
}

func TestBootstrapAPI_Cancel_NoOpOnUnknown(t *testing.T) {
	fake := &fakeBootstrapSvc{}
	a := NewBootstrapAPI(fake)
	if err := a.Cancel("t-unknown"); err != nil {
		t.Errorf("Cancel: err=%v, want nil", err)
	}
}

func TestBootstrapAPI_Cancel_PropagatesUnexpectedErr(t *testing.T) {
	fake := &fakeBootstrapSvc{cancelErr: errors.New("disk full")}
	a := NewBootstrapAPI(fake)
	if err := a.Cancel("t1"); err == nil {
		t.Error("Cancel: got nil, want error")
	}
}
