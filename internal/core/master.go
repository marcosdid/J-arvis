package core

import (
	"context"
	"errors"
	"fmt"
	"net/url"
	"os"
	"strconv"
	"sync"
	"syscall"
	"time"

	"github.com/google/uuid"

	"github.com/marcosdid/jarvis/internal/events"
	"github.com/marcosdid/jarvis/internal/sandbox"
	"github.com/marcosdid/jarvis/internal/store"
)

var (
	ErrMasterSandboxUnavailable = errors.New("master: sandbox (ai-jail) unavailable")
	ErrMasterMCPUnavailable     = errors.New("master: MCP URL not yet available (localSrv not started)")
	ErrMasterSpawnFailed        = errors.New("master: spawn failed")
)

// masterSession is the slice of *master.Session that MasterService needs.
// Defined here so tests can mock without importing master.
type masterSession interface {
	StartAijail(cwd string) (int, error)
	Send(data string) error
	Resize(rows, cols uint16) error
	Stop() error
	Running() bool
	PID() int
	SetOnOutput(func(chunk string))
	SetOnExit(func(err error))
}

type MasterStatus struct {
	Running   bool   `json:"running"`
	PID       int    `json:"pid"`
	SessionID string `json:"session_id"`
}

type MasterSession struct {
	ClaudeSessionID string    `json:"claude_session_id"`
	PID             *int      `json:"pid"`
	StartedAt       time.Time `json:"started_at"`
}

type MasterService struct {
	mu                 sync.Mutex
	repo               *store.MasterSessionRepo
	session            masterSession
	mcpURL             func() string // lazy: localSrv.BaseURL() may not be ready at construction
	mcpToken           string        // bearer token value
	masterCwd          string
	bus                events.Emitter
	sandboxCheck       func() error      // injectable for tests
	waitForProcessExit func(pid int)     // injectable for tests
}

// defaultWaitForProcessExit polls syscall.Kill(pid, 0) every 200ms until ESRCH.
func defaultWaitForProcessExit(pid int) {
	for {
		if err := syscall.Kill(pid, 0); err != nil {
			return // process gone
		}
		time.Sleep(200 * time.Millisecond)
	}
}

func NewMasterService(
	repo *store.MasterSessionRepo,
	session masterSession,
	mcpURL func() string,
	mcpToken string,
	masterCwd string,
	bus events.Emitter,
) *MasterService {
	return &MasterService{
		repo:               repo,
		session:            session,
		mcpURL:             mcpURL,
		mcpToken:           mcpToken,
		masterCwd:          masterCwd,
		bus:                bus,
		sandboxCheck:       sandbox.SandboxAvailable,
		waitForProcessExit: defaultWaitForProcessExit,
	}
}

func (s *MasterService) Start(ctx context.Context) (*MasterSession, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	// 1. Preflight: ai-jail
	if err := s.sandboxCheck(); err != nil {
		return nil, fmt.Errorf("%w: %v", ErrMasterSandboxUnavailable, err)
	}
	// 1b. Preflight: MCP URL
	mcpURL := s.mcpURL()
	if mcpURL == "" {
		return nil, ErrMasterMCPUnavailable
	}

	// 2. DB lookup. Already running?
	row, err := s.repo.Get(ctx)
	if err == nil && row.PID != nil && processAlive(*row.PID) {
		return rowToSession(row), nil
	}

	// 3. Determine session_id (reuse or new)
	sessionID := uuid.NewString()
	if err == nil && row.ClaudeSessionID != "" {
		sessionID = row.ClaudeSessionID
	}

	// 4. Ensure CWD exists
	if err := os.MkdirAll(s.masterCwd, 0o755); err != nil {
		return nil, fmt.Errorf("create master cwd: %w", err)
	}

	// 5. Configs (both writers overwrite — partial failure is self-healing)
	if err := sandbox.WriteMasterSettings(s.masterCwd, mcpURL, s.mcpToken); err != nil {
		return nil, fmt.Errorf("write master settings: %w", err)
	}
	claudeArgs := []string{"--dangerously-skip-permissions", "--resume", sessionID}
	mcpPort := portFromURL(mcpURL)
	if err := sandbox.WriteAijailConfig(s.masterCwd, claudeArgs, []int{mcpPort}); err != nil {
		return nil, fmt.Errorf("write master .ai-jail: %w", err)
	}

	// 6. Spawn PTY
	pid, err := s.session.StartAijail(s.masterCwd)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrMasterSpawnFailed, err)
	}

	// 7. Persist row
	if err := s.repo.Upsert(ctx, sessionID, pid); err != nil {
		_ = s.session.Stop()
		return nil, fmt.Errorf("persist master row: %w", err)
	}

	// 8. Watchdog (Stage 6 — placeholder, no-op for now)
	go s.watchdog(sessionID, pid)

	s.bus.Emit("master.status", MasterStatus{Running: true, PID: pid, SessionID: sessionID})
	now := time.Now()
	return &MasterSession{ClaudeSessionID: sessionID, PID: &pid, StartedAt: now}, nil
}

