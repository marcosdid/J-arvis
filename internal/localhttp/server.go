// Package localhttp owns the loopback HTTP listener that hosts the
// internal subsystems (hooks, mcp). It binds 127.0.0.1:0 and exposes
// a Mount(prefix, http.Handler) API so each subsystem registers its
// routes without owning the listener.
package localhttp

import (
	"context"
	"errors"
	"fmt"
	"net"
	"net/http"
	"sync"
	"time"
)

type Server struct {
	mu       sync.Mutex
	mux      *http.ServeMux
	srv      *http.Server
	listener net.Listener
	started  bool
}

func New() *Server {
	return &Server{mux: http.NewServeMux()}
}

func (s *Server) Started() bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.started
}

var ErrAlreadyStarted = errors.New("localhttp: already started")

func (s *Server) Mount(pattern string, h http.Handler) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.started {
		return ErrAlreadyStarted
	}
	s.mux.Handle(pattern, h)
	return nil
}

func (s *Server) Start() (port int, err error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.started {
		return 0, ErrAlreadyStarted
	}
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return 0, fmt.Errorf("localhttp: listen: %w", err)
	}
	s.listener = ln
	s.srv = &http.Server{
		Handler:           s.mux,
		ReadHeaderTimeout: 5 * time.Second,
	}
	s.started = true
	srv := s.srv
	go func() { _ = srv.Serve(ln) }()
	return ln.Addr().(*net.TCPAddr).Port, nil
}

func (s *Server) Stop() error {
	s.mu.Lock()
	srv := s.srv
	s.srv = nil
	s.listener = nil
	s.started = false
	s.mu.Unlock()
	if srv == nil {
		return nil
	}
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	return srv.Shutdown(ctx)
}

func (s *Server) BaseURL() string {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.listener == nil {
		return ""
	}
	return fmt.Sprintf("http://127.0.0.1:%d", s.listener.Addr().(*net.TCPAddr).Port)
}
