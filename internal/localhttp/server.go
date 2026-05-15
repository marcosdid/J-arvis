// Package localhttp owns the loopback HTTP listener that hosts the
// internal subsystems (hooks, mcp). It binds 127.0.0.1:0 and exposes
// a Mount(prefix, http.Handler) API so each subsystem registers its
// routes without owning the listener.
package localhttp

import (
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
