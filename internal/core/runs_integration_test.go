//go:build integration

package core

import (
	"context"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"testing"
	"time"

	"github.com/marcosdid/jarvis/internal/events"
	"github.com/marcosdid/jarvis/internal/sandbox"
	"github.com/marcosdid/jarvis/internal/store"
)

// TestRuns_IntegrationSmoke_Nginx brings up an nginx container via the real
// SubprocessDockerOps, asserts the host port responds with 200, then stops
// the run cleanly. Skips if `docker` is not on PATH.
func TestRuns_IntegrationSmoke_Nginx(t *testing.T) {
	if _, err := exec.LookPath("docker"); err != nil {
		t.Skip("docker not in PATH")
	}

	// Manifest with single nginx service
	dir := t.TempDir()
	if err := os.MkdirAll(filepath.Join(dir, ".orchestrator"), 0o755); err != nil {
		t.Fatal(err)
	}
	yaml := `version: "1"
services:
  web:
    image: nginx:alpine
    port: 80
`
	if err := os.WriteFile(filepath.Join(dir, ".orchestrator", "run.yml"), []byte(yaml), 0o644); err != nil {
		t.Fatal(err)
	}

	db := newTestStoreDB(t)
	repo := store.NewRunsRepo(db)
	seedProjectAndTaskForRuns(t, db, "p1", "t1")

	branch := "main"
	task := &store.Task{ID: "t1", ProjectID: "p1", State: "in_progress", Branch: &branch}
	wts := []store.Worktree{{ID: "w1", TaskID: stringPtr("t1"), Path: dir}}
	proj := &store.Project{ID: "p1", Path: "/projects/p1"}

	svc := NewRunsService(repo, sandbox.NewSubprocessDockerOps(), NewPortAllocator(),
		&stubTasksRepo{task: task},
		&stubWorktreesRepo{wts: wts},
		&stubProjectsRepo{proj: proj},
		&events.FakeEmitter{})

	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()

	run, err := svc.StartRun(ctx, "t1")
	if err != nil {
		t.Fatalf("StartRun: %v", err)
	}
	// Always tear down — even if asserts below fail
	t.Cleanup(func() { _ = svc.StopRun(context.Background(), run.ID) })

	if run.Status != "ready" {
		t.Errorf("status=%q, want ready", run.Status)
	}
	ports := run.Ports()
	port := ports["web"]
	if port == 0 {
		t.Fatal("no web port allocated")
	}

	// HTTP GET against the allocated port. nginx may take a beat to come up.
	url := "http://localhost:" + strconv.Itoa(port)
	deadline := time.Now().Add(15 * time.Second)
	var lastErr error
	for time.Now().Before(deadline) {
		resp, err := http.Get(url)
		if err == nil && resp.StatusCode == 200 {
			_ = resp.Body.Close()
			return // success
		}
		if resp != nil {
			_ = resp.Body.Close()
		}
		lastErr = err
		time.Sleep(500 * time.Millisecond)
	}
	t.Fatalf("nginx never responded on %s within 15s; lastErr=%v", url, lastErr)
}
