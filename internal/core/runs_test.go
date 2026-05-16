package core

import (
	"context"
	"database/sql"
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

func (s *stubProjectsRepo) Get(_ context.Context, _ string) (*store.Project, error) {
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

// seedProjectAndTaskForRuns seeds the database with project and task rows
// so that run_instances FK to tasks resolves properly.
func seedProjectAndTaskForRuns(t *testing.T, db *sql.DB, projectID, taskID string) {
	t.Helper()
	now := time.Now().UTC()
	if _, err := db.Exec(
		`INSERT INTO projects(id, name, path, created_at) VALUES (?, ?, ?, ?)`,
		projectID, projectID, "/tmp/"+projectID, now); err != nil {
		t.Fatal(err)
	}
	if _, err := db.Exec(
		`INSERT INTO tasks(id, project_id, title, state, created_at, updated_at) VALUES (?, ?, ?, 'in_progress', ?, ?)`,
		taskID, projectID, "tt", now, now); err != nil {
		t.Fatal(err)
	}
}

func TestStartRun_BuildFails_RollsBack(t *testing.T) {
	dir := t.TempDir()
	_ = os.MkdirAll(filepath.Join(dir, ".orchestrator"), 0o755)
	manifest := `version: "1"
services:
  web:
    build: ./web
    port: 8080
`
	_ = os.WriteFile(filepath.Join(dir, ".orchestrator", "run.yml"), []byte(manifest), 0o644)

	db := newTestStoreDB(t)
	repo := store.NewRunsRepo(db)
	allocator := NewPortAllocator()
	docker := newFakeDocker()
	docker.buildErr = errors.New("docker build boom")

	branch := "main"
	task := &store.Task{ID: "t1", ProjectID: "p1", State: "in_progress", Branch: &branch}
	wts := []store.Worktree{{ID: "w1", TaskID: stringPtr("t1"), Path: dir}}
	proj := &store.Project{ID: "p1", Path: "/projects/p1"}

	seedProjectAndTaskForRuns(t, db, "p1", "t1")

	svc := NewRunsService(repo, docker, allocator,
		&stubTasksRepo{task: task},
		&stubWorktreesRepo{wts: wts},
		&stubProjectsRepo{proj: proj},
		&events.FakeEmitter{})
	svc.dockerCheck = func() error { return nil }

	_, err := svc.StartRun(context.Background(), "t1")
	if err == nil {
		t.Fatal("StartRun: nil err, want build failure")
	}
	// Port released
	if _, err := allocator.Allocate(); err != nil {
		t.Errorf("port not released after rollback: %v", err)
	}
	// No active runs
	rows, _ := repo.ListActive(context.Background())
	if len(rows) != 0 {
		t.Errorf("active runs after rollback: %d, want 0", len(rows))
	}
	// No containers started
	if len(docker.containerStarts) != 0 {
		t.Errorf("containers started despite build failure: %d", len(docker.containerStarts))
	}
}

func TestStartRun_HealthcheckTimeout_RollsBack(t *testing.T) {
	dir := t.TempDir()
	_ = os.MkdirAll(filepath.Join(dir, ".orchestrator"), 0o755)
	manifest := `version: "1"
services:
  web:
    image: nginx
    port: 80
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost"]
      interval: 10ms
      retries: 2
`
	_ = os.WriteFile(filepath.Join(dir, ".orchestrator", "run.yml"), []byte(manifest), 0o644)

	db := newTestStoreDB(t)
	repo := store.NewRunsRepo(db)
	allocator := NewPortAllocator()
	docker := newFakeDocker()
	docker.healthStatus = "starting" // never becomes healthy

	branch := "main"
	task := &store.Task{ID: "t1", ProjectID: "p1", State: "in_progress", Branch: &branch}
	wts := []store.Worktree{{ID: "w1", TaskID: stringPtr("t1"), Path: dir}}
	proj := &store.Project{ID: "p1", Path: "/projects/p1"}

	seedProjectAndTaskForRuns(t, db, "p1", "t1")

	svc := NewRunsService(repo, docker, allocator,
		&stubTasksRepo{task: task},
		&stubWorktreesRepo{wts: wts},
		&stubProjectsRepo{proj: proj},
		&events.FakeEmitter{})
	svc.dockerCheck = func() error { return nil }

	_, err := svc.StartRun(context.Background(), "t1")
	if err == nil {
		t.Fatal("StartRun: nil err, want healthcheck timeout")
	}
	if len(docker.stops) != 1 || len(docker.rms) != 1 {
		t.Errorf("expected 1 stop + 1 rm, got %d/%d", len(docker.stops), len(docker.rms))
	}
	if len(docker.netRmCalls) != 1 {
		t.Errorf("expected 1 network rm, got %d", len(docker.netRmCalls))
	}
}

func TestStartRun_SeedFails_RollsBack(t *testing.T) {
	dir := t.TempDir()
	_ = os.MkdirAll(filepath.Join(dir, ".orchestrator"), 0o755)
	manifest := `version: "1"
services:
  db:
    image: postgres:15
    port: 5432
    seed:
      command: ["psql", "-c", "select 1"]
      timeout: 5s
`
	_ = os.WriteFile(filepath.Join(dir, ".orchestrator", "run.yml"), []byte(manifest), 0o644)

	db := newTestStoreDB(t)
	repo := store.NewRunsRepo(db)
	allocator := NewPortAllocator()
	docker := newFakeDocker()
	docker.runInContainerErr = errors.New("seed boom")

	branch := "main"
	task := &store.Task{ID: "t1", ProjectID: "p1", State: "in_progress", Branch: &branch}
	wts := []store.Worktree{{ID: "w1", TaskID: stringPtr("t1"), Path: dir}}
	proj := &store.Project{ID: "p1", Path: "/projects/p1"}

	seedProjectAndTaskForRuns(t, db, "p1", "t1")

	svc := NewRunsService(repo, docker, allocator,
		&stubTasksRepo{task: task},
		&stubWorktreesRepo{wts: wts},
		&stubProjectsRepo{proj: proj},
		&events.FakeEmitter{})
	svc.dockerCheck = func() error { return nil }

	_, err := svc.StartRun(context.Background(), "t1")
	if err == nil {
		t.Fatal("StartRun: nil err, want seed failure")
	}
	if len(docker.stops) == 0 {
		t.Error("rollback should have stopped container after seed failure")
	}
}

func TestStopRun_ParallelStops_ClearsResources(t *testing.T) {
	db := newTestStoreDB(t)
	repo := store.NewRunsRepo(db)
	allocator := NewPortAllocator()
	docker := newFakeDocker()
	allocator.Reserve(31000)

	seedProjectAndTaskForRuns(t, db, "p1", "t1")

	run := store.Run{
		ID: "run-1", TaskID: "t1", Status: "ready", Cwd: "/x",
		NetworkName:    "jarvis-run-run-1",
		PortsJSON:      `{"web":31000}`,
		ContainersJSON: `{"db":"cid-db","backend":"cid-backend","frontend":"cid-frontend"}`,
		StartedAt:      time.Now(),
	}
	_ = repo.Insert(context.Background(), run)

	svc := NewRunsService(repo, docker, allocator,
		&stubTasksRepo{}, &stubWorktreesRepo{}, &stubProjectsRepo{},
		&events.FakeEmitter{})

	if err := svc.StopRun(context.Background(), "run-1"); err != nil {
		t.Fatalf("StopRun: %v", err)
	}
	if len(docker.stops) != 3 {
		t.Errorf("stops=%d, want 3", len(docker.stops))
	}
	if len(docker.rms) != 3 {
		t.Errorf("rms=%d, want 3", len(docker.rms))
	}
	if len(docker.netRmCalls) != 1 {
		t.Errorf("netRm=%d, want 1", len(docker.netRmCalls))
	}
	got, _ := repo.GetByID(context.Background(), "run-1")
	if got.Status != "stopped" || got.EndedAt == nil {
		t.Errorf("status=%q EndedAt=%v, want stopped/non-nil", got.Status, got.EndedAt)
	}
}

func TestStopRun_Idempotent(t *testing.T) {
	db := newTestStoreDB(t)
	repo := store.NewRunsRepo(db)
	docker := newFakeDocker()
	seedProjectAndTaskForRuns(t, db, "p1", "t1")

	run := store.Run{
		ID: "run-1", TaskID: "t1", Status: "stopped",
		Cwd: "/x", StartedAt: time.Now(),
	}
	_ = repo.Insert(context.Background(), run)
	_ = repo.MarkEnded(context.Background(), "run-1", "stopped", "")

	svc := NewRunsService(repo, docker, NewPortAllocator(),
		&stubTasksRepo{}, &stubWorktreesRepo{}, &stubProjectsRepo{},
		&events.FakeEmitter{})

	if err := svc.StopRun(context.Background(), "run-1"); err != nil {
		t.Fatalf("StopRun: %v", err)
	}
	if len(docker.stops) != 0 {
		t.Errorf("idempotent StopRun should not invoke docker, got stops=%d", len(docker.stops))
	}
}

func TestCleanupForTask_StopsActiveRun(t *testing.T) {
	db := newTestStoreDB(t)
	repo := store.NewRunsRepo(db)
	docker := newFakeDocker()
	seedProjectAndTaskForRuns(t, db, "p1", "t1")

	run := store.Run{
		ID: "run-1", TaskID: "t1", Status: "ready",
		Cwd: "/x", NetworkName: "net-1",
		ContainersJSON: `{"web":"cid-w"}`,
		StartedAt:      time.Now(),
	}
	_ = repo.Insert(context.Background(), run)

	svc := NewRunsService(repo, docker, NewPortAllocator(),
		&stubTasksRepo{}, &stubWorktreesRepo{}, &stubProjectsRepo{},
		&events.FakeEmitter{})

	if err := svc.CleanupForTask(context.Background(), "t1"); err != nil {
		t.Fatalf("CleanupForTask: %v", err)
	}
	if len(docker.stops) == 0 {
		t.Error("CleanupForTask should have stopped active run's containers")
	}
}

func TestCleanupForTask_NoActiveRun_NoOp(t *testing.T) {
	db := newTestStoreDB(t)
	repo := store.NewRunsRepo(db)
	docker := newFakeDocker()
	svc := NewRunsService(repo, docker, NewPortAllocator(),
		&stubTasksRepo{}, &stubWorktreesRepo{}, &stubProjectsRepo{},
		&events.FakeEmitter{})
	if err := svc.CleanupForTask(context.Background(), "no-such-task"); err != nil {
		t.Errorf("CleanupForTask on empty: %v", err)
	}
}

func TestCleanupOrphans_StopsAllActive(t *testing.T) {
	db := newTestStoreDB(t)
	repo := store.NewRunsRepo(db)
	docker := newFakeDocker()
	seedProjectAndTaskForRuns(t, db, "p1", "t1")
	seedProjectAndTaskForRuns(t, db, "p2", "t2")

	_ = repo.Insert(context.Background(), store.Run{
		ID: "r1", TaskID: "t1", Status: "ready", Cwd: "/a", NetworkName: "n1",
		ContainersJSON: `{"web":"cid-w1"}`, StartedAt: time.Now(),
	})
	_ = repo.Insert(context.Background(), store.Run{
		ID: "r2", TaskID: "t2", Status: "ready", Cwd: "/b", NetworkName: "n2",
		ContainersJSON: `{"web":"cid-w2"}`, StartedAt: time.Now(),
	})

	svc := NewRunsService(repo, docker, NewPortAllocator(),
		&stubTasksRepo{}, &stubWorktreesRepo{}, &stubProjectsRepo{},
		&events.FakeEmitter{})

	if err := svc.CleanupOrphans(context.Background()); err != nil {
		t.Fatalf("CleanupOrphans: %v", err)
	}
	active, _ := repo.ListActive(context.Background())
	if len(active) != 0 {
		t.Errorf("active after orphan cleanup: %d, want 0", len(active))
	}
}

func TestContainerIDFor_ReturnsCorrectID(t *testing.T) {
	db := newTestStoreDB(t)
	repo := store.NewRunsRepo(db)
	docker := newFakeDocker()
	seedProjectAndTaskForRuns(t, db, "p1", "t1")
	_ = repo.Insert(context.Background(), store.Run{
		ID: "run-1", TaskID: "t1", Status: "ready", Cwd: "/x",
		ContainersJSON: `{"db":"cid-a","backend":"cid-b"}`,
		StartedAt:      time.Now(),
	})

	svc := NewRunsService(repo, docker, NewPortAllocator(),
		&stubTasksRepo{}, &stubWorktreesRepo{}, &stubProjectsRepo{},
		&events.FakeEmitter{})

	cid, err := svc.ContainerIDFor(context.Background(), "run-1", "db")
	if err != nil {
		t.Fatalf("ContainerIDFor: %v", err)
	}
	if cid != "cid-a" {
		t.Errorf("cid=%q, want cid-a", cid)
	}

	_, err = svc.ContainerIDFor(context.Background(), "run-1", "ghost")
	if err == nil {
		t.Error("ContainerIDFor with unknown service should error")
	}
}
