package core

import (
	"context"
	"errors"
	"os"
	"sync"
	"testing"

	"github.com/marcosdid/jarvis/internal/events"
	"github.com/marcosdid/jarvis/internal/store"
)

// fakeMasterSession satisfies the masterSession interface used by MasterService.
type fakeMasterSession struct {
	mu        sync.Mutex
	spawnedAt string // cwd captured by StartAijail
	spawnPID  int
	spawnErr  error
	running   bool
	onOutput  func(string)
	onExit    func(error)
}

func (f *fakeMasterSession) StartAijail(cwd string) (int, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	if f.spawnErr != nil {
		return 0, f.spawnErr
	}
	f.spawnedAt = cwd
	f.running = true
	return f.spawnPID, nil
}
func (f *fakeMasterSession) Send(string) error           { return nil }
func (f *fakeMasterSession) Resize(uint16, uint16) error { return nil }
func (f *fakeMasterSession) Stop() error                 { f.running = false; return nil }
func (f *fakeMasterSession) Running() bool               { return f.running }
func (f *fakeMasterSession) PID() int                    { return f.spawnPID }
func (f *fakeMasterSession) SetOnOutput(fn func(string)) { f.onOutput = fn }
func (f *fakeMasterSession) SetOnExit(fn func(error))    { f.onExit = fn }

func TestMasterService_Start_NoRow_GeneratesNewSessionID(t *testing.T) {
	db := newTestStoreDB(t)
	repo := store.NewMasterSessionRepo(db)
	fs := &fakeMasterSession{spawnPID: 4242}
	svc := NewMasterService(repo, fs,
		func() string { return "http://127.0.0.1:8080" },
		"test-token", t.TempDir(), &events.FakeEmitter{})
	svc.sandboxCheck = func() error { return nil } // bypass real ai-jail check
	got, err := svc.Start(context.Background())
	if err != nil {
		t.Fatalf("Start: %v", err)
	}
	if got.ClaudeSessionID == "" {
		t.Error("ClaudeSessionID empty; want a UUID")
	}
	if got.PID == nil || *got.PID != 4242 {
		t.Errorf("PID=%v, want 4242", got.PID)
	}
	if fs.spawnedAt == "" {
		t.Error("StartAijail not called")
	}
}

func TestMasterService_Start_MCPUnavailable_Errors(t *testing.T) {
	db := newTestStoreDB(t)
	repo := store.NewMasterSessionRepo(db)
	svc := NewMasterService(repo, &fakeMasterSession{},
		func() string { return "" }, // empty URL → preflight fails
		"test-token", t.TempDir(), &events.FakeEmitter{})
	svc.sandboxCheck = func() error { return nil }
	_, err := svc.Start(context.Background())
	if !errors.Is(err, ErrMasterMCPUnavailable) {
		t.Errorf("err=%v, want ErrMasterMCPUnavailable", err)
	}
}

func TestMasterService_Start_ExistingRow_ReusesSessionID(t *testing.T) {
	db := newTestStoreDB(t)
	repo := store.NewMasterSessionRepo(db)
	// Seed: row exists with session_id but PID nil (stopped cleanly)
	_ = repo.Upsert(context.Background(), "saved-uuid", 0)
	_ = repo.ClearPID(context.Background())

	fs := &fakeMasterSession{spawnPID: 999}
	svc := newTestMasterService(t, repo, fs)
	got, err := svc.Start(context.Background())
	if err != nil {
		t.Fatalf("Start: %v", err)
	}
	if got.ClaudeSessionID != "saved-uuid" {
		t.Errorf("ClaudeSessionID=%q, want saved-uuid (reuse)", got.ClaudeSessionID)
	}
}

func TestMasterService_Start_AlreadyRunning_IsIdempotent(t *testing.T) {
	db := newTestStoreDB(t)
	repo := store.NewMasterSessionRepo(db)
	// Seed: row with PID of current test process (guaranteed alive)
	_ = repo.Upsert(context.Background(), "live-uuid", os.Getpid())

	fs := &fakeMasterSession{spawnPID: 1}
	svc := newTestMasterService(t, repo, fs)
	got, err := svc.Start(context.Background())
	if err != nil {
		t.Fatalf("Start: %v", err)
	}
	if got.ClaudeSessionID != "live-uuid" {
		t.Errorf("ClaudeSessionID=%q, want live-uuid (idempotent)", got.ClaudeSessionID)
	}
	if fs.spawnedAt != "" {
		t.Error("StartAijail called on idempotent Start; should be no-op")
	}
}

// newTestMasterService wires a MasterService with the sandbox preflight bypassed.
func newTestMasterService(t *testing.T, repo *store.MasterSessionRepo, fs *fakeMasterSession) *MasterService {
	t.Helper()
	svc := NewMasterService(repo, fs,
		func() string { return "http://127.0.0.1:8080" },
		"test-token", t.TempDir(), &events.FakeEmitter{})
	svc.sandboxCheck = func() error { return nil }
	return svc
}
