package master

import (
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"sync"
	"sync/atomic"

	"github.com/creack/pty"
)

// Session manages a long-running claude-code subprocess attached to a pty.
// Reads stdout from the pty and forwards chunks to OnOutput; writes user
// input via Send; resizes the pty via Resize.
type Session struct {
	cmd      *exec.Cmd
	tty      *os.File
	mu       sync.Mutex
	running  atomic.Bool
	OnOutput func(chunk string)
	OnExit   func(err error)
}

func New() *Session {
	return &Session{}
}

// Start spawns the claude binary inside a pty. binPath may be empty; in
// that case "claude" is looked up via PATH. extraArgs are appended to
// the command line (e.g. ["--print", "hello"] for one-shot smoke tests).
func (s *Session) Start(binPath string, extraArgs []string) error {
	if s.running.Load() {
		return errors.New("session already running")
	}
	bin := binPath
	if bin == "" {
		bin = "claude"
	}
	cmd := exec.Command(bin, extraArgs...)
	cmd.Env = append(os.Environ(), "TERM=xterm-256color")

	tty, err := pty.Start(cmd)
	if err != nil {
		return fmt.Errorf("pty.Start: %w", err)
	}

	s.mu.Lock()
	s.cmd = cmd
	s.tty = tty
	s.mu.Unlock()
	s.running.Store(true)

	go s.readLoop()
	go s.waitLoop()
	return nil
}

func (s *Session) readLoop() {
	buf := make([]byte, 4096)
	for {
		s.mu.Lock()
		tty := s.tty
		s.mu.Unlock()
		if tty == nil {
			return
		}
		n, err := tty.Read(buf)
		if n > 0 && s.OnOutput != nil {
			s.OnOutput(string(buf[:n]))
		}
		if err != nil {
			if !errors.Is(err, io.EOF) && err != os.ErrClosed {
				// EIO etc when pty closes — terminate read loop quietly.
			}
			return
		}
	}
}

func (s *Session) waitLoop() {
	s.mu.Lock()
	cmd := s.cmd
	s.mu.Unlock()
	if cmd == nil {
		return
	}
	err := cmd.Wait()
	s.running.Store(false)
	if s.OnExit != nil {
		s.OnExit(err)
	}
}

func (s *Session) Send(data string) error {
	if !s.running.Load() {
		return errors.New("session not running")
	}
	s.mu.Lock()
	tty := s.tty
	s.mu.Unlock()
	if tty == nil {
		return errors.New("pty closed")
	}
	_, err := tty.Write([]byte(data))
	return err
}

func (s *Session) Resize(rows, cols uint16) error {
	s.mu.Lock()
	tty := s.tty
	s.mu.Unlock()
	if tty == nil {
		return errors.New("pty closed")
	}
	return pty.Setsize(tty, &pty.Winsize{Rows: rows, Cols: cols})
}

func (s *Session) Stop() error {
	if !s.running.Load() {
		return nil
	}
	s.mu.Lock()
	cmd := s.cmd
	tty := s.tty
	s.tty = nil
	s.mu.Unlock()
	if tty != nil {
		_ = tty.Close()
	}
	if cmd != nil && cmd.Process != nil {
		_ = cmd.Process.Kill()
	}
	return nil
}

func (s *Session) Running() bool {
	return s.running.Load()
}

func (s *Session) PID() int {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.cmd == nil || s.cmd.Process == nil {
		return 0
	}
	return s.cmd.Process.Pid
}
