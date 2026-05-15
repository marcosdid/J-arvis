// Package localhttp owns the loopback HTTP listener that hosts the
// internal subsystems (hooks, mcp). It binds 127.0.0.1:0 and exposes
// a Mount(prefix, http.Handler) API so each subsystem registers its
// routes without owning the listener.
package localhttp

import (
	"errors"
	"net/http"
	"sync"
)

type Server struct {
	mu      sync.Mutex
	mux     *http.ServeMux
	started bool
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
