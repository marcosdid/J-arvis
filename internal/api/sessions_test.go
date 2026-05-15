package api

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/marcosdid/jarvis/internal/sandbox"
	"github.com/marcosdid/jarvis/internal/store"
)

type fakeSessionsService struct {
	startErr      error
	stopErr       error
	startedRow    *store.Session
	listResult    []store.Session
	transcriptOut []sandbox.TranscriptMessage
}

func (f *fakeSessionsService) Start(_ context.Context, _ string) (*store.Session, error) {
	if f.startErr != nil {
		return nil, f.startErr
	}
	return f.startedRow, nil
}

func (f *fakeSessionsService) Stop(_ context.Context, _ string) error { return f.stopErr }

func (f *fakeSessionsService) ListByTask(_ context.Context, _ string) ([]store.Session, error) {
	return f.listResult, nil
}

func (f *fakeSessionsService) GetTranscript(_ context.Context, _ string) ([]sandbox.TranscriptMessage, error) {
	return f.transcriptOut, nil
}

func (f *fakeSessionsService) CleanupForTask(_ context.Context, _ string) error { return nil }

func TestSessionsAPI_Start(t *testing.T) {
	row := &store.Session{ID: "sid-1", TaskID: "task-1", Status: "executing", StartedAt: time.Now()}
	api := NewSessionsAPI(&fakeSessionsService{startedRow: row})
	got, err := api.Start("task-1")
	if err != nil {
		t.Fatalf("Start: %v", err)
	}
	if got.ID != "sid-1" {
		t.Errorf("ID: %s", got.ID)
	}
}

func TestSessionsAPI_Start_PropagatesError(t *testing.T) {
	myErr := errors.New("boom")
	api := NewSessionsAPI(&fakeSessionsService{startErr: myErr})
	_, err := api.Start("task-1")
	if !errors.Is(err, myErr) {
		t.Errorf("want propagated err, got %v", err)
	}
}

func TestSessionsAPI_Stop(t *testing.T) {
	api := NewSessionsAPI(&fakeSessionsService{})
	if err := api.Stop("sid-1"); err != nil {
		t.Errorf("Stop: %v", err)
	}
}

func TestSessionsAPI_ListByTask(t *testing.T) {
	api := NewSessionsAPI(&fakeSessionsService{
		listResult: []store.Session{{ID: "sid-a"}, {ID: "sid-b"}},
	})
	got, err := api.ListByTask("task-1")
	if err != nil {
		t.Fatalf("ListByTask: %v", err)
	}
	if len(got) != 2 {
		t.Errorf("want 2, got %d", len(got))
	}
}

func TestSessionsAPI_GetTranscript(t *testing.T) {
	api := NewSessionsAPI(&fakeSessionsService{
		transcriptOut: []sandbox.TranscriptMessage{{Role: "user", Content: "hi"}},
	})
	got, err := api.GetTranscript("sid-1")
	if err != nil {
		t.Fatalf("GetTranscript: %v", err)
	}
	if len(got) != 1 || got[0].Role != "user" {
		t.Errorf("got %+v", got)
	}
}
