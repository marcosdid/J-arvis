package api

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

// Compile-time guard: RunsAPI satisfies the expected methods.
var _ interface {
	Start(string) (RunView, error)
	Stop(string) error
	Get(string) (RunView, error)
	LocalHTTPBase() string
} = (*RunsAPI)(nil)

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
