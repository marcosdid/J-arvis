package api

import (
	"context"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/marcosdid/jarvis/internal/core"
	"github.com/marcosdid/jarvis/internal/store"
)

// Compile-time guard: RunsAPI satisfies the expected methods.
var _ interface {
	Start(string) (StartRunResult, error)
	Stop(string) error
	Get(string) (RunView, error)
	LocalHTTPBase() string
} = (*RunsAPI)(nil)

type fakeRunsSvc struct {
	startResult *store.Run
	startErr    error
}

func (f *fakeRunsSvc) StartRun(_ context.Context, _ string) (*store.Run, error) {
	return f.startResult, f.startErr
}
func (f *fakeRunsSvc) StopRun(_ context.Context, _ string) error { return nil }
func (f *fakeRunsSvc) GetActiveByTask(_ context.Context, _ string) (*store.Run, error) {
	return nil, nil
}
func (f *fakeRunsSvc) ContainerIDFor(_ context.Context, _ string, _ string) (string, error) {
	return "", nil
}
func (f *fakeRunsSvc) StreamLogs(_ context.Context, _ string, _ io.Writer) error { return nil }

func TestRunsAPI_Start_ManifestMissingReturnsBootstrapHint(t *testing.T) {
	svc := &fakeRunsSvc{startErr: core.ErrManifestMissing}
	a := NewRunsAPI(svc, func() string { return "http://localhost:0" })
	res, err := a.Start("t1")
	if err != nil {
		t.Fatalf("err=%v, want nil (manifest_missing should not error)", err)
	}
	if res.Run != nil {
		t.Errorf("res.Run=%v, want nil", res.Run)
	}
	if res.Bootstrap == nil {
		t.Fatal("Bootstrap nil")
	}
	if res.Bootstrap.Reason != "manifest_missing" {
		t.Errorf("Reason=%q", res.Bootstrap.Reason)
	}
}

func TestRunsAPI_Start_HappyPathReturnsRun(t *testing.T) {
	svc := &fakeRunsSvc{startResult: testRun(31010, 31011)}
	a := NewRunsAPI(svc, func() string { return "http://localhost:0" })
	res, err := a.Start("t1")
	if err != nil {
		t.Fatalf("err=%v, want nil", err)
	}
	if res.Bootstrap != nil {
		t.Errorf("res.Bootstrap=%v, want nil", res.Bootstrap)
	}
	if res.Run == nil {
		t.Fatal("Run nil")
	}
	if res.Run.ID != "r1" {
		t.Errorf("Run.ID=%q, want r1", res.Run.ID)
	}
}

func TestRunsAPI_Start_OtherErrorPropagates(t *testing.T) {
	svc := &fakeRunsSvc{startErr: errors.New("docker daemon dead")}
	a := NewRunsAPI(svc, func() string { return "http://localhost:0" })
	_, err := a.Start("t1")
	if err == nil {
		t.Fatal("want error, got nil")
	}
	if !strings.Contains(err.Error(), "docker daemon") {
		t.Errorf("err=%v, want passthrough of docker error", err)
	}
}

func TestRunView_URLsDerivedFromPorts(t *testing.T) {
	v := toRunView(testRun(31002, 31003))
	if v.URLs["backend"] != "http://localhost:31002" {
		t.Errorf("URLs[backend]=%q, want http://localhost:31002", v.URLs["backend"])
	}
	if v.URLs["frontend"] != "http://localhost:31003" {
		t.Errorf("URLs[frontend]=%q, want http://localhost:31003", v.URLs["frontend"])
	}
}

func TestLogsHandler_Returns404WhenContainerNotFound(t *testing.T) {
	// LogsHandler integration coverage lives in Stage 11; smoke test skipped
	// to avoid heavy mocking of core.RunsService. The handler is exercised
	// end-to-end by the Stage 11 integration test against real Docker.
	t.Skip("LogsHandler integration coverage lives in Stage 11; smoke skipped to avoid heavy mocking")
	_ = http.MethodGet
	_ = strings.Contains
	_ = io.EOF
	_ = context.Background
	_ = time.Now
	_ = httptest.NewRecorder
}
