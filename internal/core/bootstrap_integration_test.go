//go:build integration

package core

import (
	"context"
	"os"
	"testing"
	"time"

	"github.com/marcosdid/jarvis/internal/sandbox"
)

func TestBootstrap_Smoke_RealAijail(t *testing.T) {
	if _, err := sandbox.DetectTerminal(); err != nil {
		t.Skipf("no terminal: %v", err)
	}
	if err := sandbox.SandboxAvailable(); err != nil {
		t.Skipf("sandbox not available: %v", err)
	}

	env := newBootstrapTestEnv(t)
	defer env.cleanup()
	// Swap runtime to a real one for this smoke
	env.svc.runtime = sandbox.NewAijailRuntime()

	ctx := context.Background()
	started, err := env.svc.Start(ctx, env.taskID)
	if err != nil {
		t.Fatalf("Start: %v", err)
	}
	<-started.WatcherReady

	defer func() { _ = env.svc.Cancel(ctx, env.taskID) }()

	// Drop a valid manifest from the test process (simulates Claude writing).
	manifest := []byte(`version: "1"
services:
  web:
    image: nginx
`)
	if err := os.WriteFile(started.ManifestPath, manifest, 0o644); err != nil {
		t.Fatalf("write manifest: %v", err)
	}

	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		for _, c := range env.emitter.Snapshot() {
			if c.Name == "bootstrap.proposed" {
				if p, ok := c.Payload.(BootstrapProposedPayload); ok && p.Valid {
					return // success
				}
			}
		}
		time.Sleep(50 * time.Millisecond)
	}
	t.Fatal("bootstrap.proposed valid never emitted in 5s (real ai-jail)")
}
