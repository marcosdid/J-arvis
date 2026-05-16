package api

import (
	"bufio"
	"context"
	"errors"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/marcosdid/jarvis/internal/core"
	"github.com/marcosdid/jarvis/internal/store"
)

type RunsAPI struct {
	svc     *core.RunsService
	baseURL func() string
}

func NewRunsAPI(svc *core.RunsService, baseURL func() string) *RunsAPI {
	return &RunsAPI{svc: svc, baseURL: baseURL}
}

type RunView struct {
	ID           string            `json:"id"`
	TaskID       string            `json:"task_id"`
	Status       string            `json:"status"`
	Cwd          string            `json:"cwd"`
	Ports        map[string]int    `json:"ports"`
	URLs         map[string]string `json:"urls"`
	NetworkName  string            `json:"network_name"`
	StartedAt    time.Time         `json:"started_at"`
	EndedAt      *time.Time        `json:"ended_at"`
	ErrorMessage string            `json:"error_message,omitempty"`
}

func toRunView(r *store.Run) RunView {
	ports := r.Ports()
	urls := make(map[string]string, len(ports))
	for svc, port := range ports {
		urls[svc] = fmt.Sprintf("http://localhost:%d", port)
	}
	return RunView{
		ID:           r.ID,
		TaskID:       r.TaskID,
		Status:       r.Status,
		Cwd:          r.Cwd,
		Ports:        ports,
		URLs:         urls,
		NetworkName:  r.NetworkName,
		StartedAt:    r.StartedAt,
		EndedAt:      r.EndedAt,
		ErrorMessage: r.ErrorMessage,
	}
}

func (a *RunsAPI) Start(taskID string) (RunView, error) {
	run, err := a.svc.StartRun(context.Background(), taskID)
	if err != nil {
		if errors.Is(err, core.ErrManifestMissing) {
			return RunView{}, fmt.Errorf("no manifest at <worktree>/.orchestrator/run.yml — commit one to enable Run")
		}
		return RunView{}, err
	}
	return toRunView(run), nil
}

func (a *RunsAPI) Get(taskID string) (RunView, error) {
	run, err := a.svc.GetActiveByTask(context.Background(), taskID)
	if err != nil {
		return RunView{}, err
	}
	return toRunView(run), nil
}

func (a *RunsAPI) Stop(runID string) error {
	return a.svc.StopRun(context.Background(), runID)
}

// LocalHTTPBase returns the running localhttp base URL (e.g.
// "http://127.0.0.1:48123"). Used by the UI to build SSE URLs for run logs.
func (a *RunsAPI) LocalHTTPBase() string {
	return a.baseURL()
}

// LogsHandler returns the SSE handler for `/api/runs/{runID}/logs?service=<name>`.
// Mounted on the localhttp.Server in main.go (no auth, loopback-only).
func (a *RunsAPI) LogsHandler() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		runID := r.PathValue("runID")
		svc := r.URL.Query().Get("service")
		if runID == "" || svc == "" {
			http.Error(w, "missing runID or service", http.StatusBadRequest)
			return
		}

		cid, err := a.svc.ContainerIDFor(r.Context(), runID, svc)
		if err != nil {
			http.Error(w, err.Error(), http.StatusNotFound)
			return
		}

		w.Header().Set("Content-Type", "text/event-stream")
		w.Header().Set("Cache-Control", "no-cache")
		w.Header().Set("Connection", "keep-alive")
		flusher, _ := w.(http.Flusher)

		pr, pw := io.Pipe()
		defer pr.Close()
		go func() {
			defer pw.Close()
			_ = a.svc.StreamLogs(r.Context(), cid, pw)
		}()

		scanner := bufio.NewScanner(pr)
		for scanner.Scan() {
			fmt.Fprintf(w, "data: %s\n\n", scanner.Text())
			if flusher != nil {
				flusher.Flush()
			}
			if r.Context().Err() != nil {
				return
			}
		}
	})
}

// Test helper
func testRun(backendPort, frontendPort int) *store.Run {
	portsJSON := fmt.Sprintf(`{"backend":%d,"frontend":%d}`, backendPort, frontendPort)
	return &store.Run{ID: "r1", TaskID: "t1", Status: "ready", PortsJSON: portsJSON}
}
