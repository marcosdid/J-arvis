package core

import (
	"context"
	"errors"
	"io"
	"os"
	"path/filepath"
	"reflect"
	"sync"
	"testing"
	"time"

	"github.com/marcosdid/jarvis/internal/events"
	"github.com/marcosdid/jarvis/internal/sandbox"
	"github.com/marcosdid/jarvis/internal/store"
)

func TestTopoSort_NoDeps_StableOrder(t *testing.T) {
	services := map[string]ServiceSpec{
		"a": {Image: "x"},
		"b": {Image: "y"},
	}
	got, err := topoSort(services)
	if err != nil {
		t.Fatal(err)
	}
	want := []string{"a", "b"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("got=%v, want %v", got, want)
	}
}

func TestTopoSort_DependencyChain(t *testing.T) {
	services := map[string]ServiceSpec{
		"frontend": {Image: "f", DependsOn: []string{"backend"}},
		"backend":  {Image: "b", DependsOn: []string{"db"}},
		"db":       {Image: "d"},
	}
	got, err := topoSort(services)
	if err != nil {
		t.Fatal(err)
	}
	want := []string{"db", "backend", "frontend"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("got=%v, want %v", got, want)
	}
}

func TestTopoSort_Cycle_ReturnsError(t *testing.T) {
	services := map[string]ServiceSpec{
		"a": {Image: "x", DependsOn: []string{"b"}},
		"b": {Image: "y", DependsOn: []string{"a"}},
	}
	_, err := topoSort(services)
	if !errors.Is(err, ErrCircularDeps) {
		t.Errorf("err=%v, want ErrCircularDeps", err)
	}
}

// fakeDocker records calls; per-method error injection available.
type fakeDocker struct {
	mu                sync.Mutex
	buildCalls        []string
	netCreateCalls    []string
	netRmCalls        []string
	containerStarts   []sandbox.ContainerSpec
	runs              []runCall
	stops             []string
	rms               []string
	healthStatusCalls []string
	healthStatus      string

	buildErr          error
	netCreateErr      error
	containerStartErr error
	runInContainerErr error
}

type runCall struct {
	CID     string
	Command []string
}

func newFakeDocker() *fakeDocker { return &fakeDocker{healthStatus: "healthy"} }

func (f *fakeDocker) Build(_ context.Context, _, tag string) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.buildCalls = append(f.buildCalls, tag)
	return f.buildErr
}

func (f *fakeDocker) NetworkCreate(_ context.Context, name string) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.netCreateCalls = append(f.netCreateCalls, name)
	return f.netCreateErr
}

func (f *fakeDocker) NetworkRm(_ context.Context, name string) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.netRmCalls = append(f.netRmCalls, name)
	return nil
}

func (f *fakeDocker) ContainerStart(_ context.Context, spec sandbox.ContainerSpec) (string, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	if f.containerStartErr != nil {
		return "", f.containerStartErr
	}
	f.containerStarts = append(f.containerStarts, spec)
	return "cid-" + spec.NetworkAlias, nil
}

func (f *fakeDocker) RunInContainer(_ context.Context, cid string, cmd []string, _ time.Duration) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.runs = append(f.runs, runCall{cid, cmd})
	return f.runInContainerErr
}

func (f *fakeDocker) StreamLogs(_ context.Context, _ string, _ io.Writer) error { return nil }

func (f *fakeDocker) Stop(_ context.Context, cid string) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.stops = append(f.stops, cid)
	return nil
}

func (f *fakeDocker) Rm(_ context.Context, cid string) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.rms = append(f.rms, cid)
	return nil
}

func (f *fakeDocker) ContainerHealthStatus(_ context.Context, cid string) (string, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.healthStatusCalls = append(f.healthStatusCalls, cid)
	return f.healthStatus, nil
}

// Stub repos for test wiring.
type stubTasksRepo struct{ task *store.Task }

func (s *stubTasksRepo) Get(_ context.Context, _ string) (*store.Task, error) { return s.task, nil }

type stubWorktreesRepo struct{ wts []store.Worktree }

func (s *stubWorktreesRepo) ListByTask(_ context.Context, _ string) ([]store.Worktree, error) {
	return s.wts, nil
}

type stubProjectsRepo struct{ proj *store.Project }

func (s *stubProjectsRepo) GetByID(_ context.Context, _ string) (*store.Project, error) {
	return s.proj, nil
}

func stringPtr(s string) *string { return &s }

func TestStartRun_HappyPath(t *testing.T) {
	dir := t.TempDir()
	_ = os.MkdirAll(filepath.Join(dir, ".orchestrator"), 0o755)
	manifest := `version: "1"
services:
  db:
    image: postgres:15
    port: 5432
`
	_ = os.WriteFile(filepath.Join(dir, ".orchestrator", "run.yml"), []byte(manifest), 0o644)

	db := newTestStoreDB(t)
	// Seed project + task in DB so the run_instances FK to tasks resolves.
	now := time.Now().UTC()
	if _, err := db.Exec(
		`INSERT INTO projects(id, name, path, created_at) VALUES (?, ?, ?, ?)`,
		"p1", "p1", "/projects/p1", now,
	); err != nil {
		t.Fatalf("seed project: %v", err)
	}
	if _, err := db.Exec(
		`INSERT INTO tasks(id, project_id, title, state, created_at, updated_at)
		 VALUES (?, ?, ?, 'in_progress', ?, ?)`,
		"t1", "p1", "seed-t1", now, now,
	); err != nil {
		t.Fatalf("seed task: %v", err)
	}
	repo := store.NewRunsRepo(db)
	allocator := NewPortAllocator()
	docker := newFakeDocker()

	branch := "main"
	task := &store.Task{ID: "t1", ProjectID: "p1", State: "in_progress", Branch: &branch}
	wts := []store.Worktree{{ID: "w1", TaskID: stringPtr("t1"), Path: dir}}
	proj := &store.Project{ID: "p1", Path: "/projects/p1"}

	svc := NewRunsService(repo, docker, allocator,
		&stubTasksRepo{task: task},
		&stubWorktreesRepo{wts: wts},
		&stubProjectsRepo{proj: proj},
		&events.FakeEmitter{})
	svc.dockerCheck = func() error { return nil }

	run, err := svc.StartRun(context.Background(), "t1")
	if err != nil {
		t.Fatalf("StartRun: %v", err)
	}
	if run.Status != "ready" {
		t.Errorf("status=%q, want ready", run.Status)
	}
	ports := run.Ports()
	if p := ports["db"]; p < MinPort || p > MaxPort {
		t.Errorf("db port %d out of range", p)
	}
	if len(docker.netCreateCalls) != 1 {
		t.Errorf("network create calls=%d", len(docker.netCreateCalls))
	}
	if len(docker.containerStarts) != 1 {
		t.Errorf("container start calls=%d", len(docker.containerStarts))
	}
}