func (s *MasterService) Stop(ctx context.Context) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	row, err := s.repo.Get(ctx)
	if err != nil {
		return nil // nothing to stop
	}
	if row.PID != nil && processAlive(*row.PID) {
		_ = syscall.Kill(*row.PID, syscall.SIGTERM)
	}
	if err := s.repo.ClearPID(ctx); err != nil {
		return err
	}
	s.bus.Emit("master.status", MasterStatus{
		Running: false, SessionID: row.ClaudeSessionID,
	})
	return nil
}

func rowToSession(r *store.MasterSession) *MasterSession {
	return &MasterSession{
		ClaudeSessionID: r.ClaudeSessionID,
		PID:             r.PID,
		StartedAt:       r.StartedAt,
	}
}

func portFromURL(rawURL string) int {
	u, err := url.Parse(rawURL)
	if err != nil {
		return 0
	}
	p, _ := strconv.Atoi(u.Port())
	return p
}

// watchdog stub — real impl in Stage 6.
func (s *MasterService) watchdog(sessionID string, pid int) {
	start := time.Now()
	s.waitForProcessExit(pid)
	elapsed := time.Since(start)

	early := elapsed < 2*time.Second

	ctx := context.Background()
	if early {
		_ = s.repo.Delete(ctx)
	} else {
		_ = s.repo.ClearPID(ctx)
	}

	s.bus.Emit("master.exit", map[string]any{
		"session_id":  sessionID,
		"early_exit":  early,
		"elapsed_ms":  elapsed.Milliseconds(),
	})
}

// Send delegates to the underlying masterSession.
func (s *MasterService) Send(data string) error {
	return s.session.Send(data)
}

// Resize delegates to the underlying masterSession.
func (s *MasterService) Resize(rows, cols uint16) error {
	return s.session.Resize(rows, cols)
}

// SetOnOutput delegates to the underlying masterSession.
func (s *MasterService) SetOnOutput(fn func(string)) {
	s.session.SetOnOutput(fn)
}

// SetOnExit delegates to the underlying masterSession.
func (s *MasterService) SetOnExit(fn func(error)) {
	s.session.SetOnExit(fn)
}

// Status reads the DB row and verifies the PID is live. A stale PID (process
// died, watchdog hasn't fired yet) reports Running=false.
func (s *MasterService) Status(ctx context.Context) MasterStatus {
	row, err := s.repo.Get(ctx)
	if err != nil {
		return MasterStatus{Running: false}
	}
	running := row.PID != nil && processAlive(*row.PID)
	pid := 0
	if running {
		pid = *row.PID
	}
	return MasterStatus{
		Running:   running,
		PID:       pid,
		SessionID: row.ClaudeSessionID,
	}
}

// processAlive returns true if a Unix process with the given PID exists and
// is reachable by the current user. Uses kill(pid, 0) which returns ESRCH
// when no such process exists.
func processAlive(pid int) bool {
	if pid <= 0 {
		return false
	}
	err := syscall.Kill(pid, 0)
	return err == nil
}
